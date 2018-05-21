import sys
import inspect
import logging
import os
import pydoc
from contextlib import contextmanager
from datetime import datetime

import peewee
from playhouse.db_url import connect as url_connect
from playhouse.migrate import SchemaMigrator

__version__ = '1.7.3'

__all__ = ['DatabaseManager', 'MigrationHistory', 'Migrator', 'SchemaMigrator', 'TableCreator']


try:
    import click
    from flask import cli
    from flask import current_app
    FLASK_CLI_ENABLED = True
except ImportError:
    FLASK_CLI_ENABLED = False

LOG_HANDLER = logging.StreamHandler()
LOG_HANDLER.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

LOGGER = logging.getLogger('peewee_moves')
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(LOG_HANDLER)

PEEWEE_TO_FIELD = {
    peewee.BareField: 'bare',
    peewee.BigIntegerField: 'biginteger',
    peewee.BlobField: 'blob',
    peewee.BooleanField: 'bool',
    peewee.CharField: 'char',
    peewee.DateField: 'date',
    peewee.DateTimeField: 'datetime',
    peewee.DecimalField: 'decimal',
    peewee.DoubleField: 'double',
    peewee.FixedCharField: 'fixed',
    peewee.FloatField: 'float',
    peewee.ForeignKeyField: 'foreign_key',
    peewee.IntegerField: 'int',
    peewee.PrimaryKeyField: 'primary_key',
    peewee.SmallIntegerField: 'smallint',
    peewee.TextField: 'text',
    peewee.TimeField: 'time',
    peewee.TimestampField: 'int',
    peewee.UUIDField: 'uuid',
}

FIELD_TO_PEEWEE = {value: key for key, value in PEEWEE_TO_FIELD.items()}
FIELD_TO_PEEWEE['integer'] = peewee.IntegerField
FIELD_TO_PEEWEE['smallinteger'] = peewee.SmallIntegerField
FIELD_TO_PEEWEE['binary'] = peewee.BlobField

FIELD_KWARGS = ('null', 'index', 'unique', 'sequence', 'max_length', 'max_digits', 'decimal_places')

TEMPLATE = ''.join((
    '"""\n{name}\ndate created: {date}\n"""\n\n\n',
    'def upgrade(migrator):\n{upgrade}\n\n\n',
    'def downgrade(migrator):\n{downgrade}\n'
))


def build_downgrade_from_model(model):
    """
    Build a list of 'downgrade' operations for a model class.
    Each value that is yieled is one line to write to a file.

    :param model: Peewee model class or instance.
    :return: generator
    :rtype: str
    """
    yield "migrator.drop_table('{}')".format(model._meta.db_table)


def build_upgrade_from_model(model):
    """
    Build a list of 'upgrade' operations for a model class.
    Each value that is yieled is one line to write to a file.

    :param model: Peewee model class or instance.
    :return: generator
    :rtype: str
    """
    yield "with migrator.create_table('{}') as table:".format(model._meta.db_table)

    for field in model._meta.sorted_fields:
        field_type = PEEWEE_TO_FIELD.get(field.__class__, 'char')
        args = []

        # Add all fields. Foreign Key is a special case.
        if field_type == 'foreign_key':
            other_table = field.rel_model._meta.db_table
            other_col = field.to_field.db_column
            kwargs = {
                'references': '{}.{}'.format(other_table, other_col),
                'on_delete': field.on_delete,
                'on_update': field.on_update,
            }
            coltype = 'int' if field.to_field.db_field == 'primary_key' else field.to_field.db_field
            args.append(coltype)

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

        # Flatten the arg list for the field.
        argstr = ', '.join("'{}'".format(x) for x in map(str, args))
        if argstr:
            argstr = '{}, '.format(argstr)

        # Flatten the keyword arguments for the field.
        kwarg_list = ["'{}'".format(field.db_column)]
        for key, value in sorted(kwargs.items()):
            if isinstance(value, str):
                value = "'{}'".format(value)
            kwarg_list.append('{}={}'.format(key, value))

        # Then yield the field!
        yield "    table.{}({}{})".format(field_type, argstr, str.join(', ', kwarg_list))

    # Loop through all table constraints and yield them!
    constraints = getattr(model._meta, 'constraints', [])
    if constraints:
        for const in constraints:
            value = const
            if isinstance(const, peewee.SQL):
                value = const.value
            yield "    table.add_constraint('{}')".format(value)

    # Loop through all table indexes and yield them!
    indexes = getattr(model._meta, 'indexes', [])
    if indexes:
        for columns, unique in indexes:
            index_cols = []
            for colname in columns:
                model_field = model._meta.fields.get(colname)
                index_cols.append(model_field and model_field.db_column or colname)
            yield "    table.add_index({}, unique={})".format(tuple(index_cols), unique)


