from contextlib import contextmanager
from datetime import datetime
import inspect
import os
import pydoc

from playhouse.db_url import connect as url_connect
from playhouse.migrate import SchemaMigrator
import peewee

try:
    import click
    from flask import cli
    from flask import current_app
    EXTENSION_CLICK = True
except ImportError:
    EXTENSION_CLICK = False


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
    'int': peewee.IntegerField,
    'integer': peewee.IntegerField,
    'smallint': peewee.SmallIntegerField,
    'smallinteger': peewee.SmallIntegerField,
    'text': peewee.TextField,
    'time': peewee.TimeField,
    'uuid': peewee.UUIDField,
}

PEEWEE_TO_FIELD = {value: key for key, value in FIELD_TO_PEEWEE.items()}
PEEWEE_TO_FIELD[peewee.PrimaryKeyField] = 'primary_key'
PEEWEE_TO_FIELD[peewee.ForeignKeyField] = 'foreign_key'
PEEWEE_TO_FIELD[peewee.TimestampField] = 'int'

FIELD_KWARGS = ('null', 'index', 'unique', 'sequence', 'max_length', 'max_digits', 'decimal_places')

TEMPLATE = ''.join((
    '"""\n{name}\ndate created: {date}\n"""\n\n\n',
    'def upgrade(migrator):\n{upgrade}\n\n\n',
    'def downgrade(migrator):\n{downgrade}\n'
))


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
        field_type = PEEWEE_TO_FIELD.get(field.__class__, 'char')

        # Add all fields. Foreign Key is a special case.
        if field_type == 'foreign_key':
            other_table = field.rel_model._meta.db_table
            other_col = field.to_field.db_column
            kwargs = {'references': '{}.{}'.format(other_table, other_col)}
        else:
            kwargs = {
                key: getattr(field, key) for key in FIELD_KWARGS if getattr(field, key, None)
            }

            # Check for constraints which is a special case
            field_constraints = getattr(field, 'constraints', ())
            if field_constraints:
                constraints = []
                for const in field_constraints:
                    value = const
                    if isinstance(const, peewee.SQL):
                        value = const.value
                    constraints.append(value)
                kwargs['constraints'] = constraints

        # Flatten the keyword arguments for the field.
        args_list = ["'{}'".format(field.db_column)]
        for key, value in sorted(kwargs.items()):
            if isinstance(value, str):
                value = "'{}'".format(value)
            args_list.append('{}={}'.format(key, value))

        # Then yield the field!
        yield "    table.{}({})".format(field_type, str.join(', ', args_list))

    # Loop through all constraints and yield them!
    constraints = getattr(model._meta, 'constraints', [])
    if constraints:
        for const in constraints:
            value = const
            if isinstance(const, peewee.SQL):
                value = const.value
            yield "    table.add_constraint('{}')".format(value)

    # Loop through all indexes and yield them!
    indexes = getattr(model._meta, 'indexes', [])
    if indexes:
        for columns, unique in indexes:
            yield "    table.add_index({}, unique={})".format(columns, unique)


class MigrationHistory(peewee.Model):
    """Base model to manage migration history in a database."""
    name = peewee.CharField(unique=True)
    date_applied = peewee.DateTimeField(default=datetime.utcnow)

    class Meta:
        database = peewee.Proxy()
        db_table = 'migration_history'


