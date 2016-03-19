Usage
#####

.. contents::

Direct Usage
============

The main entry point is the `DatabaseManager` class which accepts the following parameters:

- database: location of database (URL string, dictionary, or `peewee.Database` instance).
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

This will create a blank migration file with the next ID and the default name of "automigration"
or whatever name you provide

.. code:: console

    >>> manager.revision()
    INFO: created migration 0001_automigration

    >>> manager.revision('custom name')
    INFO: created migration 0002_custom_name

Database Upgrade
----------------

This will run the upgrade() method in each unapplied migration. If you specify a target, the
migrator will only run upgrades through that target. If no target is specified, all unapplied
migrations will run.

    >>> manager.upgrade('0001')
    INFO: 0001_automigration: upgrade

    >>> manager.upgrade()
    INFO: 0002_custom_name: upgrade
    INFO: 0003_another_migration: upgrade

Database Downgrade
------------------

This does the opposite of upgrade(). It calls the downgrade() method on each applied migration. If
you specify a target, the migrator will only run downgrades through that target. If no target is
specified, only the most recent migration will be downgraded.

    >>> manager.downgrade()
    INFO: 0003_another_migration: downgrade

    >>> manager.downgrade('0001')
    INFO: 0002_custom_name: downgrade
    INFO: 0001_automigration: downgrade

Delete Migration
----------------

This will remove a migration from the database and the filesystem, as if it never happened. You
might never need this, but it could be useful in some circumstances.

    >>> manager.delete('0003')
    INFO: 0003_another_migration: delete

Migration Status
----------------

This will simply show the status of each migration file so you can see which ones have been applied.

    >>> manager.status()
    INFO: 0001_automigration: applied
    INFO: 0002_custom_name: applied
    INFO: 0003_another_migration: pending

Automagic Migration Creation
----------------------------

It's possible to create a migration file automatically that will have the operations necessary to
upgrade and downgrade your existing models.

Let's say you have the following two models defined in `models.py`:

.. code:: python

    import peewee

    class Group(peewee.Model):
        code = peewee.IntegerField()
        name = peewee.CharField(max_length=250)

        class Meta:
            db_table = 'auth_groups'
            indexes = (
                (('code', 'category_id'), True),
            )

    class User(peewee.Model):
        code = peewee.IntegerField(unique=True)
        name = peewee.CharField(max_length=250)

        group = peewee.ForeignKeyField(Group, related_name='users')

        class Meta:
            db_table = 'auth_users'

Running the following command will create the migration file necessary to upgrade/downgrade the
Group model.

.. code:: python

    >>> migrator.create('models.Group')
    INFO: 0001_create_table_auth_groups: created

You can also pass a module to create migration files for all models within:

.. code:: python

    >>> migrator.create('models')
    INFO: 0001_create_table_auth_groups: created
    INFO: 0002_create_table_auth_users: created

Let's look at both those files:

**0001_create_table_auth_groups.py**

.. code:: python

    def upgrade(migrator):
        with migrator.create_table('auth_groups') as table:
            table.primary_key('id')
            table.integer('code')
            table.char('name', max_length=250)
            table.add_index(('code', 'name'), unique=True)

    def downgrade(migrator):
        migrator.drop_table('auth_groups')

**0002_create_table_auth_users.py**

.. code:: python

    def upgrade(migrator):
        with migrator.create_table('auth_users') as table:
            table.primary_key('id')
            table.integer('code', unique=True)
            table.char('name', max_length=250)
            table.foreign_key('group_id', references='auth_groups.id')

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
=======================

The previous exmple shows the files that were created automatically to support two models. The
argument to upgrade() and downgrade() is a migrator instance that has a database-agnostic API.
This allows you to write command in Python that will get executed against the database when you
call upgrade or downgrade.

Here's a full example of everything you can do in either upgrade() or downgrade() using the migrator
API:

.. code:: python

    with migrator.create_table(self, name, safe=False) as table:
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
        table.foreign_key('colname', references='othertable.col')
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

The kwargs are passed to the field as they would be if you were defining
the field on the model itself.

The migrator.execute_sql allows for writing direct SQL if you need to. There's nothing stopping
you from writing something specific to your database engine using this method.

And remember, the migration files are just Python! So you can import and run other Python code
if needed.

Flask Usage
===========

This package includes an interface to Flask-Script which provides an easy-to-use command line
interface.

To set up, you first need to make sure you have DATABASE defiend in your configuration:

.. code:: python

    DATABASE = {
        'name': '/path/database.sqlite',
        'engine': 'peewee.SqliteDatabase',
    }

Then in `manage.py` (or wherever you have Flask-Script setup) you can import the database manager
and mount it as a sub-command:

.. code:: python

    from flask_script import Manager

    from peewee_moves import migration_manager

    manager = Manager(app)
    manager.add_command('db', migration_manager)

This gives you the following command line interface:

.. code:: console

    $ ./manage.py db
    usage: ./manage.py db [command]

    positional arguments:
        create       Create a migration based on an existing model.
        delete       Delete the target migration from the filesystem and database.
        downgrade    Run database downgrades.
        revision     Create a blank migration file.
        status       Show all migrations and the status of each.
        upgrade      Run database upgrades.

This should look very similar since it uses the same commands we just looked at!

For example, to create the migration for User model would look like this:

.. code:: console

    $ ./manage.py db create -m models.User
    INFO: 0003_create_table_user: created

And to create a blank migration with a custom name would look like this:

.. code:: console

    $ ./manage.py db revision -n "custom name"
    INFO: 0004_custom_name: created
