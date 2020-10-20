import importlib
import sys

from click.testing import CliRunner
from flask import Flask
from flask.cli import ScriptInfo

from peewee_moves import flask_command

flaskapp = Flask(__name__)
flaskapp.config['DATABASE'] = 'sqlite:///:memory:'

runner = CliRunner()


def test_missing_flask(mocker):
    import peewee_moves

    # flask is installed, so FLASK_CLI_ENABLED is True
    importlib.reload(peewee_moves)
    assert peewee_moves.FLASK_CLI_ENABLED

    # remove flask and reload, so FLASK_CLI_ENABLED is False
    mocker.patch.dict(sys.modules)
    sys.modules['flask'] = None
    importlib.reload(peewee_moves)

    assert not peewee_moves.FLASK_CLI_ENABLED


def test_info(tmpdir):
    flaskapp.root_path = str(tmpdir)
    obj = ScriptInfo(create_app=lambda info: flaskapp)
    result = runner.invoke(flask_command, ['info'], obj=obj)
    assert result.exit_code == 0


def test_status(tmpdir):
    flaskapp.root_path = str(tmpdir)
    obj = ScriptInfo(create_app=lambda info: flaskapp)
    result = runner.invoke(flask_command, ['status'], obj=obj)
    assert result.exit_code == 0


def test_create(tmpdir):
    flaskapp.root_path = str(tmpdir)
    obj = ScriptInfo(create_app=lambda info: flaskapp)
    result = runner.invoke(flask_command, ['create', 'name'], obj=obj)
    assert result.exit_code == 1


def test_revision(tmpdir):
    flaskapp.root_path = str(tmpdir)
    obj = ScriptInfo(create_app=lambda info: flaskapp)
    result = runner.invoke(flask_command, ['revision', 'name'], obj=obj)
    assert result.exit_code == 0


def test_upgrade(tmpdir):
    flaskapp.root_path = str(tmpdir)
    obj = ScriptInfo(create_app=lambda info: flaskapp)
    result = runner.invoke(flask_command, ['upgrade'], obj=obj)
    assert result.exit_code == 0


def test_upgrade(tmpdir):
    flaskapp.root_path = str(tmpdir)
    obj = ScriptInfo(create_app=lambda info: flaskapp)
    result = runner.invoke(flask_command, ['fake'], obj=obj)
    assert result.exit_code == 0


def test_downgrade(tmpdir):
    flaskapp.root_path = str(tmpdir)
    obj = ScriptInfo(create_app=lambda info: flaskapp)
    result = runner.invoke(flask_command, ['downgrade'], obj=obj)
    assert result.exit_code == 1


def test_delete(tmpdir):
    flaskapp.root_path = str(tmpdir)
    obj = ScriptInfo(create_app=lambda info: flaskapp)
    result = runner.invoke(flask_command, ['delete'], obj=obj)
    assert result.exit_code == 1
