# Peewee Moves

A simple and flexible migration manager for [Peewee ORM](http://docs.peewee-orm.com/en/stable/).

## Requirements

## Installation

This package can be installed using pip:

    pip install peewee-moves

## Usage

Here's a quick teaser of what you can do with peewee-moves:

    $ ./manage.py db create -m app.models.Category
    created migration 0001_create_table_category

    $ ./manage.py db revision -n "do something"
    created migration 0002_do_something

    $ ./manage.py db upgrade
    0001_create_table_category: upgrade
    0002_do_something: upgrade

    $ ./manage.py db downgrade
    0002_do_something: downgrade

    $ ./manage.py db status
    0001_create_table_category: applied
    0002_do_something: pending

And if you're curious, here's what `0001_create_table_category.py` looks like. A migration was
automatically created based on the definition of the Category model!

```python
def upgrade(migrator):
    with migrator.create_table('category') as table:
        table.primary_key('id')
        table.integer('code', unique=True)
        table.string('name', max_length=250)


def downgrade(migrator):
    migrator.drop_table('category')
```

Check out the [Usage](USAGE.md) docuemnt for more details.

## Todo

- Better command line usage without Flask
- More documentation
- More examples
- Maybe some tests, if I get around to it

## Feedback

This package is very immature. If you have any comments, suggestions, feedback, or issues, please
feel free to send me a message or submit an issue on Github.

