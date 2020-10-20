Direct Usage
============

The main entry point is the `DatabaseManager` class which accepts the following parameters:

- database: location of database (URL string, dictionary, or ``peewee.Database`` instance).
- table_name: table name to store migration history (default: migration_history)
- directory: directory to store migration files (default: migrations)

.. code:: python

    from peewee import SqliteDatabase
    from peewee_moves import DatabaseManager

    manager = DatabaseManager(SqliteDatabase('test.sqlite'))
    manager = DatabaseManager({'engine': 'peewee.SqliteDatabase', 'name': 'test.sqlite'})
    manager = DatabaseManager('sqlite:///test.sqlite')

From there, you can call methods to manage and run migration files.

New Migration
-------------

This will create a blank migration file with the next ID and the default name of "auto migration"
or whatever name you provide

.. code:: console

    >>> manager.revision()
    created: INFO: 0001_auto_migration

    >>> manager.revision('custom name')
    created: INFO: 0002_custom_name

Database Upgrade
----------------

This will run the upgrade() method in each unapplied migration. If you specify a target, the
migrator will only run upgrades through that target. If no target is specified, all unapplied
migrations will run.

.. code:: console

    >>> manager.upgrade('0001')
    INFO: upgrade: 0001_auto_migration

    >>> manager.upgrade()
    INFO: upgrade: 0002_custom_name
    INFO: upgrade: 0003_another_migration

Pass the `--fake` flag to add the record to the migration history table but don't actually run the migration:

.. code:: console

    >>> manager.upgrade(fake=True)
    INFO: upgrade: 0003_another_migration

    >>> manager.upgrade('0001', fake=True)
    INFO: upgrade: 0002_custom_name
    INFO: upgrade: 0001_auto_migration

Database Downgrade
------------------

This does the opposite of upgrade(). It calls the downgrade() method on each applied migration. If
you specify a target, the migrator will only run downgrades through that target. If no target is
specified, only the most recent migration will be downgraded.

.. code:: console

    >>> manager.downgrade()
    INFO: downgrade: 0003_another_migration

    >>> manager.downgrade('0001')
    INFO: downgrade: 0002_custom_name
    INFO: downgrade: 0001_auto_migration

Pass the `--fake` flag to remove the record from migration history table but don't actually run the migration:

.. code:: console

    >>> manager.downgrade(fake=True)
    INFO: downgrade: 0003_another_migration

    >>> manager.downgrade('0001', fake=True)
    INFO: downgrade: 0002_custom_name
    INFO: downgrade: 0001_auto_migration

Delete Migration
----------------

This will remove a migration from the database and the filesystem, as if it never happened.
You might never need this, but it could be useful in some circumstances.

.. code:: console

    >>> manager.delete('0003')
    INFO: deleted: 0003_another_migration

Migration Status
----------------

This will simply show the status of each migration file so you can see which ones have been applied.

.. code:: console

    >>> manager.status()
    INFO: [x] 0001_auto_migration
    INFO: [x] 0002_custom_name
    INFO: [ ] 0003_another_migration

Automagic Migration Creation
----------------------------

It's possible to create a migration file automatically that will have the operations necessary to
upgrade and downgrade your existing models.

Let's say you have the following two models defined in `models.py`:

.. code:: python

    import peewee

    class Group(peewee.Model):
        code = peewee.IntegerField(unique=True)
        name = peewee.CharField(max_length=250)

        class Meta:
            db_table = 'auth_groups'

    class User(peewee.Model):
        name = peewee.CharField(max_length=250)
        group = peewee.ForeignKeyField(Group, related_name='users')

        class Meta:
            db_table = 'auth_users'
            indexes = (
                (('name', 'group'), True),
            )

Running the following command will create the migration file necessary to upgrade/downgrade the
Group model.

.. code:: python

    >>> migrator.create('models.Group')
    INFO: created: 0001_create_table_auth_groups

You can also pass a module to create migration files for all models within:

.. code:: python

    >>> migrator.create('models')
    INFO: created: 0001_create_table_auth_groups
    INFO: created: 0002_create_table_auth_users

Let's look at both those files:

**0001_create_table_auth_groups.py**

.. code:: python

    def upgrade(migrator):
        with migrator.create_table('auth_groups') as table:
            table.primary_key('id')
            table.int('code', unique=True)
            table.char('name', max_length=250)

    def downgrade(migrator):
        migrator.drop_table('auth_groups')

**0002_create_table_auth_users.py**

.. code:: python

    def upgrade(migrator):
        with migrator.create_table('auth_users') as table:
            table.primary_key('id')
            table.char('name', max_length=250)
            table.foreign_key('int', 'group_id', references='auth_groups.id')
            table.add_index(('name', 'group_id'), unique=True)

    def downgrade(migrator):
        migrator.drop_table('auth_users')

As you can see, this creates all the operations necessary to create the table for both models.

The user model has a foreign key to the groups model, but the migration file for users does not
contain a dependency on the Group model! This is intentional. If the Group model changes or gets
removed in a future migration, this migration will not be impacted and can still run any time
a new database needs to be set up.

This currently only supports creating models. If your model changes, it's up to you to write the
migration to support that.

Migrator API
============

