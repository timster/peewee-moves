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


def test_info(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    manager.info()
    assert 'driver: SqliteDatabase' in caplog.text
    assert 'database: :memory:' in caplog.text


def test_revision(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    manager.revision()
    assert 'created: 0001_auto_migration' in caplog.text

    manager.revision('Custom Name')
    assert 'created: 0002_custom_name' in caplog.text


def test_revision_error(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    manager.revision('Bad Characters: \0')
    assert 'embedded' in caplog.text


def test_find_migration(tmpdir):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()

    rv = manager.find_migration('0001')
    assert rv == '0001_auto_migration'

    rv = manager.find_migration('0001_auto_migration')
    assert rv == '0001_auto_migration'

    with pytest.raises(ValueError):
        manager.find_migration('does_not_exist')


def test_open_migration(tmpdir):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()

    with manager.open_migration('0001_auto_migration') as handle:
        content = handle.read()

    assert content.startswith('"""\nauto migration')
    assert 'def upgrade(migrator):\n    pass' in content
    assert 'def downgrade(migrator):\n    pass' in content


def test_status(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    manager.status()
    assert 'no migrations found' in caplog.text

    manager.revision()
    assert 'created: 0001_auto_migration' in caplog.text

    manager.status()
    assert '[ ] 0001_auto_migration' in caplog.text


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


def test_upgrade_all(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.revision()

    manager.upgrade()
    assert 'upgrade: 0001_auto_migration' in caplog.text
    assert 'upgrade: 0002_auto_migration' in caplog.text

    assert manager.db_migrations == ['0001_auto_migration', '0002_auto_migration']
    assert manager.diff == []

    # All migrations applied now...
    manager.upgrade()
    assert 'all migrations applied!' in caplog.text


def test_upgrade_target(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.revision()

    manager.upgrade('0001')
    assert 'upgrade: 0001_auto_migration' in caplog.text

    assert manager.db_migrations == ['0001_auto_migration']
    assert manager.diff == ['0002_auto_migration']


def test_already_upgraded(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()

    manager.upgrade('0001')
    assert 'upgrade: 0001_auto_migration' in caplog.text

    manager.upgrade('0001')
    assert 'already applied: 0001_auto_migration' in caplog.text


def test_upgrade_target_error(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()

    manager.upgrade('9999')
    assert 'could not find migration: 9999' in caplog.text


def test_downgrade_nodiff(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.downgrade()
    assert 'migrations not yet applied!' in caplog.text


def test_downgrade_single(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.revision()
    manager.upgrade()

    assert manager.db_migrations == ['0001_auto_migration', '0002_auto_migration']
    assert manager.diff == []

    manager.downgrade()
    assert 'downgrade: 0002_auto_migration' in caplog.text

    assert manager.db_migrations == ['0001_auto_migration']
    assert manager.diff == ['0002_auto_migration']


def test_downgrade_target(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.revision()
    manager.upgrade()

    assert manager.db_migrations == ['0001_auto_migration', '0002_auto_migration']
    assert manager.diff == []

    manager.downgrade('0001')
    assert 'downgrade: 0002_auto_migration' in caplog.text
    assert 'downgrade: 0001_auto_migration' in caplog.text

    assert manager.db_migrations == []
    assert manager.diff == ['0001_auto_migration', '0002_auto_migration']


def test_downgrade_not_applied(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()

    manager.downgrade('0001')
    assert 'not yet applied: 0001_auto_migration' in caplog.text


def test_downgrade_target_error(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()

    manager.downgrade('9999')
    assert 'could not find migration: 9999' in caplog.text


def test_run_migration_not_found(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()

    manager.run_migration('9999')
    assert 'could not find migration: 9999' in caplog.text


def test_run_migration_exception(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()

    # Open the migration file and write lines to it that will error when we try to run it.
    with manager.open_migration('0001_auto_migration', 'w') as handle:
        handle.write('def upgrade(migrator):\n    undefined\n')

    manager.upgrade()
    assert "upgrade: 0001_auto_migration" in caplog.text
    assert "'undefined' is not defined" in caplog.text


def test_delete(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.upgrade()

    manager.delete('0001')
    assert 'deleted: 0001_auto_migration' in caplog.text

    assert manager.db_migrations == []
    assert manager.migration_files == []


def test_delete_not_found(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.upgrade()

    manager.delete('9999')
    assert 'could not find migration: 9999' in caplog.text
