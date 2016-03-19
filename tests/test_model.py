from peewee_moves import DatabaseManager

from tests import models


def test_create_migration_error(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.create('Person')

    out, err = capsys.readouterr()
    assert out == 'INFO: could not import: Person\n'


def test_create_migration(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.create(models.Person)
    out, err = capsys.readouterr()
    assert out == 'INFO: created migration 0001_create_table_person\n'


def test_create_migration_module(tmpdir, capsys):
    manager = DatabaseManager(models.database, directory=tmpdir)
    manager.create(models)
    out, err = capsys.readouterr()
    assert 'INFO: created migration 0001_create_table_basicfields' in out
    assert 'INFO: created migration 0002_create_table_organization' in out
    assert 'INFO: created migration 0003_create_table_person' in out
