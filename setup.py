from setuptools import setup
from codecs import open
from os import path

root_dir = path.abspath(path.dirname(__file__))

with open(path.join(root_dir, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

with open(path.join(root_dir, 'requirements.txt'), encoding='utf-8') as f:
    install_requires = list(map(str.strip, f.readlines()))


setup(
    name='peewee-moves',
    version='1.4.0',

    description='Simple and flexible migration manager for Peewee ORM.',
    long_description=long_description,

    url='https://github.com/timster/peewee-moves',

    author='Tim Shaffer',
    author_email='timshaffer@me.com',

    license='MIT',

    classifiers=[
        'Development Status :: 3 - Alpha',

        'Intended Audience :: Developers',
        'Topic :: Database :: Front-Ends',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],

    keywords='peewee orm database migration development',

    py_modules=['peewee_moves'],

    entry_points={
        'flask.commands': [
            'db = peewee_moves:command',
        ],
    },

    install_requires=install_requires,
)
