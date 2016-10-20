from click.testing import CliRunner
from flask import Flask
from flask.cli import ScriptInfo

from peewee_moves import delete as flask_delete
from peewee_moves import downgrade as flask_downgrade
from peewee_moves import info as flask_info
from peewee_moves import create as flask_create
from peewee_moves import revision as flask_revision
from peewee_moves import status as flask_status
from peewee_moves import upgrade as flask_upgrade

flaskapp = Flask(__name__)
flaskapp.config['DATABASE'] = 'sqlite:///:memory:'

runner = CliRunner()


def test_info(tmpdir):
    flaskapp.root_path = str(tmpdir)
    obj = ScriptInfo(create_app=lambda info: flaskapp)
    result = runner.invoke(flask_info, obj=obj)
    assert result.exit_code == 0


def test_status(tmpdir):
    flaskapp.root_path = str(tmpdir)
    obj = ScriptInfo(create_app=lambda info: flaskapp)
    result = runner.invoke(flask_status, obj=obj)
    assert result.exit_code == 0


def test_create(tmpdir):
    flaskapp.root_path = str(tmpdir)
    obj = ScriptInfo(create_app=lambda info: flaskapp)
    result = runner.invoke(flask_create, ['name'], obj=obj)
    assert result.exit_code == 0


def test_revision(tmpdir):
    flaskapp.root_path = str(tmpdir)
    obj = ScriptInfo(create_app=lambda info: flaskapp)
    result = runner.invoke(flask_revision, ['name'], obj=obj)
    assert result.exit_code == 0


def test_upgrade(tmpdir):
    flaskapp.root_path = str(tmpdir)
    obj = ScriptInfo(create_app=lambda info: flaskapp)
    result = runner.invoke(flask_upgrade, obj=obj)
    assert result.exit_code == 0


def test_downgrade(tmpdir):
    flaskapp.root_path = str(tmpdir)
    obj = ScriptInfo(create_app=lambda info: flaskapp)
    result = runner.invoke(flask_downgrade, obj=obj)
    assert result.exit_code == 0


def test_delete(tmpdir):
    flaskapp.root_path = str(tmpdir)
    obj = ScriptInfo(create_app=lambda info: flaskapp)
    result = runner.invoke(flask_delete, obj=obj)
    assert result.exit_code == 0
