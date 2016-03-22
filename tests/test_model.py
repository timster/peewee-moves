from peewee_moves import DatabaseManager
from peewee_moves import build_upgrade_from_model

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


def test_create_migration_bad_filename(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory='/')
    manager.create(models.Person)
    out, err = capsys.readouterr()
    assert 'Permission denied' in out


def test_create_migration_module(tmpdir, capsys):
    manager = DatabaseManager(models.database, directory=tmpdir)
    manager.create(models)
    out, err = capsys.readouterr()
    assert 'INFO: created migration 0001_create_table_basicfields' in out
    assert 'INFO: created migration 0002_create_table_organization' in out
    assert 'INFO: created migration 0003_create_table_complexperson' in out
    assert 'INFO: created migration 0004_create_table_person' in out


def test_build_upgrade_from_model():
    output = build_upgrade_from_model(models.ComplexPerson)
    output = list(output)
    assert output == [
        "with migrator.create_table('complexperson') as table:",
        "        table.primary_key('id')",
        "        table.char('name', max_length=5, unique=True)",
        "        table.foreign_key('organization_id', references='organization.id')",
        "        table.add_constraint(const1 fake)",
        "        table.add_constraint(const2 fake)",
    ]
