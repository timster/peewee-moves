import pytest
import peewee

from peewee_moves import DatabaseManager

database = peewee.SqliteDatabase(':memory:')


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


def test_revision(capsys, tmpdir):
    manager = DatabaseManager(database, directory=tmpdir)

    manager.revision()
    out, err = capsys.readouterr()
    assert out == 'INFO: 0001_automigration: created\n'

    manager.revision('Custom Name')
    out, err = capsys.readouterr()
    assert out == 'INFO: 0002_custom_name: created\n'


def test_find_migration(capsys, tmpdir):
    manager = DatabaseManager(database, directory=tmpdir)
    manager.revision()

    rv = manager.find_migration('0001')
    assert rv == '0001_automigration'

    rv = manager.find_migration('0001_automigration')
    assert rv == '0001_automigration'

    with pytest.raises(ValueError):
        manager.find_migration('does_not_exist')
