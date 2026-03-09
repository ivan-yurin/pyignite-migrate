from collections.abc import Sequence
from typing import Any

from pyignite_migrate.errors import MigrationError


class _OperationsContext:
    """Holds the current migration execution context."""

    def __init__(self) -> None:
        self._client: Any = None
        self._schema: str = "PUBLIC"

    def configure(self, client: Any, schema: str = "PUBLIC") -> None:
        self._client = client
        self._schema = schema

    def clear(self) -> None:
        self._client = None

    @property
    def client(self) -> Any:
        if self._client is None:
            raise MigrationError(
                "No migration context is active. Operations can only be "
                "called inside upgrade() or downgrade() functions."
            )
        return self._client

    @property
    def schema(self) -> str:
        return self._schema


_context = _OperationsContext()


class Operations:
    """
    Proxy object providing Ignite-specific migration operations.

    Imported by migration scripts as:
        from pyignite_migrate.operations import op
    """

    def execute_sql(
        self,
        query: str,
        query_args: Sequence | None = None,
        schema: str | None = None,
    ) -> list[Any]:
        target_schema = schema or _context.schema
        cursor = _context.client.sql(
            query,
            query_args=query_args,
            schema=target_schema,
            include_field_names=False,
        )
        return list(cursor)

    def create_cache(
        self,
        name: str,
        config: dict[str, Any] | None = None,
    ) -> None:
        if config is not None:
            if "CACHE_NAME" not in config:
                settings = {**config, "CACHE_NAME": name}
            else:
                settings = config
            _context.client.create_cache(settings)
        else:
            _context.client.create_cache(name)

    def destroy_cache(self, name: str) -> None:
        cache = _context.client.get_cache(name)
        cache.destroy()


op = Operations()
