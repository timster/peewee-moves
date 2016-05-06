from contextlib import contextmanager
from datetime import datetime
import inspect
import os
import pydoc
import sys

from playhouse.db_url import connect as db_url_connect
from playhouse.migrate import SchemaMigrator
import peewee

try:
    FLASK_ENABLED = True
    from flask import current_app
    from flask_script import Manager
except ImportError:
    FLASK_ENABLED = False

__all__ = ['migration_manager', 'MigrationHistory', 'DatabaseManager', 'TableCreator', 'Migrator']

FIELD_TO_PEEWEE = {
    'bare': peewee.BareField,
    'biginteger': peewee.BigIntegerField,
    'binary': peewee.BlobField,
    'blob': peewee.BlobField,
    'bool': peewee.BooleanField,
    'char': peewee.CharField,
    'date': peewee.DateField,
    'datetime': peewee.DateTimeField,
    'decimal': peewee.DecimalField,
    'double': peewee.DoubleField,
    'fixed': peewee.FixedCharField,
    'float': peewee.FloatField,
    'integer': peewee.IntegerField,
    'int': peewee.IntegerField,
    'smallinteger': peewee.SmallIntegerField,
    'smallint': peewee.SmallIntegerField,
    'text': peewee.TextField,
    'time': peewee.TimeField,
    'uuid': peewee.UUIDField,
}

PEEWEE_TO_FIELD = {value: key for key, value in FIELD_TO_PEEWEE.items()}
PEEWEE_TO_FIELD[peewee.PrimaryKeyField] = 'primary_key'
PEEWEE_TO_FIELD[peewee.ForeignKeyField] = 'foreign_key'

FIELD_KWARGS = (
    'null', 'index', 'unique', 'constraints', 'sequence',
    'max_length', 'max_digits', 'decimal_places'
)

TEMPLATE = (
    '"""\n{name}\ndate created: {date}\n"""\n\n\n',
    'def upgrade(migrator):\n    {upgrade}\n\n\n',
    'def downgrade(migrator):\n    {downgrade}\n'
)
TEMPLATE = str.join('', TEMPLATE)


if FLASK_ENABLED:

    migration_manager = Manager(usage='{} db [command]'.format(sys.argv[0]))

    def get_database_manager():
        """Return a DatabaseManager for the current Flask application."""
        return DatabaseManager(current_app.config['DATABASE'], directory='app/migrations')

    @migration_manager.option('-m', '--model', dest='model', required=False)
    def create(model):
        """Create a migration based on an existing model."""
        get_database_manager().create(model)

    @migration_manager.option('-n', '--name', dest='name', required=False)
    def revision(name):
        """Create a blank migration file."""
        get_database_manager().revision(name)

    @migration_manager.command
    def status():
        """Show information about the database."""
        get_database_manager().status()

    @migration_manager.command
    def info():
        """Show all migrations and the status of each."""
        get_database_manager().status()

    @migration_manager.option('-t', '--target', dest='target', required=False)
    def upgrade(target):
        """Run database upgrades."""
        get_database_manager().upgrade(target)

    @migration_manager.option('-t', '--target', dest='target', required=False)
    def downgrade(target):
        """Run database downgrades."""
        get_database_manager().downgrade(target)

    @migration_manager.option('-t', '--target', dest='target', required=True)
    def delete(target):
        """Delete the target migration from the filesystem and database."""
        get_database_manager().delete(target)


def build_downgrade_from_model(model):
    """
    Build a list of 'downgrade' operations for a model class.
    Each value that is yieled is one operation.

    :param model: Peewee model class or instance.
    :return: generator
    :rtype: str
    """
    yield "migrator.drop_table('{}')".format(model._meta.db_table)


def build_upgrade_from_model(model):
    """
    Build a list of 'upgrade' operations for a model class.
    Each value that is yieled is one operation.

    :param model: Peewee model class or instance.
    :return: generator
    :rtype: str
    """
    yield "with migrator.create_table('{}') as table:".format(model._meta.db_table)

    for field in model._meta.sorted_fields:
        coltype = PEEWEE_TO_FIELD.get(field.__class__, 'char')

        # Add all fields. Foreign Key is a special case.
        if coltype == 'foreign_key':
            other_table = field.rel_model._meta.db_table
            other_col = field.to_field.db_column
            kwargs = {'references': '{}.{}'.format(other_table, other_col)}
        else:
            kwargs = {
                key: getattr(field, key) for key in FIELD_KWARGS if getattr(field, key, None)
            }

        # Flatten the keyword arguments for the field.
        args_list = ["'{}'".format(field.db_column)]
        for key, value in sorted(kwargs.items()):
            if isinstance(value, str):
                value = "'{}'".format(value)
            args_list.append('{}={}'.format(key, value))

        # Then yield the field!
        yield "        table.{}({})".format(coltype, str.join(', ', args_list))

    indexes = getattr(model._meta, 'indexes', [])
    if indexes:
        for columns, unique in indexes:
            yield "        table.add_index({}, unique={})".format(columns, unique)

    constraints = getattr(model._meta, 'constraints', [])
    if constraints:
        for const in constraints:
            yield "        table.add_constraint({})".format(const)


