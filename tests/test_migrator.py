import pytest
import peewee

from peewee_moves import DatabaseManager


def test_create_table(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    with manager.migrator.create_table('awesome') as table:
        table.primary_key('id')
        table.char('first_name', index=True)
        table.char('last_name')
        table.add_index(('last_name', 'first_name'), unique=True)


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
