import os
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from pyignite_migrate.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestInitCommand:
    def test_init_creates_structure(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0
            assert os.path.isfile("pyignite_migrate.ini")
            assert os.path.isdir("migrations/versions")
            assert os.path.isfile("migrations/env.py")

    def test_init_custom_directory(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["init", "-d", "my_migrations"])
            assert result.exit_code == 0
            assert os.path.isdir("my_migrations/versions")
            assert os.path.isfile("my_migrations/env.py")

    def test_init_does_not_overwrite(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["init"])
            result = runner.invoke(cli, ["init"])
            assert result.exit_code == 0
            assert "already exists" in result.output


class TestRevisionCommand:
    def test_revision_creates_file(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["init"])
            result = runner.invoke(
                cli,
                ["revision", "-m", "create users"],
            )
            assert result.exit_code == 0
            assert "Generated new revision" in result.output

            versions = os.listdir("migrations/versions")
            migration_files = [
                f for f in versions if f.endswith(".py") and f != "__init__.py"
            ]
            assert len(migration_files) == 1
            assert "create_users" in migration_files[0]

    def test_revision_chain(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["init"])
            runner.invoke(
                cli,
                ["revision", "-m", "first"],
            )
            result = runner.invoke(
                cli,
                ["revision", "-m", "second"],
            )
            assert result.exit_code == 0

            versions = os.listdir("migrations/versions")
            migration_files = [
                f for f in versions if f.endswith(".py") and f != "__init__.py"
            ]
            assert len(migration_files) == 2


class TestHistoryCommand:
    def test_history_empty(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["init"])
            result = runner.invoke(cli, ["history"])
            assert result.exit_code == 0
            assert "No migration revisions" in result.output

    def test_history_with_revisions(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["init"])
            runner.invoke(
                cli,
                ["revision", "-m", "create users"],
            )
            runner.invoke(
                cli,
                ["revision", "-m", "add email"],
            )
            result = runner.invoke(cli, ["history"])
            assert result.exit_code == 0
            assert "create users" in result.output
            assert "add email" in result.output


class TestHeadsCommand:
    def test_heads_empty(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["init"])
            result = runner.invoke(cli, ["heads"])
            assert result.exit_code == 0
            assert "No migration revisions" in result.output

    def test_heads_with_revisions(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["init"])
            runner.invoke(
                cli,
                ["revision", "-m", "create users"],
            )
            result = runner.invoke(cli, ["heads"])
            assert result.exit_code == 0
            assert "Head revision(s)" in result.output
            assert "create users" in result.output


class TestUpgradeCommand:
    def test_upgrade_with_mock(self, runner, tmp_path):
        mock_client = MagicMock()
        mock_client.sql.return_value = iter([])

        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["init"])
            runner.invoke(
                cli,
                ["revision", "-m", "create users"],
            )

            with patch("pyignite_migrate.migration.Client") as MockClient:
                MockClient.return_value = mock_client
                result = runner.invoke(cli, ["upgrade"])
                assert result.exit_code == 0
                assert "Applied 1 migration" in result.output


class TestDowngradeCommand:
    def test_downgrade_base_with_mock(self, runner, tmp_path):
        mock_client = MagicMock()
        call_count = [0]

        def sql_side_effect(*args, **kwargs):
            call_count[0] += 1
            query = args[0]
            if "SELECT version_num" in query:
                return iter([])
            return iter([])

        mock_client.sql.side_effect = sql_side_effect

        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["init"])
            runner.invoke(
                cli,
                ["revision", "-m", "create users"],
            )

            with patch("pyignite_migrate.migration.Client") as MockClient:
                MockClient.return_value = mock_client
                result = runner.invoke(cli, ["downgrade", "base"])
                assert result.exit_code == 0


class TestCurrentCommand:
    def test_current_at_base(self, runner, tmp_path):
        mock_client = MagicMock()
        mock_client.sql.return_value = iter([])

        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["init"])

            with patch("pyignite_migrate.migration.Client") as MockClient:
                MockClient.return_value = mock_client
                result = runner.invoke(cli, ["current"])
                assert result.exit_code == 0
                assert "(base)" in result.output


class TestStampCommand:
    def test_stamp_with_mock(self, runner, tmp_path):
        mock_client = MagicMock()
        mock_client.sql.return_value = iter([])

        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["init"])
            runner.invoke(
                cli,
                ["revision", "-m", "create users"],
            )

            # Get the revision ID
            versions = os.listdir("migrations/versions")
            migration_file = [
                f for f in versions if f.endswith(".py") and f != "__init__.py"
            ][0]
            rev_id = migration_file.split("_")[0]

            with patch("pyignite_migrate.migration.Client") as MockClient:
                MockClient.return_value = mock_client
                result = runner.invoke(cli, ["stamp", rev_id])
                assert result.exit_code == 0
                assert "Stamped" in result.output

    def test_stamp_base(self, runner, tmp_path):
        mock_client = MagicMock()
        mock_client.sql.return_value = iter([])

        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["init"])

            with patch("pyignite_migrate.migration.Client") as MockClient:
                MockClient.return_value = mock_client
                result = runner.invoke(cli, ["stamp", "base"])
                assert result.exit_code == 0
                assert "Stamped database as: (base)" in result.output
