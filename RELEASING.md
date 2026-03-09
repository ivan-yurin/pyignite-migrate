# Releasing

This project publishes to PyPI via GitHub Actions and OpenID Connect (OIDC)
Trusted Publisher.

## One-time setup

### 1. GitHub environment `pypi`

Create environment `pypi` in repository settings.

Recommended settings:
- Require manual approval for this environment.
- Deployment branches and tags: `main` and `v*`.
- Disable admin bypass if you want strict approvals.

### 2. Trusted Publisher in PyPI

In PyPI, configure Trusted Publisher with:
- Owner: `ivan-yurin`
- Repository: `pyignite-migrate`
- Workflow name: `publish-pypi.yml`
- Environment name: `pypi`

For a brand-new project, create a pending publisher with the same values.

## Release flow

### 1. Bump package version

Update `pyignite_migrate/__init__.py`:

```python
__version__ = "0.1.1"
```

Version is read dynamically from this file by `pyproject.toml`.

### 2. Commit and create tag

```bash
git add .
git commit -m "Release 0.1.1"
git tag v0.1.1
git push origin main --tags
```

Requirements:
- Tag format: `v<version>`.
- Tag value must match `__version__`.
- Tagged commit must be reachable from `origin/main`.

### 3. Automatic workflow

Workflow [.github/workflows/publish-pypi.yml](.github/workflows/publish-pypi.yml)
runs three jobs:
- `check`: `ruff`, `mypy`, and `pytest` on Python 3.10, 3.11, 3.12, 3.13, 3.14.
- `build`: builds `sdist` and `wheel`, then runs `twine check`.
- `publish`: uploads artifacts to PyPI via OIDC.

## Verify release

Check:
- PyPI page renders properly.
- `pip install pyignite-migrate` works.
- `pyignite-migrate --help` works.
