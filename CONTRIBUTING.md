# Contributing

## Setup

1. Install [poetry](https://python-poetry.org/)
2. Install the dependencies:
   ```bash
   $ poetry install
   ```
3. Run the tests:
   ```bash
   $ poetry pytest
   ```

## Developer cheat sheet

Tag a release (simply replace ``1.x.x`` with the current version number):

```bash
$ git tag -a -m "Tagged version 1.x.x." v1.x.x
$ git push --tags
```

Upload release to PyPI:

```bash
rm -rf dist
poetry build
poetry twine check dist/*.whl
poetry twine upload --config-file ~/.pypirc dist/*.whl
```