The previous exmple shows the files that were created automatically to support two models.
The argument to upgrade() and downgrade() is a migrator instance that has a database-agnostic API.
This allows you to write command in Python that will get executed against the database when
upgrade() and downgrade() are called.

Here's a full example of everything you can do in either upgrade() or downgrade() using the migrator
API:

.. code:: python

    with migrator.create_table(name, safe=False) as table:
        table.primary_key('colname', **kwargs)
        table.bare('colname', **kwargs)
        table.biginteger('colname', **kwargs)
        table.binary('colname', **kwargs)
        table.blob('colname', **kwargs)
        table.bool('colname', **kwargs)
        table.date('colname', **kwargs)
        table.datetime('colname', **kwargs)
        table.decimal('colname', **kwargs)
        table.double('colname', **kwargs)
        table.fixed('colname', **kwargs)
        table.float('colname', **kwargs)
        table.integer('colname', **kwargs)
        table.char('colname', **kwargs)
        table.text('colname', **kwargs)
        table.time('colname', **kwargs)
        table.uuid('colname', **kwargs)
        table.foreign_key('coltype', 'colname', references='othertable.col')
        table.add_index(('col1', 'col2'), unique=True)
        table.add_constraint('constraint string')

    migrator.drop_table('name', safe=False, cascade=False)
    migrator.add_column('table', 'name', 'type', **kwargs)
    migrator.drop_column('table', 'name', 'field', cascade=True)
    migrator.rename_column('table', 'old_name', 'new_name')
    migrator.rename('table', 'old_name', 'new_name')
    migrator.add_not_null('table', 'column')
    migrator.drop_not_null('table', 'column')
    migrator.add_index('table', 'columns', unique=False)
    migrator.drop_index('table', 'index_name')
    cursor = migrator.execute_sql(sql, params=None)

The kwargs are passed to the field as they would be if you were defining the
field on a Peewee model class.

The migrator.execute_sql allows for writing direct SQL if you need to. There's nothing stopping
you from writing something specific to your database engine using this method.

And remember, the migration files are just Python! So you can import and run other Python code
if needed.

Command Line Usage
==================

A command named ``peewee-db`` is automatically installed with this package.
This command allows you to easily issue database management commands without using the Python
API directly:

.. code:: console

    $ peewee-db --help

    Usage: peewee-db [OPTIONS] COMMAND [ARGS]...

        Run database migration commands.

    Options:
        --directory TEXT  [required]
        --database TEXT   [required]
        --table TEXT
        --help            Show this message and exit.

    Commands:
        create     Create a migration based on an existing...
        delete     Delete the target migration from the...
        downgrade  Run database downgrades.
        info       Show information about the current database.
        revision   Create a blank migration file.
        status     Show information about migration status.
        upgrade    Run database upgrades.

Each command requires that you specify a ``database`` and ``directory`` where
``database`` is the URL to your database and ``directory`` is where migration files are stored.

For example, here's how you can show the status of your database:

.. code:: console

    $ peewee-db --database=sqlite:///mydata.sqlite --directory=migrations status
    INFO: [ ] 0001_create_table_auth_groups
    INFO: [ ] 0002_create_table_auth_users

And to create a new revision file you can do this:

.. code:: console

    $ peewee-db --database=sqlite:///mydata.sqlite --directory=migrations revision "custom revision"
    INFO: created: 0003_custom_revision

Pass the `--fake` flag to `upgrade` or `downgrade` to update the migration history table without running the migration:

.. code:: console
    $ peewee-db --database=sqlite:///mydata.sqlite --directory=migrations upgrade --fake
    INFO: upgrade: 0003_custom_revision

    $ peewee-db --database=sqlite:///mydata.sqlite --directory=migrations upgrade
    INFO: all migrations applied!

Flask Usage
===========

This package includes an interface to Flask versions 0.11 or later using Click which provides an
easy-to-use command line interface.
If you are using Flask 0.10, you can use backported integration via Flask-CLI.

For this to work properly, you must define a configuration variable named ``DATABASE`` in your
Flask app config:

.. code:: python

    app = Flask(__name__)
    app.config['DATABASE'] = 'sqlite:///database.sqlite'

This can be a connection string as shown above, or also a dict or ``peewee.Database`` instance.

.. code:: python

    app.config['DATABASE'] = SqliteDatabase('test.sqlite')

    app.config['DATABASE'] = {
        'engine': 'peewee.SqliteDatabase',
        'name': 'test.sqlite'
    }

The ``db`` command will automatically add the command to the cli if Flask is installed:

.. code:: console

    flask db --help

This gives you the following command line interface:

.. code:: console

    $ flask db --help
    Usage: flask db [OPTIONS] COMMAND [ARGS]...

        Run database migration commands for a Flask application.

    Options:
        --help  Show this message and exit.

    Commands:
        create     Create a migration based on an existing model.
        delete     Delete the target migration from the filesystem and database.
        downgrade  Run database downgrades.
        info       Show information about the current database.
        revision   Create a blank migration file.
        status     Show information about the database.
        upgrade    Run database upgrades.

This should look very similar since it uses the same commands we just looked at!

For example, to create the migration for User model would look like this:

.. code:: console

    $ flask db create models.User
    INFO: created: 0003_create_table_user

And to create a blank migration with a custom name would look like this:

.. code:: console

    $ flask db revision "custom revision"
    INFO: created: 0004_custom_revision
