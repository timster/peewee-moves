.PHONY: clean dist docs install lint release test

help:
	@echo "clean    remove all build, test, coverage, and Python artifacts"
	@echo "dist     create a package"
	@echo "install  install the package to the active Python's site-packages"
	@echo "release  package and upload a release"
	@echo "test     run tests quickly with the default Python"

clean:
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	rm -fr docs/_build/
	rm -fr .coverage htmlcov/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

install: clean
	python setup.py install

dist: clean
	python setup.py sdist
	python setup.py bdist_wheel

release: clean
	python setup.py sdist upload -r pypi
	python setup.py bdist_wheel upload -r pypi

test:
	py.test

testcov:
	py.test --cov=peewee_moves.py
	coverage html --directory=.covhtml
	open .covhtml/index.html
