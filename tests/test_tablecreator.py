import pytest
import peewee

from peewee_moves import TableCreator


def test_initialize():
    tc = TableCreator('awesome')

    assert issubclass(tc.model, peewee.Model)


def test_column():
    tc = TableCreator('awesome')
    tc.primary_key('id')
    tc.column('char', 'name')

    assert isinstance(tc.model.id, peewee.PrimaryKeyField)
    assert isinstance(tc.model.name, peewee.Field)


def test_index():
    tc = TableCreator('awesome')
    tc.column('char', 'fname')
    tc.column('char', 'lname')
    tc.add_index(('fname', 'lname'), unique=True)

    assert tc.model._meta.indexes == [(('fname', 'lname'), True)]


def test_constraint():
    tc = TableCreator('awesome')
    tc.column('char', 'fname')

    const = peewee.SQL('fname not null')
    tc.add_constraint(const)

    assert tc.model._meta.constraints == [const]


def test_foreign_key():
    tc = TableCreator('awesome')
    tc.foreign_key('user_id', references='user.id', on_delete='cascade', on_update='cascade')

    const = 'FOREIGN KEY(user_id) REFERENCES user(id) ON DELETE cascade ON UPDATE cascade'
    assert tc.model._meta.constraints[0].value == const
