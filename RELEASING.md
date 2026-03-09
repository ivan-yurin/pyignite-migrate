# Releasing

## Release flow

### 1. Bump package version

Update `pyignite_migrate/__init__.py`:

```python
__version__ = "0.1.1"
```

`pyproject.toml` reads version dynamically from this file.

### 2. Commit and tag

```bash
git add .
git commit -m "Release 0.1.1"
git tag v0.1.1
git push origin main --tags
```

Tag must be `v<version>`. The workflow checks that tag and `__version__` match.
Also, tagged commit must be reachable from `origin/main`.

### 3. Automatic publish

Workflow [.github/workflows/publish-pypi.yml](.github/workflows/publish-pypi.yml)
will:
- build `sdist` and `wheel`
- run `twine check`
- publish to PyPI via OIDC

## Verify release

Check:
- PyPI page renders properly
- `pip install pyignite-migrate` works
- `pyignite-migrate --help` works