class MigrationHistory(peewee.Model):
    name = peewee.CharField()
    date_applied = peewee.DateTimeField(default=datetime.utcnow)

    class Meta:
        db_table = 'migration_history'


class DatabaseManager:
    def __init__(self, database, table_name='migration_history', directory='migrations'):
        """
        Initialize a DatabaseManager with the given options.

        :param database: Connection string, dict, or peewee.Database instance to use.
        :param table_name: Table name to hold migrations (default migration_history).
        :param directory: Directory to store migrations (default migrations).
        """
        self.directory = str(directory)
        os.makedirs(self.directory, exist_ok=True)
        self.database = self.load_database(database)
        self.migrator = Migrator(self.database)

        MigrationHistory._meta.database = self.database
        MigrationHistory._meta.db_table = table_name
        MigrationHistory.create_table(fail_silently=True)

    def load_database(self, database):
        """
        Load the given database, whatever it might be.

        :param database: Connection string, dict, or peewee.Database instance to use.
        :raises: peewee.DatabaseError if database connection cannot be established.
        :return: Database connection.
        :rtype: peewee.Database instance.
        """
        if isinstance(database, peewee.Database):
            return database

        if isinstance(database, dict):
            try:
                name = database.pop('name')
                engine = database.pop('engine')
            except KeyError:
                error_msg = 'Configuration dict must specify "name" and "engine" keys.'
                raise peewee.DatabaseError(error_msg)

            db_class = pydoc.locate(engine)
            if not db_class:
                raise peewee.DatabaseError('Unable to import engine class: {}'.format(engine))
            return db_class(name, **database)

        return db_url_connect(database)

    @property
    def migration_files(self):
        """
        List all the migrations sitting on the filesystem.

        :return: List of migration names.
        :rtype: list
        """
        files = (f[:-len('.py')] for f in os.listdir(self.directory) if f.endswith('.py'))
        return sorted(files)

    @property
    def db_migrations(self):
        """
        List all the migrations applied to the database.

        :return: List of migration names.
        :rtype: list
        """
        return sorted(row.name for row in MigrationHistory.select())

    @property
    def diff(self):
        """
        List all the migrations that have not been applied to the database.

        :return: List of migration names.
        :rtype: list
        """
        return sorted(set(self.migration_files) - set(self.db_migrations))

    def find_migration(self, value):
        """
        Try to find a migration by name or start of name.

        :raises: ValueError if no matching migration is found.
        :return: Name of matching migration.
        :rtype: str
        """
        value = str(value)
        for name in self.migration_files:
            if name == value:
                return name
            if name.startswith('{}_'.format(value)):
                return name
        raise ValueError('could not find migration: {}'.format(value))

    def get_ident(self):
        """
        Return a unique identifier for a revision. Override this method to change functionality.
        Make sure the IDs will be sortable (like timestamps or incremental numbers).

        :return: Name of new migration.
        :rtype: str
        """
        next_id = 1
        if self.migration_files:
            next_id = int(list(self.migration_files)[-1].split('_')[0]) + 1
        return '{:04}'.format(next_id)

    def next_migration(self, name):
        """
        Get the name of the next migration that should be created.

        :param name: Name to use for migration (not including identifier).
        :return: Name of new migration.
        :rtype: str
        """
        return '{}_{}'.format(self.get_ident(), name.replace(' ', '_'))

    def get_filename(self, migration):
        """
        Return the full path and filename for the given migration.

        :param migration: Name of migration to find (not including extension).
        :return: Path and filename to migration.
        :rtype: str
        """
        return os.path.join(self.directory, '{}.py'.format(migration))

    def open_migration(self, migration, mode='r'):
        """
        Open a migration file with the given mode and return it.

        :param migration: Name of migration to find (not including extension).
        :param mode: Mode to pass to open(). Most likely 'r' or 'w'.
        :raises: IOError if the file cannot be opened.
        :return: File instance.
        :rtype: io.FileIO
        """
        return open(self.get_filename(migration), mode)

    def info(self):
        """
        Show the current database.
        Don't include any sensitive information like passwords.

        :return: String representation.
        :rtype: str
        """
        driver = self.database.__class__.__name__
        database = self.database.database
        print('INFO:', 'Driver:', driver)
        print('INFO:', 'Database:', database)

    def delete(self, migration):
        """
        Delete the migration from filesystem and database. As if it never happened.

        :param migration: Name of migration to find (not including extension).
        :return: True if delete was successful, otherwise False.
        :type: bool
        """
        try:
            migration = self.find_migration(migration)
            os.remove(self.get_filename(migration))
            with self.database.transaction():
                cmd = MigrationHistory.delete().where(MigrationHistory.name == migration)
                cmd.execute()
        except Exception as exc:
            self.database.rollback()
            print('ERROR:', exc)
            return False

        print('INFO:', '{}: delete'.format(migration))
        return True

    def status(self):
        """
        Show all the migrations and a status for each.

        :return: True if listing was successful, otherwise None.
        :type: bool
        """
        if not self.migration_files:
            print('INFO:', 'no migrations found')
            return True
        for name in self.migration_files:
            status = 'applied' if name in self.db_migrations else 'pending'
            print('INFO:', '{}: {}'.format(name, status))
        return True

    def upgrade(self, target=None):
        """
        Run all the migrations (up to target if specified). If no target, run all upgrades.

        :param target: Migration target to limit upgrades.
        :return: True if upgrade was successful, otherwise False.
        :type: bool
        """
        try:
            if target:
                target = self.find_migration(target)
                if target in self.db_migrations:
                    print('INFO:', '{}: already applied'.format(target))
                    return False
        except ValueError as exc:
            print('ERROR:', exc)
            return False

        if self.diff:
            for name in self.diff:
                rv = self.run_migration(name, 'upgrade')
                # If it didn't work, don't try any more.
                # Or if we are at the end of the line, don't run anymore.
                if not rv or (target and target == name):
                    break
            return True

        print('INFO:', 'all migrations applied!')
        return True

    def downgrade(self, target=None):
        """
        Run all the migrations (down to target if specified). If no target, run one downgrade.

        :param target: Migration target to limit downgrades.
        :return: True if downgrade was successful, otherwise False.
        :type: bool
        """
        try:
            if target:
                target = self.find_migration(target)
                if target not in self.db_migrations:
                    print('INFO:', '{}: not yet applied'.format(target))
                    return False
        except ValueError as exc:
            print('ERROR:', exc)
            return False

        diff = self.db_migrations[::-1]
        if diff:
            for name in diff:
                rv = self.run_migration(name, 'downgrade')
                # If it didn't work, don't try any more.
                # Or if we are at the end of the line, don't run anymore.
                if not rv or (not target or target == name):
                    break
            return True

        print('INFO:', 'migrations not yet applied!')
        return True

    def run_migration(self, migration, direction='upgrade'):
        """
        Run a single migration. Does not check to see if migration has already been applied.

        :param migration: Migration to run.
        :param: Direction to run (either 'upgrade' or 'downgrade') (default upgrade).
        :return: True if migration was run successfully, otherwise False.
        :type: bool
        """
        try:
            migration = self.find_migration(migration)
        except ValueError as exc:
            print('ERROR:', exc)
            return False

        try:
            print('INFO:', '{}: {}'.format(migration, direction))
            with self.database.transaction():
                scope = {}
                with self.open_migration(migration, 'r') as handle:
                    exec(handle.read(), scope)

                method = scope.get(direction, lambda migrator: None)
                method(self.migrator)

                if direction == 'upgrade':
                    MigrationHistory.create(name=migration)
                if direction == 'downgrade':
                    instance = MigrationHistory.get(MigrationHistory.name == migration)
                    instance.delete_instance()
        except Exception as exc:
            self.database.rollback()
            print('ERROR:', exc)
            return False

        return True

    def revision(self, name=None):
        """
        Create a single blank migration file with given name or default of 'automigration'.

        :param name: Name of migration to create (default automigration).
        :return: True if migration file was created, otherwise False.
        :type: bool
        """
        try:
            if name is None:
                name = 'automigration'
            name = str(name).lower()
            migration = self.next_migration(name)
            with self.open_migration(migration, 'w') as handle:
                handle.write(TEMPLATE.format(
                    name=name,
                    date=datetime.utcnow(),
                    upgrade='pass',
                    downgrade='pass'))
        except Exception as exc:
            print('ERROR:', exc)
            return False

        print('INFO:', '{}: created'.format(migration))
        return True

    def create(self, modelstr):
        """
        Create a new migration file for an existing model.
        Model could actually also be a module, in which case all Peewee models are extracted
        from the model and created.

        :param modelstr: Python class, module, or string pointing to a class or module.
        :return: True if migration file was created, otherwise False.
        :type: bool
        """
        model = modelstr
        if isinstance(modelstr, str):
            model = pydoc.locate(modelstr)
            if not model:
                print('INFO:', 'could not import: {}'.format(modelstr))
                return False

        # If it's a module, we need to loop through all the models in it.
        if inspect.ismodule(model):
            print('model was module')
            model_list = []
            for item in model.__dict__.values():
                if inspect.isclass(item) and issubclass(item, peewee.Model):
                    if getattr(item, '__abstract__', False):
                        continue
                    model_list.append(item)
            for model in peewee.sort_models_topologically(model_list):
                self.create(model)
            return True

        try:
            name = 'create table {}'.format(model._meta.db_table.lower())
            migration = self.next_migration(name)

            upgrade_ops = str.join('\n', build_upgrade_from_model(model))
            downgrade_ops = str.join('\n', build_downgrade_from_model(model))

            with self.open_migration(migration, 'w') as handle:
                handle.write(TEMPLATE.format(
                    name=name,
                    date=datetime.utcnow(),
                    upgrade=upgrade_ops,
                    downgrade=downgrade_ops))
        except Exception as exc:
            print('ERROR:', exc)
            return False

        print('INFO:', '{}: created'.format(migration))
        return True


