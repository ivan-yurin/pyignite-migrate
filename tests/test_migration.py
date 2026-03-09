import pytest
from unittest.mock import MagicMock, patch, call

from pyignite_migrate.config import Config
from pyignite_migrate.errors import MigrationError
from pyignite_migrate.migration import MigrationContext
from pyignite_migrate.script import ScriptDirectory


@pytest.fixture
def migration_ctx(sample_migration_files, mock_client):
    """Create a MigrationContext with mock client."""
    config = Config.from_file(
        str(
            sample_migration_files / "pyignite_migrate.ini"
        )
    )
    script_dir = ScriptDirectory(config)

    with patch(
        "pyignite_migrate.migration.Client"
    ) as MockClient:
        MockClient.return_value = mock_client
        ctx = MigrationContext(config, script_dir)
        ctx.connect()
        yield ctx
        ctx.close()


class TestVersionTracking:
    def test_ensure_version_table(self, migration_ctx):
        migration_ctx.ensure_version_table()
        sql_calls = [
            c[0][0]
            for c in migration_ctx.client.sql.call_args_list
        ]
        assert any(
            "CREATE TABLE IF NOT EXISTS" in s
            for s in sql_calls
        )

    def test_get_current_revision_empty(
        self, migration_ctx
    ):
        rev = migration_ctx.get_current_revision()
        assert rev is None

    def test_get_current_revision_with_data(
        self, migration_ctx, mock_client
    ):
        # First call: CREATE TABLE IF NOT EXISTS -> empty
        # Second call: SELECT version_num -> return data
        mock_client.sql.side_effect = [
            iter([]),  # ensure_version_table
            iter([["abc123"]]),  # SELECT
        ]
        rev = migration_ctx.get_current_revision()
        assert rev == "abc123"

    def test_set_current_revision(
        self, migration_ctx, mock_client
    ):
        mock_client.sql.return_value = iter([])
        migration_ctx.set_current_revision("abc123")

        sql_calls = [
            c[0][0]
            for c in mock_client.sql.call_args_list
        ]
        assert any("DELETE FROM" in s for s in sql_calls)
        assert any("INSERT INTO" in s for s in sql_calls)

    def test_set_current_revision_to_none(
        self, migration_ctx, mock_client
    ):
        mock_client.sql.return_value = iter([])
        migration_ctx.set_current_revision(None)

        sql_calls = [
            c[0][0]
            for c in mock_client.sql.call_args_list
        ]
        assert any("DELETE FROM" in s for s in sql_calls)
        assert not any(
            "INSERT INTO" in s for s in sql_calls
        )


class TestRunUpgrade:
    def test_upgrade_from_base(
        self, migration_ctx, mock_client
    ):
        # Simulate: version table exists, no current version
        mock_client.sql.return_value = iter([])

        applied = migration_ctx.run_upgrade()
        assert len(applied) == 2
        assert applied[0] == "aaa111222333"
        assert applied[1] == "bbb444555666"

    def test_upgrade_already_at_head(
        self, migration_ctx, mock_client
    ):
        # First call: CREATE TABLE -> empty
        # Second call: SELECT -> current is head
        call_count = [0]

        def sql_side_effect(*args, **kwargs):
            call_count[0] += 1
            query = args[0]
            if "SELECT version_num" in query:
                return iter([["bbb444555666"]])
            return iter([])

        mock_client.sql.side_effect = sql_side_effect

        applied = migration_ctx.run_upgrade()
        assert applied == []

    def test_upgrade_empty_revisions(
        self, tmp_project, mock_client
    ):
        config = Config.from_file(
            str(tmp_project / "pyignite_migrate.ini")
        )
        script_dir = ScriptDirectory(config)

        with patch(
            "pyignite_migrate.migration.Client"
        ) as MockClient:
            MockClient.return_value = mock_client
            ctx = MigrationContext(config, script_dir)
            ctx.connect()
            mock_client.sql.return_value = iter([])
            applied = ctx.run_upgrade()
            assert applied == []
            ctx.close()


class TestRunDowngrade:
    def test_downgrade_to_base(
        self, migration_ctx, mock_client
    ):
        call_count = [0]

        def sql_side_effect(*args, **kwargs):
            call_count[0] += 1
            query = args[0]
            if "SELECT version_num" in query:
                return iter([["bbb444555666"]])
            return iter([])

        mock_client.sql.side_effect = sql_side_effect

        reverted = migration_ctx.run_downgrade(target=None)
        assert len(reverted) == 2
        assert reverted[0] == "bbb444555666"
        assert reverted[1] == "aaa111222333"

    def test_downgrade_already_at_base(
        self, migration_ctx, mock_client
    ):
        mock_client.sql.return_value = iter([])

        reverted = migration_ctx.run_downgrade(target=None)
        assert reverted == []


class TestContextManager:
    def test_context_manager(
        self, sample_migration_files, mock_client
    ):
        config = Config.from_file(
            str(
                sample_migration_files
                / "pyignite_migrate.ini"
            )
        )
        script_dir = ScriptDirectory(config)

        with patch(
            "pyignite_migrate.migration.Client"
        ) as MockClient:
            MockClient.return_value = mock_client
            with MigrationContext(
                config, script_dir
            ) as ctx:
                assert ctx._client is not None
            mock_client.close.assert_called_once()

    def test_not_connected_raises(
        self, sample_migration_files
    ):
        config = Config.from_file(
            str(
                sample_migration_files
                / "pyignite_migrate.ini"
            )
        )
        script_dir = ScriptDirectory(config)
        ctx = MigrationContext(config, script_dir)
        with pytest.raises(
            MigrationError, match="Not connected"
        ):
            _ = ctx.client
