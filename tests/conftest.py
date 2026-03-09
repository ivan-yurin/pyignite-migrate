import os
import textwrap

import pytest
from pyignite.client import Client

IGNITE_HOST = os.environ.get("PYIGNITE_TEST_HOST", "127.0.0.1")
IGNITE_PORT = int(os.environ.get("PYIGNITE_TEST_PORT", "10800"))

TEST_VERSION_TABLE = "__test_pyignite_migrate_version"
TEST_SCHEMA = "PUBLIC"


def _ignite_available() -> bool:
    try:
        client = Client()
        client.connect([(IGNITE_HOST, IGNITE_PORT)])
        client.close()
        return True
    except Exception:
        return False


requires_ignite = pytest.mark.skipif(
    not _ignite_available(),
    reason=f"Apache Ignite not available at {IGNITE_HOST}:{IGNITE_PORT}",
)


@pytest.fixture()
def ignite_client():
    """Raw pyignite Client connected to the test cluster."""
    client = Client()
    client.connect([(IGNITE_HOST, IGNITE_PORT)])
    yield client
    client.close()


@pytest.fixture()
def clean_version_table(ignite_client):
    """Drop the test version table before and after each test."""
    _drop_table(ignite_client, TEST_VERSION_TABLE)
    yield
    _drop_table(ignite_client, TEST_VERSION_TABLE)


def _drop_table(client: Client, table: str) -> None:
    cursor = client.sql(
        f"DROP TABLE IF EXISTS {table}",
        schema=TEST_SCHEMA,
    )
    list(cursor)


def write_migration_file(
    versions_dir: str,
    revision: str,
    down_revision: str | None,
    description: str = "",
    upgrade_body: str = "pass",
    downgrade_body: str = "pass",
) -> str:
    """Write a migration .py file to the versions directory and return its path."""
    slug = description.lower().replace(" ", "_")[:30] or "migration"
    filename = f"{revision}_{slug}.py"
    filepath = os.path.join(versions_dir, filename)

    down_rev_repr = repr(down_revision)
    content = textwrap.dedent(f"""\
        from pyignite_migrate.operations import op

        revision = {revision!r}
        down_revision = {down_rev_repr}
        description = {description!r}

        def upgrade():
            {upgrade_body}

        def downgrade():
            {downgrade_body}
    """)
    with open(filepath, "w") as f:
        f.write(content)
    return filepath
