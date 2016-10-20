import pytest
import peewee

from peewee_moves import DatabaseManager


def test_create_table(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    with manager.migrator.create_table('awesome') as table:
        table.primary_key('id')
        table.bare('col_bare')
        table.biginteger('col_biginteger')
        table.binary('col_binary')
        table.blob('col_blob')
        table.bool('col_bool')
        table.char('col_char')
        table.date('col_date')
        table.datetime('col_datetime')
        table.decimal('col_decimal')
        table.double('col_double')
        table.fixed('col_fixed')
        table.float('col_float')
        table.int('col_int')
        table.integer('col_integer')
        table.smallint('col_smallint')
        table.smallinteger('col_smallinteger')
        table.text('col_text')
        table.time('col_time')
        table.uuid('col_uuid')
        table.add_index(('col_char', 'col_integer'), unique=True)


def test_drop_table(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    with manager.migrator.create_table('awesome') as table:
        table.primary_key('id')

    manager.migrator.drop_table('awesome')


def test_add_drop_column(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    with manager.migrator.create_table('awesome') as table:
        table.primary_key('id')

    manager.migrator.add_column('awesome', 'name', 'char', null=True)
    manager.migrator.drop_column('awesome', 'name')


def test_rename_column(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    with manager.migrator.create_table('awesome') as table:
        table.primary_key('id')

    manager.migrator.add_column('awesome', 'name', 'char', null=True)
    manager.migrator.rename_column('awesome', 'name', 'newname')


def test_rename_table(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    with manager.migrator.create_table('awesome') as table:
        table.primary_key('id')

    manager.migrator.rename_table('awesome', 'more_awesome')


def test_not_null(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    with manager.migrator.create_table('awesome') as table:
        table.primary_key('id')
        table.char('name')

    manager.migrator.add_not_null('awesome', 'name')
    manager.migrator.drop_not_null('awesome', 'name')


def test_index(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    with manager.migrator.create_table('awesome') as table:
        table.primary_key('id')
        table.char('name')

    manager.migrator.add_index('awesome', ('name',), unique=True)
    manager.migrator.drop_index('awesome', 'awesome_name')


def test_execute_sql(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    with manager.migrator.create_table('awesome') as table:
        table.primary_key('id')
        table.char('name')

    manager.migrator.execute_sql('select * from awesome')
    with pytest.raises(peewee.OperationalError):
        manager.migrator.execute_sql('select * from notable')


def test_str_constraints(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    with manager.migrator.create_table('awesome') as table:
        table.primary_key('id')
        table.char('username', constraints=[
            "check (username in ('tim', 'bob'))",
            peewee.Check("username in ('tim', 'bob')")
        ])


def test_foreign_key(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    with manager.migrator.create_table('basic') as table:
        table.primary_key('id')
        table.char('username')

    with manager.migrator.create_table('related1') as table:
        table.primary_key('id')
        table.foreign_key('basic_id', 'basic')

    with manager.migrator.create_table('related2') as table:
        table.primary_key('id')
        table.foreign_key('basic_id', 'basic.id')

    with manager.migrator.create_table('related3') as table:
        table.primary_key('id')
        table.foreign_key('basic', 'basic')

    with manager.migrator.create_table('related4') as table:
        table.primary_key('id')
        table.foreign_key('basic', 'basic.id')
