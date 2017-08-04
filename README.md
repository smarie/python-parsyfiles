# python simple file collection parsing framework (parsyfiles)

[![Build Status](https://travis-ci.org/smarie/python-parsyfiles.svg?branch=master)](https://travis-ci.org/smarie/python-parsyfiles) [![Tests Status](https://smarie.github.io/python-parsyfiles/junit/junit-badge.svg?dummy=8484744)](https://smarie.github.io/python-parsyfiles/junit/report.html) [![codecov](https://codecov.io/gh/smarie/python-parsyfiles/branch/master/graph/badge.svg)](https://codecov.io/gh/smarie/python-parsyfiles) [![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://smarie.github.io/python-parsyfiles/) [![PyPI](https://img.shields.io/badge/PyPI-parsyfiles-blue.svg)](https://pypi.python.org/pypi/parsyfiles/)

Project page : [https://smarie.github.io/python-parsyfiles/](https://smarie.github.io/python-parsyfiles/)

## What's new

* Travis and codecov integration
* Doc now generated from markdown using [mkdocs](http://www.mkdocs.org/)

## Want to contribute ?

Contributions are welcome ! Simply fork this project on github, commit your contributions, and create_not_able_to_convert pull requests.

Here is a non-exhaustive list of interesting open topics: [https://github.com/smarie/python-parsyfiles/issues](https://github.com/smarie/python-parsyfiles/issues)

## Running the tests

This project uses `pytest`. 

```bash
pytest -v parsyfiles/tests/
```

You may need to install requirements for setup beforehand, using 

```bash
pip install -r ci_tools/requirements-test.txt
```
## Generating the documentation page

This project uses `mkdocs` to generate its documentation page. Therefore building a local copy of the doc page may be done using:

```bash
mkdocs build
```

You may need to install requirements for doc beforehand, using 

```bash
pip install -r ci_tools/requirements-doc.txt
```

## Generating the test reports

The following commands generate the html test report and the associated badge. 

```bash
pytest --junitxml=junit.xml -v parsyfiles/tests/
ant -f ci_tools/generate-junit-html.xml
python ci_tools/generate-junit-badge.py
```

### PyPI Releasing memo

This project is now automatically deployed to PyPI when a tag is created. Anyway, for manual deployment we can use:

```bash
twine upload dist/* -r pypitest
twine upload dist/*
```
