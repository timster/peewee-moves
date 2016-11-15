from peewee_moves import DatabaseManager
from peewee_moves import build_upgrade_from_model

from tests import models


def test_create_import(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.create('Person')

    out, err = capsys.readouterr()
    assert out == 'could not import: Person\n'


def test_create_error(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.create(models.NotModel)
    out, err = capsys.readouterr()
    assert out == "ERROR: type object 'NotModel' has no attribute '_meta'\n"


def test_create(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.create(models.Person)
    out, err = capsys.readouterr()
    assert out == 'created: 0001_create_table_person\n'


def test_create_module(tmpdir, capsys):
    manager = DatabaseManager(models.database, directory=tmpdir)
    manager.create(models)
    out, err = capsys.readouterr()
    assert 'created: 0001_create_table_basicfields' in out
    assert 'created: 0002_create_table_hascheckconstraint' in out
    assert 'created: 0003_create_table_organization' in out
    assert 'created: 0004_create_table_complexperson' in out
    assert 'created: 0005_create_table_person' in out


def test_build_upgrade_from_model():
    output = build_upgrade_from_model(models.ComplexPerson)
    output = list(output)
    assert output == [
        "with migrator.create_table('complexperson') as table:",
        "    table.primary_key('id')",
        "    table.char('name', max_length=5, unique=True)",
        "    table.foreign_key('organization_id', references='organization.id')",
        "    table.add_constraint('const1 fake')",
        "    table.add_constraint('CHECK (const2 fake)')",
    ]


def test_non_id_foreign_key_output():
    output = build_upgrade_from_model(models.RelatesToName)
    output = list(output)

    assert output == [
        "with migrator.create_table('relatestoname') as table:",
        "    table.primary_key('id')",
        "    table.foreign_key('person_name', references='person.name')"]
