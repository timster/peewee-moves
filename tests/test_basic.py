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

    assert manager.revision()
    first = manager.migration_files[0]
    assert 'created: {}'.format(first) in caplog.text

    assert manager.revision('Custom Name')
    first = manager.migration_files[1]
    assert 'created: {}'.format(first) in caplog.text


def test_revision_error(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    assert not manager.revision('Bad Characters: \0')
    assert 'embedded' in caplog.text


def test_find_migration(tmpdir):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()

    # find the first migration name
    first = manager.migration_files[0]
    first_id = first.split('_')[0]

    rv = manager.find_migration(first_id)
    assert rv == first

    rv = manager.find_migration(first)
    assert rv == first

    with pytest.raises(ValueError):
        manager.find_migration('does_not_exist')


def test_open_migration(tmpdir):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    first = manager.migration_files[0]

    with manager.open_migration(first) as handle:
        content = handle.read()

    assert content.startswith('"""\nauto migration')
    assert 'def upgrade(migrator):\n    pass' in content
    assert 'def downgrade(migrator):\n    pass' in content


def test_status(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)

    manager.status()
    assert 'no migrations found' in caplog.text

    manager.revision()
    first = manager.migration_files[0]
    assert 'created: {}'.format(first) in caplog.text

    manager.status()
    assert '[ ] {}'.format(first) in caplog.text


def test_files_and_diff(tmpdir):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.revision('custom name')
    migrations = manager.migration_files

    rv = manager.db_migrations
    assert not rv

    rv = manager.migration_files
    assert rv == (migrations[0], migrations[1],)

    rv = manager.diff
    assert rv == (migrations[0], migrations[1],)


def test_upgrade_all(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.revision()
    migrations = manager.migration_files

    manager.upgrade()
    assert 'upgrade: {}'.format(migrations[0]) in caplog.text
    assert 'upgrade: {}'.format(migrations[1]) in caplog.text

    assert manager.db_migrations == (migrations[0], migrations[1])
    assert not manager.diff

    # All migrations applied now...
    manager.upgrade()
    assert 'all migrations applied!' in caplog.text


def test_upgrade_target(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.revision()
    migrations = manager.migration_files

    manager.upgrade(migrations[0])
    assert 'upgrade: {}'.format(migrations[0]) in caplog.text

    assert manager.db_migrations == (migrations[0],)
    assert manager.diff == (migrations[1],)


def test_already_upgraded(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    migrations = manager.migration_files

    manager.upgrade(migrations[0])
    assert 'upgrade: {}'.format(migrations[0]) in caplog.text

    manager.upgrade(migrations[0])
    assert 'already applied: {}'.format(migrations[0]) in caplog.text


def test_upgrade_target_error(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()

    manager.upgrade('does-not-exist')
    assert 'could not find migration: does-not-exist' in caplog.text


def test_downgrade_nodiff(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.downgrade()
    assert 'migrations not yet applied!' in caplog.text


def test_downgrade_single(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.revision()
    manager.upgrade()
    migrations = manager.migration_files

    assert manager.db_migrations == (migrations[0], migrations[1],)
    assert not manager.diff

    manager.downgrade()
    assert 'downgrade: {}'.format(migrations[1]) in caplog.text

    assert manager.db_migrations == (migrations[0],)
    assert manager.diff == (migrations[1],)


def test_downgrade_target(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.revision()
    manager.upgrade()
    migrations = manager.migration_files

    assert manager.db_migrations == (migrations[0], migrations[1],)
    assert not manager.diff

    manager.downgrade('0001')
    assert 'downgrade: {}'.format(migrations[1]) in caplog.text
    assert 'downgrade: {}'.format(migrations[0]) in caplog.text

    assert not manager.db_migrations
    assert manager.diff == (migrations[0], migrations[1],)


def test_downgrade_not_applied(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    migrations = manager.migration_files

    manager.downgrade(migrations[0])
    assert 'not yet applied: {}'.format(migrations[0]) in caplog.text


def test_downgrade_target_error(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()

    manager.downgrade('does-not-exist')
    assert 'could not find migration: does-not-exist' in caplog.text


def test_run_migration_not_found(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()

    manager.run_migration('does-not-exist')
    assert 'could not find migration: does-not-exist' in caplog.text


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
    migrations = manager.migration_files

    manager.delete(migrations[0])
    assert 'deleted: {}'.format(migrations[0]) in caplog.text

    assert not manager.db_migrations
    assert not manager.migration_files


def test_delete_not_found(tmpdir, caplog):
    manager = DatabaseManager('sqlite:///:memory:', directory=tmpdir)
    manager.revision()
    manager.upgrade()

    manager.delete('does-not-exist')
    assert 'could not find migration: does-not-exist' in caplog.text
