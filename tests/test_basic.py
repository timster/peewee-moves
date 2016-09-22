import os

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


def test_info(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    manager.info()
    out, err = capsys.readouterr()
    assert out == 'INFO: driver = SqliteDatabase\nINFO: database = :memory:\n'


def test_revision(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    manager.revision()
    out, err = capsys.readouterr()
    assert out == 'INFO: 0001_auto_migration: created\n'

    manager.revision('Custom Name')
    out, err = capsys.readouterr()
    assert out == 'INFO: 0002_custom_name: created\n'


def test_find_migration(tmpdir):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()

    rv = manager.find_migration('0001')
    assert rv == '0001_auto_migration'

    rv = manager.find_migration('0001_auto_migration')
    assert rv == '0001_auto_migration'

    with pytest.raises(ValueError):
        manager.find_migration('does_not_exist')


def test_open_migration(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()

    with manager.open_migration('0001_auto_migration') as handle:
        content = handle.read()

    assert content.startswith('"""\nauto migration')
    assert 'def upgrade(migrator):\n    pass' in content
    assert 'def downgrade(migrator):\n    pass' in content


def test_status(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    manager.status()
    out, err = capsys.readouterr()
    assert out == 'INFO: no migrations found\n'

    manager.revision()
    out, err = capsys.readouterr()
    assert out == 'INFO: 0001_auto_migration: created\n'

    manager.status()
    out, err = capsys.readouterr()
    assert out == 'INFO: 0001_auto_migration: pending\n'


def test_files_and_diff(tmpdir):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.revision('custom name')

    rv = manager.db_migrations
    assert rv == []

    rv = manager.migration_files
    assert rv == ['0001_auto_migration', '0002_custom_name']

    rv = manager.diff
    assert rv == ['0001_auto_migration', '0002_custom_name']


def test_upgrade_all(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.revision()
    capsys.readouterr()

    manager.upgrade()
    out, err = capsys.readouterr()
    assert out == 'INFO: 0001_auto_migration: upgrade\nINFO: 0002_auto_migration: upgrade\n'

    assert manager.db_migrations == ['0001_auto_migration', '0002_auto_migration']
    assert manager.diff == []

    # All migrations applied now...
    manager.upgrade()
    out, err = capsys.readouterr()
    assert out == 'INFO: all migrations applied!\n'


def test_upgrade_target(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.revision()
    capsys.readouterr()

    manager.upgrade('0001')
    out, err = capsys.readouterr()
    assert out == 'INFO: 0001_auto_migration: upgrade\n'

    assert manager.db_migrations == ['0001_auto_migration']
    assert manager.diff == ['0002_auto_migration']


def test_already_upgraded(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    capsys.readouterr()

    manager.upgrade('0001')
    out, err = capsys.readouterr()
    assert out == 'INFO: 0001_auto_migration: upgrade\n'

    manager.upgrade('0001')
    out, err = capsys.readouterr()
    assert out == 'INFO: 0001_auto_migration: already applied\n'


def test_upgrade_target_error(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    capsys.readouterr()

    manager.upgrade('9999')
    out, err = capsys.readouterr()
    assert out == 'ERROR: could not find migration: 9999\n'


def test_downgrade_nodiff(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.downgrade()
    out, err = capsys.readouterr()
    assert out == 'INFO: migrations not yet applied!\n'


def test_downgrade_single(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.revision()
    manager.upgrade()
    capsys.readouterr()

    assert manager.db_migrations == ['0001_auto_migration', '0002_auto_migration']
    assert manager.diff == []

    manager.downgrade()
    out, err = capsys.readouterr()
    assert out == 'INFO: 0002_auto_migration: downgrade\n'

    assert manager.db_migrations == ['0001_auto_migration']
    assert manager.diff == ['0002_auto_migration']


def test_downgrade_target(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.revision()
    manager.upgrade()
    capsys.readouterr()

    assert manager.db_migrations == ['0001_auto_migration', '0002_auto_migration']
    assert manager.diff == []

    manager.downgrade('0001')
    out, err = capsys.readouterr()
    assert out == 'INFO: 0002_auto_migration: downgrade\nINFO: 0001_auto_migration: downgrade\n'

    assert manager.db_migrations == []
    assert manager.diff == ['0001_auto_migration', '0002_auto_migration']


def test_downgrade_not_applied(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    capsys.readouterr()

    manager.downgrade('0001')
    out, err = capsys.readouterr()
    assert out == 'INFO: 0001_auto_migration: not yet applied\n'


def test_downgrade_target_error(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    capsys.readouterr()

    manager.downgrade('9999')
    out, err = capsys.readouterr()
    assert out == 'ERROR: could not find migration: 9999\n'


def test_run_migration_not_found(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    capsys.readouterr()

    manager.run_migration('9999')
    out, err = capsys.readouterr()
    assert out == 'ERROR: could not find migration: 9999\n'


def test_run_migration_exception(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    capsys.readouterr()

    # Open the migration file and write lines to it that will error when we try to run it.
    with manager.open_migration('0001_auto_migration', 'w') as handle:
        handle.write('def upgrade(migrator):\n    undefined\n')

    manager.upgrade()
    out, err = capsys.readouterr()
    assert "INFO: 0001_auto_migration: upgrade" in out
    assert "'undefined' is not defined" in out


def test_delete(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.upgrade()
    capsys.readouterr()

    manager.delete('0001')
    out, err = capsys.readouterr()
    assert out == 'INFO: 0001_auto_migration: delete\n'

    assert manager.db_migrations == []
    assert manager.migration_files == []


def test_delete_not_found(tmpdir, capsys):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.upgrade()
    capsys.readouterr()

    manager.delete('9999')
    out, err = capsys.readouterr()
    assert out == 'ERROR: could not find migration: 9999\n'
