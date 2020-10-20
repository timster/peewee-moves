import pytest
from click.testing import CliRunner

from peewee_moves import cli_command

runner = CliRunner()


@pytest.fixture(scope='function')
def command(tmpdir):
    migration_dir = str(tmpdir.join('migrations'))
    database = 'sqlite:///{}'.format(tmpdir.join('database.sqlite'))
    return ['--directory', migration_dir, '--database', database]


def test_info(command):
    command = command + ['info']
    result = runner.invoke(cli_command, command)
    assert result.exit_code == 0


def test_status(command):
    command = command + ['status']
    result = runner.invoke(cli_command, command)
    assert result.exit_code == 0


def test_create(command):
    command = command + ['create'] + ['tests.models']
    result = runner.invoke(cli_command, command)
    assert result.exit_code == 0


def test_create_fail(command):
    command = command + ['create'] + ['name']
    result = runner.invoke(cli_command, command)
    assert result.exit_code == 1


def test_revision(command):
    command = command + ['revision'] + ['name']
    result = runner.invoke(cli_command, command)
    assert result.exit_code == 0


def test_upgrade(command):
    command = command + ['upgrade']
    result = runner.invoke(cli_command, command)
    assert result.exit_code == 0


def test_fake(command):
    command = command + ['fake']
    result = runner.invoke(cli_command, command)
    assert result.exit_code == 0


def test_downgrade(command):
    test_revision(command)
    test_upgrade(command)

    command3 = command + ['downgrade']
    result = runner.invoke(cli_command, command3)
    assert result.exit_code == 0


def test_downgrade_fail(command):
    command = command + ['downgrade']
    result = runner.invoke(cli_command, command)
    assert result.exit_code == 1


def test_delete(command):
    test_revision(command)
    test_upgrade(command)

    command3 = command + ['delete'] + ['0001']
    result = runner.invoke(cli_command, command3)
    assert result.exit_code == 0


def test_delete_fail(command):
    command = command + ['delete']
    result = runner.invoke(cli_command, command)
    assert result.exit_code == 1
