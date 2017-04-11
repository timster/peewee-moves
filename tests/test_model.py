from peewee_moves import DatabaseManager
from peewee_moves import build_upgrade_from_model

from tests import models


def test_create_import(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.create('Person')

    assert 'could not import: Person' in caplog.text


def test_create_error(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.create(models.NotModel)
    assert "type object 'NotModel' has no attribute '_meta'" in caplog.text


def test_create(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.create(models.Person)
    assert 'created: 0001_create_table_person' in caplog.text


def test_create_module(tmpdir, caplog):
    manager = DatabaseManager(models.database, directory=tmpdir)
    manager.create(models)
    assert 'created: 0001_create_table_basicfields' in caplog.text
    assert 'created: 0002_create_table_hascheckconstraint' in caplog.text
    assert 'created: 0003_create_table_organization' in caplog.text
    assert 'created: 0004_create_table_complexperson' in caplog.text
    assert 'created: 0005_create_table_person' in caplog.text


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
        "    table.foreign_key('person_name', on_delete='SET NULL', on_update='CASCADE', references='person.name')"]