class TableCreator:
    def __init__(self, name):
        """
        Initialize a new TableCreator instance.

        :param name: Name of database table.
        """
        self.name = name
        self.model = TableCreator.build_fake_model(self.name)

        # Dynamically add a method for all of the field types.
        for fieldname, fieldtype in FIELD_TO_PEEWEE.items():
            def method(name, **kwargs):
                self.column(fieldtype, name, **kwargs)
            setattr(self, fieldname, method)

    @staticmethod
    def build_fake_model(name):
        """
        Build a fake model with some defaults and the given table name.
        We need this so we can perform operations that actually require a model class.

        :param name: Name of database table.
        :return: A new model class.
        :rtype: peewee.Model
        """
        class Meta:
            primary_key = False
            indexes = []
            constraints = []
            db_table = name
        return type('FakeModel', (peewee.Model,), {'Meta': Meta})

    def column(self, coltype, name, **kwargs):
        """
        Generic method to add a column of any type.

        :param coltype: Column type (from FIELD_TO_PEEWEE).
        :param name: Name of column.
        :param kwargs: Arguments for the given column type.
        """
        field_class = FIELD_TO_PEEWEE.get(coltype, peewee.CharField)
        field_class(**kwargs).add_to_class(self.model, name)

    def add_index(self, columns, unique=False):
        """
        Add an index to the model.

        :param columns: Columns (list or tuple).
        :param unique: True or False whether index should be unique (default False).
        """
        self.model._meta.indexes.append((columns, unique))

    def add_constraint(self, value):
        """
        Add a constraint to the model.

        :param name: String value of constraint.
        :return: None
        """
        self.model._meta.constraints.append(peewee.SQL(value))

    def primary_key(self, name):
        """
        Add a primary key to the model.
        This has some special cases, which is why it's not handled like all the other column types.

        :param name: Name of column.
        :return: None
        """
        pkfield = peewee.PrimaryKeyField(primary_key=True)
        self.model._meta.primary_key = pkfield
        self.model._meta.auto_increment = True
        pkfield.add_to_class(self.model, name)

    def foreign_key(self, name, references, **kwargs):
        """
        Add a foreign key to the model.
        This has some special cases, which is why it's not handled like all the other column types.

        :param name: Name of the foreign key.
        :param references: Table name in the format of "table.column" or just
            "table" (and id will be default column).
        :param kwargs: Additional kwargs to pass to the column instance.
            You can also provide "on_delete" and "on_update" to add constraints.
        :return: None
        """
        on_delete = kwargs.pop('on_delete', False)
        on_update = kwargs.pop('on_update', False)
        rel_table, rel_col = references, 'id'
        splitref = references.split('.', 1)
        if len(splitref) == 2:
            rel_table, rel_col = splitref

        const = 'FOREIGN KEY({}) REFERENCES {}({})'.format(name, rel_table, rel_col)
        if on_delete:
            const += ' ON DELETE {}'.format(on_delete)
        if on_update:
            const += ' ON UPDATE {}'.format(on_update)

        kwargs['index'] = True
        self.column('integer', name, **kwargs)
        self.add_constraint(const)


