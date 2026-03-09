# pyignite-migrate

Database migration tool for Apache Ignite.

## Installation

```bash
pip install pyignite-migrate
```

or with `uv`:

```bash
uv add pyignite-migrate
```

## Quick Start

### 1. Initialize migration environment

```bash
pyignite-migrate init
```

This creates:
- `pyignite_migrate.ini` — configuration file
- `migrations/` — directory with `env.py` and `versions/`

### 2. Configure connection

Edit `pyignite_migrate.ini`:

```ini
[pyignite_migrate]
hosts = 127.0.0.1:10800
script_location = migrations
schema = PUBLIC
```

### 3. Create a migration

```bash
pyignite-migrate revision -m "create users table"
```

Edit the generated file in `migrations/versions/`:

```python
from pyignite_migrate.operations import op

revision = '0001'
down_revision = None
description = 'create users table'


def upgrade():
    op.execute_sql("""
        CREATE TABLE users (
            id INT,
            name VARCHAR(100),
            email VARCHAR(255),
            PRIMARY KEY (id)
        )
    """)
    op.execute_sql("CREATE INDEX idx_users_email ON users (email)")


def downgrade():
    op.execute_sql("DROP INDEX IF EXISTS idx_users_email")
    op.execute_sql("DROP TABLE IF EXISTS users")
```

### 4. Apply migrations

```bash
pyignite-migrate upgrade head
```

### 5. Rollback

```bash
pyignite-migrate downgrade -1    # one step back
pyignite-migrate downgrade base  # revert all
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `init` | Initialize migration environment |
| `revision -m "msg"` | Create a new migration |
| `upgrade [head\|rev_id]` | Apply migrations |
| `downgrade <base\|-N\|rev_id>` | Revert migrations |
| `current` | Show current revision |
| `history` | Show migration history |
| `heads` | Show head revision(s) |
| `stamp <rev_id\|base>` | Set version without running migrations |

## Available Operations

```python
from pyignite_migrate.operations import op

# SQL
op.execute_sql(query, query_args=None, schema=None)

# Cache management
op.create_cache(name, config=None)
op.destroy_cache(name)
```

## Configuration

`pyignite_migrate.ini`:

```ini
[pyignite_migrate]
# Comma-separated host:port pairs
hosts = 127.0.0.1:10800

# Path to migration scripts (relative to this file)
script_location = migrations

# SQL schema
schema = PUBLIC

# Version tracking table name
version_table = __pyignite_migrate_version
```

## Requirements

- Python >= 3.10
- Apache Ignite with thin client protocol

## Development

```bash
uv sync
uv run pytest tests/ -v
uv run ruff check .
uv run ruff format --check .
uv run mypy pyignite_migrate/
```

## Release

See [RELEASING.md](https://github.com/ivan-yurin/pyignite-migrate/blob/main/RELEASING.md)
for build and PyPI publishing steps.

## License

Apache License 2.0