class TableCreator:
    def __init__(self, name):
        """
        Initialize a new TableCreator instance.

        :param name: Name of database table.
        """
        self.name = name
        self.model = self.build_fake_model(self.name)

    def bare(self, name, **kwargs):
        return self.column('bare', name, **kwargs)

    def biginteger(self, name, **kwargs):
        return self.column('biginteger', name, **kwargs)

    def binary(self, name, **kwargs):
        return self.column('binary', name, **kwargs)

    def blob(self, name, **kwargs):
        return self.column('blob', name, **kwargs)

    def bool(self, name, **kwargs):
        return self.column('bool', name, **kwargs)

    def char(self, name, **kwargs):
        return self.column('char', name, **kwargs)

    def date(self, name, **kwargs):
        return self.column('date', name, **kwargs)

    def datetime(self, name, **kwargs):
        return self.column('datetime', name, **kwargs)

    def decimal(self, name, **kwargs):
        return self.column('decimal', name, **kwargs)

    def double(self, name, **kwargs):
        return self.column('double', name, **kwargs)

    def fixed(self, name, **kwargs):
        return self.column('fixed', name, **kwargs)

    def float(self, name, **kwargs):
        return self.column('float', name, **kwargs)

    def int(self, name, **kwargs):
        return self.column('int', name, **kwargs)

    def integer(self, name, **kwargs):
        return self.column('int', name, **kwargs)

    def smallint(self, name, **kwargs):
        return self.column('smallint', name, **kwargs)

    def smallinteger(self, name, **kwargs):
        return self.column('smallinteger', name, **kwargs)

    def text(self, name, **kwargs):
        return self.column('text', name, **kwargs)

    def time(self, name, **kwargs):
        return self.column('time', name, **kwargs)

    def uuid(self, name, **kwargs):
        return self.column('uuid', name, **kwargs)

    def build_fake_model(self, name):
        """
        Build a fake model with some defaults and the given table name.
        We need this so we can perform operations that actually require a model class.

        :param name: Name of database table.
        :return: A new model class.
        :rtype: peewee.Model
        """
        class FakeModel(peewee.Model):
            class Meta:
                database = peewee.Proxy()
                primary_key = False
                indexes = []
                constraints = []
                db_table = name
        return FakeModel

    def column(self, coltype, name, **kwargs):
        """
        Generic method to add a column of any type.

        :param coltype: Column type (from FIELD_TO_PEEWEE).
        :param name: Name of column.
        :param kwargs: Arguments for the given column type.
        """
        constraints = kwargs.pop('constraints', [])
        for const in constraints:
            new_constraints = []
            if isinstance(const, str):
                const = peewee.SQL(const)
            new_constraints.append(const)
            kwargs['constraints'] = new_constraints

        field_class = FIELD_TO_PEEWEE.get(coltype, peewee.CharField)
        field_class(**kwargs).add_to_class(self.model, name)

    def primary_key(self, name):
        """
        Add a primary key to the model.
        This has some special cases, which is why it's not handled like all the other column types.

        :param name: Name of column.
        :return: None
        """
        pk_field = peewee.PrimaryKeyField(primary_key=True)
        self.model._meta.primary_key = pk_field
        self.model._meta.auto_increment = True
        pk_field.add_to_class(self.model, name)

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
        if name.endswith('_id'):
            name = name[:-3]

        try:
            rel_table, rel_column = references.split('.', 1)
        except ValueError:
            rel_table, rel_column = references, 'id'

        class DummyRelated(peewee.Model):
            class Meta:
                database = peewee.Proxy()
                db_table = rel_table

        field = peewee.ForeignKeyField(DummyRelated, to_field=rel_column, **kwargs)
        field.add_to_class(self.model, name)

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


class Migrator:
    def __init__(self, database):
        """
        Initialize a new Migrator instance for the given database.

        :param database: Connection string, dict, or peewee.Database instance to use.
        :return:
        """
        self.database = database
        self.migrator = SchemaMigrator.from_database(self.database)
        self.models = []

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
        creator = TableCreator(name)
        creator.model._meta.database.initialize(self.database)

        yield creator

        creator.model.create_table()

    def drop_table(self, name, safe=False, cascade=False):
        """
        Drop the table.

        :param name: Table name to drop.
        :param safe: If True, exception will be raised if table does not exist.
        :param cascade: If True, drop will be cascaded.
        :return: None
        """
        creator = TableCreator(name)
        creator.model._meta.database.initialize(self.database)
        self.database.drop_table(creator.model, fail_silently=safe, cascade=cascade)

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


