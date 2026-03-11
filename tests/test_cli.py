import os
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from pyignite_migrate.cli import cli
from pyignite_migrate.config import DEFAULT_CONFIG_FILENAME

from .conftest import (
    IGNITE_HOST,
    IGNITE_PORT,
    TEST_SCHEMA,
    TEST_VERSION_TABLE,
    requires_ignite,
    write_migration_file,
)

pytestmark = pytest.mark.usefixtures("clean_version_table")


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def cli_env(tmp_path):
    """CLI test environment: config .ini file + migrations directory."""
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "versions").mkdir()

    ini_path = tmp_path / DEFAULT_CONFIG_FILENAME
    ini_path.write_text(
        f"[pyignite_migrate]\n"
        f"hosts = {IGNITE_HOST}:{IGNITE_PORT}\n"
        f"script_location = migrations\n"
        f"schema = {TEST_SCHEMA}\n"
        f"version_table = {TEST_VERSION_TABLE}\n"
        f"file_template = ${{rev}}_${{slug}}\n"
    )

    return SimpleNamespace(
        ini_path=str(ini_path),
        versions_dir=str(migrations_dir / "versions"),
        tmp_path=tmp_path,
    )


def _invoke(runner, cli_env, args):
    return runner.invoke(cli, ["-c", cli_env.ini_path, *args])