class MigrationHistory(peewee.Model):
    """
    Base model to manage migration history in a database.
    You can use this manually to query the database if you want, but normally it's handled
    by the DatabaseManager class.
    """
    name = peewee.CharField(unique=True)
    date_applied = peewee.DateTimeField(default=datetime.utcnow)

    class Meta:
        database = peewee.Proxy()
        db_table = 'migration_history'


class TableCreator:
    """
    A class used for creating a table in a migration file.

    :param name: Name of database table.
    """

    def __init__(self, name):
        self.name = name
        self.model = self.build_fake_model(self.name)

    def bare(self, name, **kwargs):
        """Create a bare column. Alias for ``table.column('bare')``"""
        return self.column('bare', name, **kwargs)

    def biginteger(self, name, **kwargs):
        """Create a biginteger column. Alias for ``table.column('biginteger')``"""
        return self.column('biginteger', name, **kwargs)

    def binary(self, name, **kwargs):
        """Create a binary column. Alias for ``table.column('binary')``"""
        return self.column('binary', name, **kwargs)

    def blob(self, name, **kwargs):
        """Create a blob column. Alias for ``table.column('blob')``"""
        return self.column('blob', name, **kwargs)

    def bool(self, name, **kwargs):
        """Create a bool column. Alias for ``table.column('bool')``"""
        return self.column('bool', name, **kwargs)

    def char(self, name, **kwargs):
        """Create a char column. Alias for ``table.column('char')``"""
        return self.column('char', name, **kwargs)

    def date(self, name, **kwargs):
        """Create a date column. Alias for ``table.column('date')``"""
        return self.column('date', name, **kwargs)

    def datetime(self, name, **kwargs):
        """Create a datetime column. Alias for ``table.column('datetime')``"""
        return self.column('datetime', name, **kwargs)

    def decimal(self, name, **kwargs):
        """Create a decimal column. Alias for ``table.column('decimal')``"""
        return self.column('decimal', name, **kwargs)

    def double(self, name, **kwargs):
        """Create a double column. Alias for ``table.column('double')``"""
        return self.column('double', name, **kwargs)

    def fixed(self, name, **kwargs):
        """Create a fixed column. Alias for ``table.column('fixed')``"""
        return self.column('fixed', name, **kwargs)

    def float(self, name, **kwargs):
        """Create a float column. Alias for ``table.column('float')``"""
        return self.column('float', name, **kwargs)

    def int(self, name, **kwargs):
        """Create a int column. Alias for ``table.column('int')``"""
        return self.column('int', name, **kwargs)

    def integer(self, name, **kwargs):
        """Create a integer column. Alias for ``table.column('integer')``"""
        return self.column('int', name, **kwargs)

    def smallint(self, name, **kwargs):
        """Create a smallint column. Alias for ``table.column('smallint')``"""
        return self.column('smallint', name, **kwargs)

    def smallinteger(self, name, **kwargs):
        """Create a smallinteger column. Alias for ``table.column('smallinteger')``"""
        return self.column('smallinteger', name, **kwargs)

    def text(self, name, **kwargs):
        """Create a text column. Alias for ``table.column('text')``"""
        return self.column('text', name, **kwargs)

    def time(self, name, **kwargs):
        """Create a time column. Alias for ``table.column('time')``"""
        return self.column('time', name, **kwargs)

    def uuid(self, name, **kwargs):
        """Create a uuid column. Alias for ``table.column('uuid')``"""
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
        new_constraints = []
        for const in constraints:
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

    def foreign_key(self, coltype, name, references, **kwargs):
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
        try:
            rel_table, rel_column = references.split('.', 1)
        except ValueError:
            rel_table, rel_column = references, 'id'

        # Create a dummy model that we can relate this field to.
        # Add the foreign key as a local field on the dummy model.
        # We only do this so that Peewee can generate the nice foreign key constraint for us.

        class DummyRelated(peewee.Model):
            class Meta:
                primary_key = False
                database = peewee.Proxy()
                db_table = rel_table

        rel_field_class = FIELD_TO_PEEWEE.get(coltype, peewee.IntegerField)
        rel_field = rel_field_class()
        rel_field.add_to_class(DummyRelated, rel_column)

        field = peewee.ForeignKeyField(DummyRelated, db_column=name, to_field=rel_column, **kwargs)
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
    """
    A migrator is a class that runs migrations for a specific upgrade or downgrade operation.

    An instance of this class is automatically created and passed as the only argument to
    ``upgrade(migrator)`` and ``downgrade(migrator)`` methods in migration files.

    :param database: Connection string, dict, or peewee.Database instance to use.
    """

    def __init__(self, database):
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
        Drop the given table.

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
    """
    A DatabaseManager is a class responsible for managing and running all migrations
    against a specific database with a set of migration files.

    :param database: Connection string, dict, or peewee.Database instance to use.
    :param table_name: Table name to hold migrations (default migration_history).
    :param directory: Directory to store migrations (default migrations).
    """

    ext = '.py'

    def __init__(self, database, table_name=None, directory='migrations'):
        self.directory = str(directory)
        self.database = self.load_database(database)
        self.migrator = Migrator(self.database)

        os.makedirs(self.directory, exist_ok=True)

        MigrationHistory._meta.db_table = table_name or 'migration_history'
        MigrationHistory._meta.database.initialize(self.database)
        MigrationHistory.create_table(fail_silently=True)

    def load_database(self, database):
        """
        Load the given database, whatever it might be.

        A connection string: ``sqlite:///database.sqlite``

        A dictionary: ``{'engine': 'SqliteDatabase', 'name': 'database.sqlite'}``

        A peewee.Database instance: ``peewee.SqliteDatabase('database.sqlite')``

        :param database: Connection string, dict, or peewee.Database instance to use.
        :raises: peewee.DatabaseError if database connection cannot be established.
        :return: Database connection.
        :rtype: peewee.Database instance.
        """
        # It could be an actual instance...
        if isinstance(database, (peewee.Proxy, peewee.Database)):
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
        :rtype: tuple
        """
        files = (f[:-len(self.ext)] for f in os.listdir(self.directory) if f.endswith(self.ext))
        return tuple(sorted(files))

    @property
    def db_migrations(self):
        """
        List all the migrations applied to the database.

        :return: List of migration names.
        :rtype: tuple
        """
        return tuple(sorted(row.name for row in MigrationHistory.select()))

    @property
    def diff(self):
        """
        List all the migrations that have not been applied to the database.

        :return: List of migration names.
        :rtype: tuple
        """
        return tuple(sorted(set(self.migration_files) - set(self.db_migrations)))

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
        Return a unique identifier for a revision.
        This defaults to the current next incremental identifier.
        Override this method to change functionality.
        Make sure the IDs will be sortable (like timestamps or incremental numbers).

        :return: Name of new migration.
        :rtype: str
        """
        # return str(round(time.time()))
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
        kwargs = self.database.connect_kwargs
        LOGGER.info('driver: {}'.format(driver))
        LOGGER.info('database: {}'.format(database))
        LOGGER.info('arguments:')
        for key, value in kwargs.items():
            LOGGER.info('  {}: {}'.format(key, value))

    def status(self):
        """
        Show all the migrations and a status for each.

        :return: True if listing was successful, otherwise None.
        :rtype: bool
        """
        if not self.migration_files:
            LOGGER.info('no migrations found')
            return
        for name in self.migration_files:
            status = 'x' if name in self.db_migrations else ' '
            LOGGER.info('[{}] {}'.format(status, name))

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
            LOGGER.error(exc)
            return False

        LOGGER.info('deleted: {}'.format(migration))
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
                    LOGGER.info('already applied: {}'.format(target))
                    return False
        except ValueError as exc:
            LOGGER.error(exc)
            return False

        if not self.diff:
            LOGGER.info('all migrations applied!')
            return True

        for name in self.diff:
            success = self.run_migration(name, 'upgrade')
            # If it didn't work, don't try any more and exit.
            if not success:
                return False
            # Or if we are at the end of the line, don't run anymore.
            if target and target == name:
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
                    LOGGER.info('not yet applied: {}'.format(target))
                    return False
        except ValueError as exc:
            LOGGER.error(exc)
            return False

        diff = self.db_migrations[::-1]

        if not diff:
            LOGGER.info('migrations not yet applied!')
            return False

        for name in diff:
            success = self.run_migration(name, 'downgrade')
            # If it didn't work, don't try any more.
            if not success:
                return False
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
            LOGGER.error(exc)
            return False

        try:
            LOGGER.info('{}: {}'.format(direction, migration))
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
            LOGGER.error(exc)
            return False

        return True

    def revision(self, name=None):
        """
        Create a single blank migration file with given name or default of 'auto migration'.

        :param name: Name of migration to create (default auto migration).
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
            LOGGER.error(exc)
            return False

        LOGGER.info('created: {}'.format(migration))
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
                LOGGER.info('could not import: {}'.format(modelstr))
                return False

        # If it's a module, we need to loop through all the models in it.
        if inspect.ismodule(model):
            model_list = []
            for item in model.__dict__.values():
                if inspect.isclass(item) and issubclass(item, peewee.Model):
                    # Don't create migration file for imported models.
                    if model.__name__ != item.__module__:
                        continue
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
            LOGGER.error(exc)
            return False

        LOGGER.info('created: {}'.format(migration))
        return True


@click.group()
@click.option('--directory', required=True)
@click.option('--database', required=True)
@click.option('--table')
@click.pass_context
def cli_command(ctx, directory, database, table=None):
    """Run database migration commands."""
    class ScriptInfo:
        def __init__(self):
            self.data = {'manager': None}

    ctx.obj = ctx.obj or ScriptInfo()
    ctx.obj.data['manager'] = DatabaseManager(database, table_name=table, directory=directory)


@cli_command.command('info')
@click.pass_context
def cli_info(ctx):
    """Show information about the current database."""
    ctx.obj.data['manager'].info()


@cli_command.command('status')
@click.pass_context
def cli_status(ctx):
    """Show information about migration status."""
    ctx.obj.data['manager'].status()


@cli_command.command('create')
@click.argument('model')
@click.pass_context
def cli_create(ctx, model):
    """Create a migration based on an existing model."""
    if not ctx.obj.data['manager'].create(model):
        sys.exit(1)


@cli_command.command('revision')
@click.argument('name')
@click.pass_context
def cli_revision(ctx, name):
    """Create a blank migration file."""
    if not ctx.obj.data['manager'].revision(name):
        sys.exit(1)


@cli_command.command('upgrade')
@click.argument('target', default='')
@click.pass_context
def cli_upgrade(ctx, target):
    """Run database upgrades."""
    if not ctx.obj.data['manager'].upgrade(target):
        sys.exit(1)


@cli_command.command('downgrade')
@click.argument('target', default='')
@click.pass_context
def cli_downgrade(ctx, target):
    """Run database downgrades."""
    if not ctx.obj.data['manager'].downgrade(target):
        sys.exit(1)


@cli_command.command('delete')
@click.argument('target', default='')
@click.pass_context
def cli_delete(ctx, target):
    """Delete the target migration from the filesystem and database."""
    if not ctx.obj.data['manager'].delete(target):
        sys.exit(1)


if FLASK_CLI_ENABLED:

    def get_flask_database_manager(app, table=None):
        """Get a database manager for the given Flask application."""
        directory = os.path.join(app.root_path, 'migrations')
        database = app.config['DATABASE']
        return DatabaseManager(database, table_name=table, directory=directory)

    @click.group()
    @click.option('--table')
    @click.pass_context
    @cli.with_appcontext
    def flask_command(ctx, table=None):
        """Run database migration commands for a Flask application."""
        ctx.obj.data['manager'] = get_flask_database_manager(current_app, table=None)

    flask_command.add_command(cli_info)
    flask_command.add_command(cli_status)
    flask_command.add_command(cli_create)
    flask_command.add_command(cli_revision)
    flask_command.add_command(cli_upgrade)
    flask_command.add_command(cli_downgrade)
    flask_command.add_command(cli_delete)