class DatabaseManager:
    ext = '.py'

    def __init__(self, database, table_name='migration_history', directory='migrations', out=print):
        """
        Initialize a DatabaseManager with the given options.

        :param database: Connection string, dict, or peewee.Database instance to use.
        :param table_name: Table name to hold migrations (default migration_history).
        :param directory: Directory to store migrations (default migrations).
        """
        self.out = out
        self.directory = str(directory)
        self.database = self.load_database(database)
        self.migrator = Migrator(self.database)

        os.makedirs(self.directory, exist_ok=True)

        MigrationHistory._meta.db_table = table_name
        MigrationHistory._meta.database.initialize(self.database)
        MigrationHistory.create_table(fail_silently=True)

    def load_database(self, database):
        """
        Load the given database, whatever it might be.

        :param database: Connection string, dict, or peewee.Database instance to use.
        :raises: peewee.DatabaseError if database connection cannot be established.
        :return: Database connection.
        :rtype: peewee.Database instance.
        """
        # It could be an actual instance...
        if isinstance(database, peewee.Database):
            return database

        # It could be a dictionary...
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

        # Or it could be a database URL.
        return url_connect(database)

    @property
    def migration_files(self):
        """
        List all the migrations sitting on the filesystem.

        :return: List of migration names.
        :rtype: list
        """
        files = (f[:-len(self.ext)] for f in os.listdir(self.directory) if f.endswith(self.ext))
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
            if name == value or name.startswith('{}_'.format(value)):
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
        return os.path.join(self.directory, '{}{}'.format(migration, self.ext))

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

    def write_migration(self, migration, name, upgrade='pass', downgrade='pass'):
        """
        Open a migration file and write the given attributes to it.

        :param migration: Name of migration to find (not including extension).
        :name: Name to write in file header.
        :upgrade: Text for upgrade operations.
        :downgrade: Text for downgrade operations.
        :raises: IOError if the file cannot be opened.
        :return: None.
        """
        with self.open_migration(migration, 'w') as handle:
            if not isinstance(upgrade, str):
                upgrade = '\n    '.join(upgrade)
            if not isinstance(downgrade, str):
                downgrade = '\n    '.join(downgrade)
            handle.write(TEMPLATE.format(
                    name=name,
                    date=datetime.utcnow(),
                    upgrade='    ' + upgrade,
                    downgrade='    ' + downgrade))

    def info(self):
        """
        Show the current database.
        Don't include any sensitive information like passwords.

        :return: String representation.
        :rtype: str
        """
        driver = self.database.__class__.__name__
        database = self.database.database
        self.out('INFO:', 'driver =', driver)
        self.out('INFO:', 'database =', database)

    def status(self):
        """
        Show all the migrations and a status for each.

        :return: True if listing was successful, otherwise None.
        :rtype: bool
        """
        if not self.migration_files:
            self.out('INFO:', 'no migrations found')
            return
        for name in self.migration_files:
            status = 'applied' if name in self.db_migrations else 'pending'
            self.out('INFO:', '{}: {}'.format(name, status))

    def delete(self, migration):
        """
        Delete the migration from filesystem and database. As if it never happened.

        :param migration: Name of migration to find (not including extension).
        :return: True if delete was successful, otherwise False.
        :rtype: bool
        """
        try:
            migration = self.find_migration(migration)
            os.remove(self.get_filename(migration))
            with self.database.transaction():
                cmd = MigrationHistory.delete().where(MigrationHistory.name == migration)
                cmd.execute()
        except Exception as exc:
            self.database.rollback()
            self.out('ERROR:', exc)
            return False

        self.out('INFO:', '{}: delete'.format(migration))
        return True

    def upgrade(self, target=None):
        """
        Run all the migrations (up to target if specified). If no target, run all upgrades.

        :param target: Migration target to limit upgrades.
        :return: True if upgrade was successful, otherwise False.
        :rtype: bool
        """
        try:
            if target:
                target = self.find_migration(target)
                if target in self.db_migrations:
                    self.out('INFO:', '{}: already applied'.format(target))
                    return False
        except ValueError as exc:
            self.out('ERROR:', exc)
            return False

        if not self.diff:
            self.out('INFO:', 'all migrations applied!')
            return False

        for name in self.diff:
            success = self.run_migration(name, 'upgrade')
            # If it didn't work, don't try any more.
            # Or if we are at the end of the line, don't run anymore.
            if not success or (target and target == name):
                break
        return True

    def downgrade(self, target=None):
        """
        Run all the migrations (down to target if specified). If no target, run one downgrade.

        :param target: Migration target to limit downgrades.
        :return: True if downgrade was successful, otherwise False.
        :rtype: bool
        """
        try:
            if target:
                target = self.find_migration(target)
                if target not in self.db_migrations:
                    self.out('INFO:', '{}: not yet applied'.format(target))
                    return False
        except ValueError as exc:
            self.out('ERROR:', exc)
            return False

        diff = self.db_migrations[::-1]

        if not diff:
            self.out('INFO:', 'migrations not yet applied!')
            return False

        for name in diff:
            success = self.run_migration(name, 'downgrade')
            # If it didn't work, don't try any more.
            # Or if we are at the end of the line, don't run anymore.
            if not success or (not target or target == name):
                break
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
            self.out('ERROR:', exc)
            return False

        try:
            self.out('INFO:', '{}: {}'.format(migration, direction))
            with self.database.transaction():
                scope = {
                    '__file__': self.get_filename(migration),
                }
                with self.open_migration(migration, 'r') as handle:
                    exec(handle.read(), scope)

                method = scope.get(direction, None)
                if method:
                    method(self.migrator)

                if direction == 'upgrade':
                    MigrationHistory.create(name=migration)

                if direction == 'downgrade':
                    instance = MigrationHistory.get(MigrationHistory.name == migration)
                    instance.delete_instance()

        except Exception as exc:
            self.database.rollback()
            self.out('ERROR:', exc)
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
                name = 'auto migration'
            name = str(name).lower().strip()
            migration = self.next_migration(name)
            self.write_migration(migration, name=name)
        except Exception as exc:
            self.out('ERROR:', exc)
            return False

        self.out('INFO:', '{}: created'.format(migration))
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
                self.out('INFO:', 'could not import: {}'.format(modelstr))
                return False

        # If it's a module, we need to loop through all the models in it.
        if inspect.ismodule(model):
            model_list = []
            for item in model.__dict__.values():
                if inspect.isclass(item) and issubclass(item, peewee.Model):
                    model_list.append(item)
            for model in peewee.sort_models_topologically(model_list):
                self.create(model)
            return True

        try:
            name = 'create table {}'.format(model._meta.db_table.lower())
            migration = self.next_migration(name)
            up_ops = build_upgrade_from_model(model)
            down_ops = build_downgrade_from_model(model)
            self.write_migration(migration, name=name, upgrade=up_ops, downgrade=down_ops)
        except Exception as exc:
            self.out('ERROR:', exc)
            return False

        self.out('INFO:', '{}: created'.format(migration))
        return True


