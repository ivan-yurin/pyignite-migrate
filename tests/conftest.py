from unittest.mock import MagicMock

import pytest

from pyignite_migrate.config import Config


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with config and migrations."""
    config_content = """\
[pyignite_migrate]
hosts = 127.0.0.1:10800
script_location = migrations
schema = PUBLIC
version_table = __pyignite_migrate_version
"""
    config_path = tmp_path / "pyignite_migrate.ini"
    config_path.write_text(config_content)

    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    versions_dir = migrations_dir / "versions"
    versions_dir.mkdir()
    (versions_dir / "__init__.py").write_text("")

    return tmp_path


@pytest.fixture
def mock_client():
    """Create a mock pyignite Client."""
    client = MagicMock()
    client.sql.return_value = iter([])
    return client


@pytest.fixture
def sample_config(tmp_project):
    """Load config from tmp_project."""
    return Config.from_file(str(tmp_project / "pyignite_migrate.ini"))


@pytest.fixture
def sample_migration_files(tmp_project):
    """Create sample migration files in the tmp project."""
    versions_dir = tmp_project / "migrations" / "versions"

    (versions_dir / "aaa111222333_create_users.py").write_text(
        """\
from pyignite_migrate.operations import op

revision = "aaa111222333"
down_revision = None
description = "create users"


def upgrade():
    op.execute_sql(
        "CREATE TABLE users (id INT, PRIMARY KEY (id))"
    )


def downgrade():
    op.execute_sql("DROP TABLE IF EXISTS users")
"""
    )

    (versions_dir / "bbb444555666_add_email.py").write_text(
        """\
from pyignite_migrate.operations import op

revision = "bbb444555666"
down_revision = "aaa111222333"
description = "add email"


def upgrade():
    op.execute_sql(
        "ALTER TABLE users ADD COLUMN email VARCHAR(255)"
    )


def downgrade():
    op.execute_sql(
        "ALTER TABLE users DROP COLUMN email"
    )
"""
    )

    return tmp_project
