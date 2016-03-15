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
    FLASK_SCRIPT = True
    from flask import current_app
    from flask_script import Manager
except ImportError:
    FLASK_SCRIPT = False

__all__ = ['migration_manager', 'MigrationHistory', 'DatabaseManager', 'TableCreator', 'Migrator']

FIELD_TO_PEEWEE = {
    'bare': peewee.BareField,
    'biginteger': peewee.BigIntegerField,
    'binary': peewee.BinaryField,
    'blob': peewee.BlobField,
    'bool': peewee.BooleanField,
    'date': peewee.DateField,
    'datetime': peewee.DateTimeField,
    'decimal': peewee.DecimalField,
    'double': peewee.DoubleField,
    'fixed': peewee.FixedCharField,
    'float': peewee.FloatField,
    'integer': peewee.IntegerField,
    'string': peewee.CharField,
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

TEMPLATE = """
def upgrade(migrator):
    {upgrade}


def downgrade(migrator):
    {downgrade}
""".lstrip()


if FLASK_SCRIPT:

    migration_manager = Manager(usage='{} db [command]'.format(sys.argv[0]))

    def get_database_manager():
        """Return a DatabaseManager for the current Flask application."""
        return DatabaseManager(current_app.config['DATABASE'], directory='app/migrations')

    @migration_manager.option('-m', '--model', dest='model', required=True)
    def create(model):
        """Create a migration based on an existing model."""
        get_database_manager().create(model)

    @migration_manager.option('-n', '--name', dest='name', required=False)
    def revision(name):
        """Create a blank migration file."""
        get_database_manager().revision(name)

    @migration_manager.command
    def status():
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

    @migration_manager.option('-t', '--target', dest='target', required=False)
    def delete(target):
        """Delete the target migration from the filesystem and database."""
        get_database_manager().delete(target)


def build_fake_model(name):
    """
    Build a fake model with some defaults and the given table name.
    We need this so we can perform operations that actually require a model class.
    """
    class Meta:
        primary_key = False
        indexes = []
        constraints = []
        db_table = name
    return type('FakeModel', (peewee.Model,), {'Meta': Meta})


def build_downgrade_from_model(model):
    """Build a list of 'downgrade' operations for a model class."""
    yield "migrator.drop_table('{}')".format(model._meta.db_table)


def build_upgrade_from_model(model):
    """Build a list of 'upgrade' operations for a model class."""
    yield "with migrator.create_table('{}') as table:".format(model._meta.db_table)

    for field in model._meta.sorted_fields:
        coltype = PEEWEE_TO_FIELD.get(field.__class__, 'string')

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
        for key, value in kwargs.items():
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
        self.directory = directory
        os.makedirs(self.directory, exist_ok=True)
        self.database = self.load_database(database)
        self.migrator = Migrator(self.database)
        self.compiler = self.database.compiler()

        MigrationHistory._meta.database = self.database
        MigrationHistory._meta.db_table = table_name
        MigrationHistory.create_table(fail_silently=True)

    def load_database(self, database):
        """Load the given database, whatever it might be."""
        if isinstance(database, peewee.Database):
            return database

        if isinstance(database, dict):
            try:
                name = database.pop('name')
                engine = database.pop('engine')
            except KeyError:
                raise KeyError('Configuration dict must specify "name" and "engine" keys.')

            db_class = pydoc.locate(engine)
            if not db_class:
                raise ImportError('Unable to import engine class: {}'.format(engine))
            return db_class(name, **database)

        return db_url_connect(database)

    @property
    def migration_files(self):
        """List all the migrations sitting on the filesystem."""
        files = (f[:-len('.py')] for f in os.listdir(self.directory) if f.endswith('.py'))
        return sorted(files)

    @property
    def db_migrations(self):
        """List all the migrations applied to the database."""
        return sorted(row.name for row in MigrationHistory.select())

    @property
    def diff(self):
        """List all the migrations that have not been applied to the database."""
        return sorted(set(self.migration_files) - set(self.db_migrations))

    def find_migration(self, value):
        """Try to find a migration by name or start of name."""
        for name in self.migration_files:
            if name == value:
                return name
            if name.startswith('{}_'.format(value)):
                return name
        raise ValueError('could not find migration: {}'.format(value))

    def get_ident(self):
        """
        Return a unique identifier for a revision. Override this method to change functionality.
        Make sure the IDs will be sortable (like timestamps or incremental numbers)
        """
        next_id = 1
        if self.migration_files:
            next_id = int(list(self.migration_files)[-1].split('_')[0]) + 1
        return '{:04}'.format(next_id)

    def next_migration(self, name):
        """Get the name of the next migration that should be created."""
        return '{}_{}'.format(self.get_ident(), name.replace(' ', '_'))

    def get_filename(self, migration):
        """Return the filename for the given migation."""
        return os.path.join(self.directory, '{}.py'.format(migration))

    def open_migration(self, migration, mode='r'):
        """Open a migration file with the given mode and return it."""
        return open(self.get_filename(migration), mode)

    def delete(self, migration):
        """Delete the migration from filesystem and database. As if it never happened."""
        try:
            migration = self.find_migration(migration)
            try:
                os.remove(self.get_filename(migration))
            except OSError:
                pass
            with self.database.transaction():
                cmd = MigrationHistory.delete().where(MigrationHistory.name == migration)
                cmd.execute()
        except Exception as exc:
            self.database.rollback()
            print('DELETE-ERROR:', exc)
            return False

        print('{}: delete'.format(migration))
        return True

    def status(self):
        """Show all the migrations and a status for each."""
        if not self.migration_files:
            print('no migrations found')
            return True
        for name in self.migration_files:
            status = 'applied' if name in self.db_migrations else 'pending'
            print('{}: {}'.format(name, status))
        return True

    def upgrade(self, target=None):
        """Run all the migrations (up to target if specified). If no target, run all upgrades."""
        try:
            if target:
                target = self.find_migration(target)
                if target in self.db_migrations:
                    print('{}: already applied'.format(target))
                    return False
        except ValueError as exc:
            print('UPGRADE-ERROR:', exc)
            return False

        if self.diff:
            for name in self.diff:
                rv = self.run_migration(name, 'upgrade')
                # If it didn't work, don't try any more.
                # Or if we are at the end of the line, don't run anymore.
                if not rv or (target and target == name):
                    break
            return True

        print('all migrations applied!')
        return True

    def downgrade(self, target=None):
        """Run all the migrations (down to target if specified). If no target, run one downgrade."""
        try:
            if target:
                target = self.find_migration(target)
                if target not in self.db_migrations:
                    print('{}: not yet applied'.format(target))
                    return False
        except ValueError as exc:
            print('UPGRADE-ERROR:', exc)
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

        print('migrations not yet applied!')
        return True

    def run_migration(self, migration, direction='upgrade'):
        """Run a single migration."""
        try:
            migration = self.find_migration(migration)

            if direction == 'upgrade' and migration in self.db_migrations:
                print('{}: already applied'.format(migration))
                return False

            if direction == 'downgrade' and migration not in self.db_migrations:
                print('{}: not yet applied'.format(migration))
                return False

        except ValueError as exc:
            print('RUN-ERROR:', exc)
            return False

        try:
            print('{}: {}'.format(migration, direction))
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
            print('RUN-ERROR:', exc)
            return False

        return True

    def revision(self, name=None):
        """Create a single blank migration file with given name or default of 'automigration'."""
        try:
            if name is None:
                name = 'automigration'
            migration = self.next_migration(name)
            print('created migration {}'.format(migration))

            with self.open_migration(migration, 'w') as handle:
                handle.write(TEMPLATE.format(upgrade='pass', downgrade='pass'))
        except Exception as exc:
            print('REVISION-ERROR:', exc)
            return False

        return True

    def create(self, model):
        """
        Create a new migration file for an existing model.
        Model could actually also be a module, in which case all Peewee models are extracted
        from the model and created.
        """
        if isinstance(model, str):
            model = pydoc.locate(model)
            if not model:
                print('could not import: {}'.format(model))
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
            name = 'create_table_{}'.format(model._meta.db_table.lower())
            migration = self.next_migration(name)

            upgrade_ops = str.join('\n', build_upgrade_from_model(model))
            downgrade_ops = str.join('\n', build_downgrade_from_model(model))

            with self.open_migration(migration, 'w') as handle:
                handle.write(TEMPLATE.format(upgrade=upgrade_ops, downgrade=downgrade_ops))
        except Exception as exc:
            print('CREATE-ERROR:', exc)
            return False

        print('created migration {}'.format(migration))
        return True


class TableCreator:
    def __init__(self, name):
        self.name = name
        self.model = build_fake_model(self.name)

        # Dynamically add a method for all of the field types.
        for fieldname, fieldtype in FIELD_TO_PEEWEE.items():
            def method(name, **kwargs):
                self.column(fieldtype, name, **kwargs)
            setattr(self, fieldname, method)

    def column(self, coltype, name, **kwargs):
        """Generic method to add a column of any type."""
        field_class = FIELD_TO_PEEWEE.get(coltype, peewee.CharField)
        field_class(**kwargs).add_to_class(self.model, name)

    def add_index(self, columns, unique=False):
        """Add an index to the model."""
        self.model._meta.indexes.append((columns, unique))

    def add_constraint(self, value):
        """Add a constraint to the model."""
        self.model._meta.constraints.append(peewee.SQL(value))

    def primary_key(self, name):
        """
        Add a primary key to the model.
        This has some special cases, which is why it's not handled like all the other column types.
        """
        pkfield = peewee.PrimaryKeyField(primary_key=True)
        self.model._meta.primary_key = pkfield
        self.model._meta.auto_increment = True
        pkfield.add_to_class(self.model, name)

    def foreign_key(self, name, references, **kwargs):
        """
        Add a foreign key to the model.
        This has some special cases, which is why it's not handled like all the other column types.
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

        self.column('integer', name, **kwargs)
        self.add_constraint(const)


class Migrator:
    def __init__(self, database):
        self.database = database
        self.migrator = SchemaMigrator.from_database(self.database)

    @contextmanager
    def create_table(self, name, safe=False):
        table = TableCreator(name)
        yield table
        self.database.create_table(table.model, safe=safe)

    def drop_table(self, name, safe=False, cascade=False):
        model = build_fake_model(name)
        self.database.drop_table(model, fail_silently=safe, cascade=cascade)

    def add_column(self, table, name, coltype, **kwargs):
        field_class = FIELD_TO_PEEWEE.get(coltype, peewee.CharField)
        self.migrator.add_column(table, name, field_class(**kwargs)).run()

    def drop_column(self, table, name, field, cascade=True):
        self.migrator.drop_column(table, name, field, cascade=cascade).run()

    def rename_column(self, table, old_name, new_name):
        self.migrator.rename_column(table, old_name, new_name).run()

    def rename_table(self, old_name, new_name):
        self.migrator.rename_table(old_name, new_name).run()

    def add_not_null(self, table, column):
        self.migrator.add_not_null(table, column).run()

    def drop_not_null(self, table, column):
        self.migrator.drop_not_null(table, column).run()

    def add_index(self, table, columns, unique=False):
        self.migrator.add_index(table, columns, unique=unique).run()

    def drop_index(self, table, index_name):
        self.migrator.drop_index(table, index_name).run()

    def execute_sql(self, sql, params=None):
        return self.database.execute_sql(sql, params=params, require_commit=False)