if EXTENSION_CLICK:

    def get_database_manager():
        """Return a DatabaseManager for the current Flask application."""
        directory = os.path.join(current_app.root_path, 'migrations')
        return DatabaseManager(current_app.config['DATABASE'], directory=directory)

    @click.group()
    def command():
        """Run Peewee migration commands."""

    @command.command()
    @click.argument('model')
    @cli.with_appcontext
    def create(model):
        """Create a migration based on an existing model."""
        get_database_manager().create(model)

    @command.command()
    @cli.with_appcontext
    def info():
        """Show information about the current database."""
        get_database_manager().info()

    @command.command()
    @cli.with_appcontext
    def status():
        """Show information about the database."""
        get_database_manager().status()

    @command.command()
    @click.argument('name')
    @cli.with_appcontext
    def revision(name):
        """Create a blank migration file."""
        get_database_manager().revision(name)

    @command.command()
    @click.argument('target', default='')
    @cli.with_appcontext
    def upgrade(target):
        """Run database upgrades."""
        get_database_manager().upgrade(target)

    @command.command()
    @click.argument('target', default='')
    @cli.with_appcontext
    def downgrade(target):
        """Run database downgrades."""
        get_database_manager().downgrade(target)

    @command.command()
    @click.argument('target', default='')
    @cli.with_appcontext
    def delete(target):
        """Delete the target migration from the filesystem and database."""
        get_database_manager().delete(target)
