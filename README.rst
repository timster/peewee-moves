Peewee Moves
############

A simple and flexible migration manager for `Peewee ORM <http://docs.peewee-orm.com/>`_.

.. image:: http://img.shields.io/travis/timster/peewee-moves.svg?style=flat-square
    :target: http://travis-ci.org/timster/peewee-moves
    :alt: Build Status

.. image:: http://img.shields.io/coveralls/timster/peewee-moves.svg?style=flat-square
    :target: https://coveralls.io/r/timster/peewee-moves
    :alt: Code Coverage

.. image:: http://img.shields.io/pypi/v/peewee-moves.svg?style=flat-square
    :target: https://pypi.python.org/pypi/peewee-moves
    :alt: Version

.. image:: http://img.shields.io/pypi/dm/peewee-moves.svg?style=flat-square
    :target: https://pypi.python.org/pypi/peewee-moves
    :alt: Downloads

Requirements
============

* python >= 3.3
* peewee >= 2.8.0

Installation
============

This package can be installed using pip:

::

    pip install peewee-moves

Usage
=====

Here's a quick teaser of what you can do with peewee-moves:

.. code:: console

    $ ./manage.py db create -m app.models.Category
    INFO: created migration 0001_create_table_category

    $ ./manage.py db revision -n "do something"
    INFO: created migration 0002_do_something

    $ ./manage.py db upgrade
    INFO: 0001_create_table_category: upgrade
    INFO: 0002_do_something: upgrade

    $ ./manage.py db downgrade
    INFO: 0002_do_something: downgrade

    $ ./manage.py db status
    INFO: 0001_create_table_category: applied
    INFO: 0002_do_something: pending

And if you're curious, here's what `0001_create_table_category.py` looks like. A migration was
automatically created based on the definition of the Category model!

.. code:: python

    def upgrade(migrator):
        with migrator.create_table('category') as table:
            table.primary_key('id')
            table.integer('code', unique=True)
            table.string('name', max_length=250)

    def downgrade(migrator):
        migrator.drop_table('category')

Check out the `Usage documentation <USAGE.rst>`_ for more details.

Todo
====

* Command line usage without Flask
* More documentation
* More examples
* More tests

Feedback
========

This package is very immature. If you have any comments, suggestions, feedback, or issues, please
feel free to send me a message or submit an issue on Github.