class Migrator:
    def __init__(self, database):
        """
        Initialize a new Migrator instance for the given database.

        :param database: Connection string, dict, or peewee.Database instance to use.
        :return:
        """
        self.database = database
        self.migrator = SchemaMigrator.from_database(self.database)

    @contextmanager
    def create_table(self, name, safe=False):
        """
        Context manager to create the given table.
        Yield a TableCreator instance on which you can perform operations and add columns.

        :param name: Name of table to created
        :param safe: If True, will be created with "IF NOT EXISTS" (default False).
        :return: generator
        :rtype: TableCreator
        """
        table = TableCreator(name)

        yield table

        self.database.create_table(table.model, safe=safe)

        for field in table.model._fields_to_index():
            self.database.create_index(table.model, [field], field.unique)

        if table.model._meta.indexes:
            for fields, unique in table.model._meta.indexes:
                self.database.create_index(table.model, fields, unique)

    def drop_table(self, name, safe=False, cascade=False):
        """
        Drop the table.

        :param name: Table name to drop.
        :param safe: If True, exception will be raised if table does not exist.
        :param cascade: If True, drop will be cascaded.
        :return: None
        """
        model = TableCreator.build_fake_model(name)
        self.database.drop_table(model, fail_silently=safe, cascade=cascade)

    def add_column(self, table, name, coltype, **kwargs):
        """
        Add the given column to the given table.

        :param table: Table name to add column to.
        :param name: Name of the column field to add.
        :param coltype: Column type (from FIELD_TO_PEEWEE).
        :param kwargs: Arguments for the given column type.
        :return: None
        """
        field_class = FIELD_TO_PEEWEE.get(coltype, peewee.CharField)
        self.migrator.add_column(table, name, field_class(**kwargs)).run()

    def drop_column(self, table, name, cascade=True):
        """
        Drop the column from the given table.

        :param table: Table name to drop column from.
        :param name: Name of the column field to drop.
        :param cascade: If True, drop will be cascaded.
        :return: None
        """
        self.migrator.drop_column(table, name, cascade=cascade).run()

    def rename_column(self, table, old_name, new_name):
        """
        Rename a column leaving everything else in tact.

        :param table: Table name to rename column from.
        :param old_name: Old column name.
        :param new_name: New column name.
        :return: None
        """
        self.migrator.rename_column(table, old_name, new_name).run()

    def rename_table(self, old_name, new_name):
        """
        Rename a table leaving everything else in tact.

        :param old_name: Old table name.
        :param new_name: New table name.
        :return: None
        """
        self.migrator.rename_table(old_name, new_name).run()

    def add_not_null(self, table, column):
        """
        Add a NOT NULL constraint to a column.

        :param table: Table name.
        :param column: Column name.
        :return: None
        """
        self.migrator.add_not_null(table, column).run()

    def drop_not_null(self, table, column):
        """
        Remove a NOT NULL constraint to a column.

        :param table: Table name.
        :param column: Column name.
        :return: None
        """
        self.migrator.drop_not_null(table, column).run()

    def add_index(self, table, columns, unique=False):
        """
        Add an index to a table based on columns.

        :param table: Table name.
        :param columns: Columns (list or tuple).
        :param unique: True or False whether index should be unique (default False).
        :return: None
        """
        self.migrator.add_index(table, columns, unique=unique).run()

    def drop_index(self, table, index_name):
        """
        Remove an index from a table.

        :param table: Table name.
        :param index_name: Index name.
        :return: None
        """
        self.migrator.drop_index(table, index_name).run()

    def execute_sql(self, sql, params=None):
        """
        Run the given sql and return a cursor.

        :param sql: SQL string.
        :param params: Parameters for the given SQL (deafult None).
        :return: SQL cursor
        :rtype: cursor
        """
        return self.database.execute_sql(sql, params=params, require_commit=False)
