import peewee
import pytest

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


@pytest.mark.skipif(peewee.__version__.startswith('2.10'),
                    reason='peewee 2.10 generate the modules depending on the module relationship')
def test_create_module(tmpdir, caplog):
    """Test module creations.

    peewee handles the model creation sequentially in prior versions of 2.10

    Refer to:
    https://github.com/coleifer/peewee/compare/2.9.2...2.10.0
    """
    manager = DatabaseManager(models.database, directory=tmpdir)
    manager.create(models)
    migrations = manager.migration_files

    assert len(migrations) == 7

    assert migrations[0].endswith('create_table_basicfields')
    assert 'created: {}'.format(migrations[0]) in caplog.text

    assert migrations[1].endswith('create_table_hascheckconstraint')
    assert 'created: {}'.format(migrations[1]) in caplog.text

    assert migrations[2].endswith('create_table_organization')
    assert 'created: {}'.format(migrations[2]) in caplog.text

    assert migrations[3].endswith('create_table_complexperson')
    assert 'created: {}'.format(migrations[3]) in caplog.text

    assert migrations[4].endswith('create_table_person')
    assert 'created: {}'.format(migrations[4]) in caplog.text

    assert migrations[5].endswith('create_table_hasuniqueforeignkey')
    assert 'created: {}'.format(migrations[5]) in caplog.text

    assert migrations[6].endswith('create_table_relatestoname')
    assert 'created: {}'.format(migrations[6]) in caplog.text


@pytest.mark.skipif(not peewee.__version__.startswith('2.10'),
                    reason='peewee prior to 2.10 generate module migrations sequentially')
def test_create_module_2_10(tmpdir, caplog):
    """Test module creations.

    peewee changed the migration creation order in:
    https://github.com/coleifer/peewee/compare/2.9.2...2.10.0
    
    First create models on which current model depends
    (either through foreign keys or through depends_on),
    then create current model itself.
    """
    manager = DatabaseManager(models.database, directory=tmpdir)
    manager.create(models)
    migrations = manager.migration_files

    assert len(migrations) == 7

    assert migrations[0].endswith('create_table_basicfields')
    assert 'created: {}'.format(migrations[0]) in caplog.text

    assert migrations[1].endswith('create_table_organization')
    assert 'created: {}'.format(migrations[1]) in caplog.text

    assert migrations[2].endswith('create_table_complexperson')
    assert 'created: {}'.format(migrations[2]) in caplog.text

    assert migrations[3].endswith('create_table_hascheckconstraint')
    assert 'created: {}'.format(migrations[3]) in caplog.text

    assert migrations[4].endswith('create_table_person')
    assert 'created: {}'.format(migrations[4]) in caplog.text

    assert migrations[5].endswith('create_table_hasuniqueforeignkey')
    assert 'created: {}'.format(migrations[5]) in caplog.text

    assert migrations[6].endswith('create_table_relatestoname')
    assert 'created: {}'.format(migrations[6]) in caplog.text


def test_build_upgrade_from_model():
    output = build_upgrade_from_model(models.ComplexPerson)
    output = list(output)
    assert output == [
        "with migrator.create_table('complexperson') as table:",
        "    table.primary_key('id')",
        "    table.char('name', max_length=5, unique=True)",
        "    table.foreign_key('int', 'organization_id', on_delete=None, on_update=None, references='organization.id')",
        "    table.add_constraint('const1 fake')",
        "    table.add_constraint('CHECK (const2 fake)')",
    ]


def test_non_id_foreign_key_output():
    output = build_upgrade_from_model(models.RelatesToName)
    output = list(output)

    assert output == [
        "with migrator.create_table('relatestoname') as table:",
        "    table.primary_key('id')",
        "    table.foreign_key('string', 'person_name', on_delete='SET NULL', on_update='CASCADE', references='person.name')"]


def test_index_field_names():
    output = build_upgrade_from_model(models.HasUniqueForeignKey)
    output = list(output)

    assert output == [
        "with migrator.create_table('hasuniqueforeignkey') as table:",
        "    table.primary_key('id')",
        "    table.int('age')",
        "    table.foreign_key('string', 'person_name', on_delete=None, on_update=None, references='person.name')",
        "    table.add_index(('age', 'person_name'), unique=True)"]
