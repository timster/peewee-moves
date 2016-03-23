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
    assert out == 'INFO: 0001_create_table_person: created\n'


def test_create_migration_bad_filename(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory='/invalid')
    manager.create(models.Person)
    out, err = capsys.readouterr()
    assert out.startswith('ERROR: [Errno 1')


def test_create_migration_module(tmpdir, capsys):
    manager = DatabaseManager(models.database, directory=tmpdir)
    manager.create(models)
    out, err = capsys.readouterr()
    assert 'INFO: 0001_create_table_basicfields: created' in out
    assert 'INFO: 0002_create_table_organization: created' in out
    assert 'INFO: 0003_create_table_complexperson: created' in out
    assert 'INFO: 0004_create_table_person: created' in out


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
