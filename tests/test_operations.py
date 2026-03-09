import pytest
from unittest.mock import MagicMock

from pyignite_migrate.errors import MigrationError
from pyignite_migrate.operations import Operations, _context


@pytest.fixture(autouse=True)
def clear_context():
    """Ensure context is cleared before and after each test."""
    _context.clear()
    yield
    _context.clear()


@pytest.fixture
def configured_op(mock_client):
    """Configure operations context with a mock client."""
    _context.configure(mock_client, "PUBLIC")
    return Operations()


class TestOperationsContext:
    def test_no_context_raises(self):
        op = Operations()
        with pytest.raises(
            MigrationError, match="No migration context"
        ):
            op.execute_sql("SELECT 1")

    def test_configure_and_use(self, mock_client):
        _context.configure(mock_client, "PUBLIC")
        op = Operations()
        op.execute_sql("SELECT 1")
        mock_client.sql.assert_called_once()

    def test_clear_then_raises(self, mock_client):
        _context.configure(mock_client, "PUBLIC")
        _context.clear()
        op = Operations()
        with pytest.raises(MigrationError):
            op.execute_sql("SELECT 1")


class TestExecuteSQL:
    def test_basic_query(self, configured_op, mock_client):
        configured_op.execute_sql("SELECT 1")
        mock_client.sql.assert_called_once_with(
            "SELECT 1",
            query_args=None,
            schema="PUBLIC",
            include_field_names=False,
        )

    def test_with_args(self, configured_op, mock_client):
        configured_op.execute_sql(
            "SELECT ?", query_args=[42]
        )
        mock_client.sql.assert_called_once_with(
            "SELECT ?",
            query_args=[42],
            schema="PUBLIC",
            include_field_names=False,
        )

    def test_schema_override(
        self, configured_op, mock_client
    ):
        configured_op.execute_sql(
            "SELECT 1", schema="OTHER"
        )
        mock_client.sql.assert_called_once_with(
            "SELECT 1",
            query_args=None,
            schema="OTHER",
            include_field_names=False,
        )


class TestCacheOperations:
    def test_create_cache(
        self, configured_op, mock_client
    ):
        configured_op.create_cache("my_cache")
        mock_client.create_cache.assert_called_once_with(
            "my_cache"
        )

    def test_create_cache_with_config(
        self, configured_op, mock_client
    ):
        configured_op.create_cache(
            "my_cache", config={"BACKUPS": 2}
        )
        mock_client.create_cache.assert_called_once()
        args = mock_client.create_cache.call_args[0][0]
        assert args["CACHE_NAME"] == "my_cache"
        assert args["BACKUPS"] == 2

    def test_destroy_cache(
        self, configured_op, mock_client
    ):
        configured_op.destroy_cache("my_cache")
        mock_client.get_cache.assert_called_once_with(
            "my_cache"
        )
        mock_client.get_cache.return_value.destroy.assert_called_once()
