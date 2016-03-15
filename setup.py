from setuptools import setup
from codecs import open
from os import path

root_dir = path.abspath(path.dirname(__file__))

with open(path.join(root_dir, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='peewee-moves',
    version='0.0.2',

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

    install_requires=['peewee>=2.8.0'],
)
