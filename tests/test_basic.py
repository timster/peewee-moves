import pytest
import peewee

from peewee_moves import DatabaseManager



def test_database_creation(tmpdir):
    db = peewee.SqliteDatabase(':memory:')
    manager = DatabaseManager(db, directory=tmpdir)
    assert isinstance(manager.database, peewee.SqliteDatabase)

    db = {'engine': 'peewee.SqliteDatabase', 'name': ':memory:'}
    manager = DatabaseManager(db, directory=tmpdir)
    assert isinstance(manager.database, peewee.SqliteDatabase)

    db = 'sqlite:///:memory:'
    manager = DatabaseManager(db, directory=tmpdir)
    assert isinstance(manager.database, peewee.SqliteDatabase)


def test_database_creation_error(tmpdir):
    db = {'name': ':memory:'}
    with pytest.raises(peewee.DatabaseError):
        DatabaseManager(db, directory=tmpdir)

    db = {'engine': 'peewee.SqliteDatabase'}
    with pytest.raises(peewee.DatabaseError):
        DatabaseManager(db, directory=tmpdir)

    db = {'engine': 'unknown.FakeDatabase', 'name': ':memory:'}
    with pytest.raises(peewee.DatabaseError):
        DatabaseManager(db, directory=tmpdir)


def test_revision(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    manager.revision()
    out, err = capsys.readouterr()
    assert out == 'INFO: 0001_automigration: created\n'

    manager.revision('Custom Name')
    out, err = capsys.readouterr()
    assert out == 'INFO: 0002_custom_name: created\n'


def test_find_migration(tmpdir):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()

    rv = manager.find_migration('0001')
    assert rv == '0001_automigration'

    rv = manager.find_migration('0001_automigration')
    assert rv == '0001_automigration'

    with pytest.raises(ValueError):
        manager.find_migration('does_not_exist')


def test_status(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    manager.status()
    out, err = capsys.readouterr()
    assert out == 'INFO: no migrations found\n'

    manager.revision()
    out, err = capsys.readouterr()
    assert out == 'INFO: 0001_automigration: created\n'

    manager.status()
    out, err = capsys.readouterr()
    assert out == 'INFO: 0001_automigration: pending\n'


def test_files_and_diff(tmpdir):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.revision('custom name')

    rv = manager.db_migrations
    assert rv == []

    rv = manager.migration_files
    assert rv == ['0001_automigration', '0002_custom_name']

    rv = manager.diff
    assert rv == ['0001_automigration', '0002_custom_name']