@requires_ignite
class TestInit:
    def test_creates_migration_environment(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(cli, ["init"])

        assert result.exit_code == 0
        assert (tmp_path / DEFAULT_CONFIG_FILENAME).exists()
        assert (tmp_path / "migrations" / "env.py").exists()
        assert (tmp_path / "migrations" / "versions" / "__init__.py").exists()

    def test_creates_with_custom_directory(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(cli, ["init", "-d", "custom_migrations"])

        assert result.exit_code == 0
        assert (tmp_path / "custom_migrations" / "env.py").exists()
        assert (tmp_path / "custom_migrations" / "versions").is_dir()

    def test_skips_existing_config(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner.invoke(cli, ["init"])

        result = runner.invoke(cli, ["init"])

        assert result.exit_code == 0
        assert "already exists" in result.output


@requires_ignite
class TestRevision:
    def test_generates_first_revision(self, runner, cli_env):
        result = _invoke(runner, cli_env, ["revision"])

        assert result.exit_code == 0
        assert result.output == "Generated new revision: 0001\n"

        files = os.listdir(cli_env.versions_dir)
        assert files == ["0001_migration.py"]

    def test_generates_sequential_revision(self, runner, cli_env):
        _invoke(runner, cli_env, ["revision"])

        result = _invoke(runner, cli_env, ["revision"])

        assert result.exit_code == 0
        assert result.output == "Generated new revision: 0002\n"

        files = sorted(f for f in os.listdir(cli_env.versions_dir) if f.endswith(".py"))
        assert files == ["0001_migration.py", "0002_migration.py"]

    def test_generates_revision_with_message(self, runner, cli_env):
        result = _invoke(runner, cli_env, ["revision", "-m", "create users table"])

        assert result.exit_code == 0
        assert result.output == "Generated new revision: 0001\n"

        files = os.listdir(cli_env.versions_dir)
        assert files == ["0001_create_users_table.py"]


@requires_ignite
class TestUpgrade:
    def test_upgrade_to_head(self, runner, cli_env):
        write_migration_file(
            cli_env.versions_dir,
            revision="0001",
            down_revision=None,
            description="first",
        )
        write_migration_file(
            cli_env.versions_dir,
            revision="0002",
            down_revision="0001",
            description="second",
        )

        result = _invoke(runner, cli_env, ["upgrade"])

        assert result.exit_code == 0
        assert result.output == (
            "Applied 2 migration(s):\n  -> 0001: first\n  -> 0002: second\n"
        )

    def test_upgrade_to_specific_target(self, runner, cli_env):
        write_migration_file(
            cli_env.versions_dir,
            revision="0001",
            down_revision=None,
            description="first",
        )
        write_migration_file(
            cli_env.versions_dir,
            revision="0002",
            down_revision="0001",
            description="second",
        )
        write_migration_file(
            cli_env.versions_dir,
            revision="0003",
            down_revision="0002",
            description="third",
        )

        result = _invoke(runner, cli_env, ["upgrade", "0002"])

        assert result.exit_code == 0
        assert result.output == (
            "Applied 2 migration(s):\n  -> 0001: first\n  -> 0002: second\n"
        )

    def test_upgrade_noop(self, runner, cli_env):
        write_migration_file(
            cli_env.versions_dir,
            revision="0001",
            down_revision=None,
            description="first",
        )
        _invoke(runner, cli_env, ["upgrade"])

        result = _invoke(runner, cli_env, ["upgrade"])

        assert result.exit_code == 0
        assert result.output == "No migrations to apply.\n"

    def test_upgrade_error_in_migration(self, runner, cli_env):
        filepath = os.path.join(cli_env.versions_dir, "0001_bad.py")
        with open(filepath, "w") as f:
            f.write(
                "revision = '0001'\n"
                "down_revision = None\n"
                "description = 'bad'\n"
                "def upgrade(): raise RuntimeError('boom')\n"
                "def downgrade(): pass\n"
            )

        result = _invoke(runner, cli_env, ["upgrade"])

        assert result.exit_code == 1
        assert "Error running upgrade()" in result.output

    def test_upgrade_executes_sql(self, runner, cli_env, ignite_client):
        write_migration_file(
            cli_env.versions_dir,
            revision="0001",
            down_revision=None,
            description="create table",
            upgrade_body=(
                'op.execute_sql("CREATE TABLE __test_cli_upgrade '
                '(id INT, val INT, PRIMARY KEY(id))")'
            ),
        )

        result = _invoke(runner, cli_env, ["upgrade"])

        assert result.exit_code == 0

        cursor = ignite_client.sql(
            "SELECT * FROM __test_cli_upgrade",
            schema=TEST_SCHEMA,
            include_field_names=True,
        )
        rows = list(cursor)
        assert rows[0] == ["ID", "VAL"]

        # Cleanup
        sql = ignite_client.sql(
            "DROP TABLE IF EXISTS __test_cli_upgrade",
            schema=TEST_SCHEMA,
        )
        list(sql)


@requires_ignite
class TestDowngrade:
    def test_downgrade_to_base(self, runner, cli_env):
        write_migration_file(
            cli_env.versions_dir,
            revision="0001",
            down_revision=None,
            description="first",
        )
        write_migration_file(
            cli_env.versions_dir,
            revision="0002",
            down_revision="0001",
            description="second",
        )
        _invoke(runner, cli_env, ["upgrade"])

        result = _invoke(runner, cli_env, ["downgrade", "base"])

        assert result.exit_code == 0
        assert result.output == (
            "Reverted 2 migration(s):\n  <- 0002: second\n  <- 0001: first\n"
        )

    def test_downgrade_single_step(self, runner, cli_env):
        write_migration_file(
            cli_env.versions_dir,
            revision="0001",
            down_revision=None,
            description="first",
        )
        write_migration_file(
            cli_env.versions_dir,
            revision="0002",
            down_revision="0001",
            description="second",
        )
        _invoke(runner, cli_env, ["upgrade"])

        result = _invoke(runner, cli_env, ["downgrade", "--", "-1"])

        assert result.exit_code == 0
        assert result.output == "Reverted 1 migration(s):\n  <- 0002: second\n"

    def test_downgrade_to_specific_revision(self, runner, cli_env):
        write_migration_file(
            cli_env.versions_dir,
            revision="0001",
            down_revision=None,
            description="first",
        )
        write_migration_file(
            cli_env.versions_dir,
            revision="0002",
            down_revision="0001",
            description="second",
        )
        write_migration_file(
            cli_env.versions_dir,
            revision="0003",
            down_revision="0002",
            description="third",
        )
        _invoke(runner, cli_env, ["upgrade"])

        result = _invoke(runner, cli_env, ["downgrade", "0001"])

        assert result.exit_code == 0
        assert result.output == (
            "Reverted 2 migration(s):\n  <- 0003: third\n  <- 0002: second\n"
        )

    def test_downgrade_when_at_base(self, runner, cli_env):
        result = _invoke(runner, cli_env, ["downgrade", "base"])

        assert result.exit_code == 0
        assert result.output == "No migrations to revert.\n"


@requires_ignite
class TestCurrent:
    def test_current_no_migrations(self, runner, cli_env):
        result = _invoke(runner, cli_env, ["current"])

        assert result.exit_code == 0
        assert "(base)" in result.output

    def test_current_after_upgrade(self, runner, cli_env):
        write_migration_file(
            cli_env.versions_dir,
            revision="0001",
            down_revision=None,
            description="first",
        )
        write_migration_file(
            cli_env.versions_dir,
            revision="0002",
            down_revision="0001",
            description="second",
        )
        _invoke(runner, cli_env, ["upgrade", "0001"])

        result = _invoke(runner, cli_env, ["current"])

        assert result.exit_code == 0
        assert result.output == "Current revision: 0001\n  Description: first\n"

    def test_current_at_head(self, runner, cli_env):
        write_migration_file(
            cli_env.versions_dir,
            revision="0001",
            down_revision=None,
            description="only",
        )
        _invoke(runner, cli_env, ["upgrade"])

        result = _invoke(runner, cli_env, ["current"])

        assert result.exit_code == 0
        assert result.output == "Current revision: 0001 (head)\n  Description: only\n"


@requires_ignite
class TestHistory:
    def test_history_empty(self, runner, cli_env):
        result = _invoke(runner, cli_env, ["history"])

        assert result.exit_code == 0
        assert result.output == "No migration revisions found.\n"

    def test_history_with_revisions(self, runner, cli_env):
        write_migration_file(
            cli_env.versions_dir,
            revision="0001",
            down_revision=None,
            description="create users",
        )
        write_migration_file(
            cli_env.versions_dir,
            revision="0002",
            down_revision="0001",
            description="add index",
        )
        _invoke(runner, cli_env, ["upgrade"])

        result = _invoke(runner, cli_env, ["history"])

        assert result.exit_code == 0
        assert result.output == (
            "0001 -> (base) (base): create users\n"
            "0002 -> 0001 (head, current): add index\n"
        )


@requires_ignite
class TestHeads:
    def test_heads_empty(self, runner, cli_env):
        result = _invoke(runner, cli_env, ["heads"])

        assert result.exit_code == 0
        assert result.output == "No migration revisions found.\n"

    def test_heads_single(self, runner, cli_env):
        write_migration_file(
            cli_env.versions_dir,
            revision="0001",
            down_revision=None,
            description="first migration",
        )

        result = _invoke(runner, cli_env, ["heads"])

        assert result.exit_code == 0
        assert result.output == "Head revision(s) (1):\n  0001: first migration\n"


@requires_ignite
class TestStamp:
    def test_stamp_sets_revision(self, runner, cli_env):
        write_migration_file(
            cli_env.versions_dir,
            revision="0001",
            down_revision=None,
            description="first",
        )

        result = _invoke(runner, cli_env, ["stamp", "0001"])

        assert result.exit_code == 0
        assert result.output == "Stamped database as: 0001\n"

        current_result = _invoke(runner, cli_env, ["current"])
        assert "0001" in current_result.output

    def test_stamp_base_clears_revision(self, runner, cli_env):
        write_migration_file(
            cli_env.versions_dir,
            revision="0001",
            down_revision=None,
            description="first",
        )
        _invoke(runner, cli_env, ["stamp", "0001"])

        result = _invoke(runner, cli_env, ["stamp", "base"])

        assert result.exit_code == 0
        assert result.output == "Stamped database as: (base)\n"

        current_result = _invoke(runner, cli_env, ["current"])
        assert current_result.output == (
            "Current revision: (base) - no migrations applied\n"
        )
