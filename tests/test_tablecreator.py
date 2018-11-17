import peewee

from peewee_moves import TableCreator


def test_initialize():
    tc = TableCreator('awesome')

    assert issubclass(tc.model, peewee.Model)


def test_column():
    tc = TableCreator('awesome')
    tc.primary_key('id')
    tc.column('bare', 'col_bare')
    tc.column('biginteger', 'col_biginteger')
    tc.column('binary', 'col_binary')
    tc.column('blob', 'col_blob')
    tc.column('bool', 'col_bool')
    tc.column('char', 'col_char')
    tc.column('date', 'col_date')
    tc.column('datetime', 'col_datetime')
    tc.column('decimal', 'col_decimal')
    tc.column('double', 'col_double')
    tc.column('fixed', 'col_fixed')
    tc.column('float', 'col_float')
    tc.column('int', 'col_int')
    tc.column('integer', 'col_integer')
    tc.column('smallint', 'col_smallint')
    tc.column('smallinteger', 'col_smallinteger')
    tc.column('text', 'col_text')
    tc.column('time', 'col_time')
    tc.column('uuid', 'col_uuid')

    assert isinstance(tc.model.id, peewee.AutoField)
    assert isinstance(tc.model.col_bare, peewee.BareField)
    assert isinstance(tc.model.col_biginteger, peewee.BigIntegerField)
    assert isinstance(tc.model.col_binary, peewee.BlobField)
    assert isinstance(tc.model.col_blob, peewee.BlobField)
    assert isinstance(tc.model.col_bool, peewee.BooleanField)
    assert isinstance(tc.model.col_char, peewee.CharField)
    assert isinstance(tc.model.col_date, peewee.DateField)
    assert isinstance(tc.model.col_datetime, peewee.DateTimeField)
    assert isinstance(tc.model.col_decimal, peewee.DecimalField)
    assert isinstance(tc.model.col_double, peewee.DoubleField)
    assert isinstance(tc.model.col_fixed, peewee.CharField)
    assert isinstance(tc.model.col_float, peewee.FloatField)
    assert isinstance(tc.model.col_int, peewee.IntegerField)
    assert isinstance(tc.model.col_integer, peewee.IntegerField)
    assert isinstance(tc.model.col_smallint, peewee.SmallIntegerField)
    assert isinstance(tc.model.col_smallinteger, peewee.SmallIntegerField)
    assert isinstance(tc.model.col_text, peewee.TextField)
    assert isinstance(tc.model.col_time, peewee.TimeField)
    assert isinstance(tc.model.col_uuid, peewee.UUIDField)


def test_column_aliases():
    tc = TableCreator('awesome')
    tc.bare('col_bare')
    tc.biginteger('col_biginteger')
    tc.binary('col_binary')
    tc.blob('col_blob')
    tc.bool('col_bool')
    tc.char('col_char')
    tc.date('col_date')
    tc.datetime('col_datetime')
    tc.decimal('col_decimal')
    tc.double('col_double')
    tc.fixed('col_fixed')
    tc.float('col_float')
    tc.int('col_int')
    tc.integer('col_integer')
    tc.smallint('col_smallint')
    tc.smallinteger('col_smallinteger')
    tc.text('col_text')
    tc.time('col_time')
    tc.uuid('col_uuid')

    assert isinstance(tc.model.col_bare, peewee.BareField)
    assert isinstance(tc.model.col_biginteger, peewee.BigIntegerField)
    assert isinstance(tc.model.col_binary, peewee.BlobField)
    assert isinstance(tc.model.col_blob, peewee.BlobField)
    assert isinstance(tc.model.col_bool, peewee.BooleanField)
    assert isinstance(tc.model.col_char, peewee.CharField)
    assert isinstance(tc.model.col_date, peewee.DateField)
    assert isinstance(tc.model.col_datetime, peewee.DateTimeField)
    assert isinstance(tc.model.col_decimal, peewee.DecimalField)
    assert isinstance(tc.model.col_double, peewee.DoubleField)
    assert isinstance(tc.model.col_fixed, peewee.CharField)
    assert isinstance(tc.model.col_float, peewee.FloatField)
    assert isinstance(tc.model.col_int, peewee.IntegerField)
    assert isinstance(tc.model.col_integer, peewee.IntegerField)
    assert isinstance(tc.model.col_smallint, peewee.SmallIntegerField)
    assert isinstance(tc.model.col_smallinteger, peewee.SmallIntegerField)
    assert isinstance(tc.model.col_text, peewee.TextField)
    assert isinstance(tc.model.col_time, peewee.TimeField)
    assert isinstance(tc.model.col_uuid, peewee.UUIDField)


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
    tc.foreign_key('int', 'user_id', references='user.id', on_delete='cascade', on_update='cascade')

    assert isinstance(tc.model.user_id, peewee.ForeignKeyField)


def test_foreign_key_index():
    tc = TableCreator('awesome')
    tc.foreign_key('int', 'user_id', references='user.id', on_delete='cascade', on_update='cascade')
    tc.add_index(('user_id',), False)

    assert isinstance(tc.model.user_id, peewee.ForeignKeyField)
    assert tc.model._meta.indexes == [(('user_id',), False)]
