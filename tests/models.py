import peewee

database = peewee.SqliteDatabase(':memory:')


class NotModel:
    pass


class BasicFields(peewee.Model):
    field1 = peewee.CharField()
    field2 = peewee.CharField()
    field3 = peewee.CharField()

    class Meta:
        database = database
        indexes = (
            (('field1', 'field2'), True),
            (('field3',), False),
        )


class Organization(peewee.Model):
    name = peewee.CharField(null=False)

    class Meta:
        database = database


class Person(peewee.Model):
    name = peewee.CharField(null=False, max_length=5, unique=True)

    class Meta:
        database = database


class ComplexPerson(peewee.Model):
    name = peewee.CharField(null=False, max_length=5, unique=True)

    organization = peewee.ForeignKeyField(Organization)

    class Meta:
        database = database
        constraints = (
            peewee.SQL('const1 fake'),
            peewee.Check('const2 fake'),
        )


class HasCheckConstraint(peewee.Model):
    name = peewee.CharField(null=False, constraints=[peewee.Check("name in ('tim', 'bob')")])

    class Meta:
        database = database


class RelatesToName(peewee.Model):
    person = peewee.ForeignKeyField(
        Person,
        db_column="person_name",
        to_field='name',
        on_update='CASCADE',
        on_delete='SET NULL')

    class Meta:
        database = database
