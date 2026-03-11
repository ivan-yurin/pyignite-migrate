from pyignite.client import Client

from pyignite_migrate.config import Config
from pyignite_migrate.errors import MigrationError
from pyignite_migrate.operations import _context as ops_context
from pyignite_migrate.revision import Revision
from pyignite_migrate.script import ScriptDirectory


class MigrationContext:
    """Manages the lifecycle of a migration session."""

    def __init__(self, config: Config, script_dir: ScriptDirectory):
        self.config = config
        self.script_dir = script_dir
        self._client: Client | None = None

    def __enter__(self) -> "MigrationContext":
        self._connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self._close()

    def get_current_revision(self) -> str | None:
        self._ensure_version_table()

        cursor = self._get_client().sql(
            f"SELECT version_num FROM {self.config.version_table}",
            schema=self.config.schema,
            include_field_names=False,
        )

        rows = list(cursor)
        if not rows:
            return None

        result: str = rows[0][0]
        return result

    def stamp(self, revision: str | None) -> None:
        self._ensure_version_table()

        if revision is None:
            self._clear_current_revision()
        else:
            self._set_current_revision(revision)

    def run_upgrade(self, target: str | None = None) -> list[str]:
        self._ensure_version_table()

        rev_map = self.script_dir.get_revision_map()
        if rev_map.is_empty():
            return []

        if target is None:
            heads = rev_map.get_heads()
            if len(heads) > 1:
                raise MigrationError(
                    f"Multiple heads detected: {heads}. Specify a target revision."
                )
            target = heads[0]

        current = self.get_current_revision()
        if current == target:
            return []

        path = rev_map.get_upgrade_path(current, target)

        applied = []
        for rev in path:
            self._execute_revision(rev, direction="upgrade")
            self._set_current_revision(rev.revision)
            applied.append(rev.revision)

        return applied

    def run_downgrade(self, target: str | None = None) -> list[str]:
        self._ensure_version_table()

        current = self.get_current_revision()
        if current is None:
            return []

        rev_map = self.script_dir.get_revision_map()
        path = rev_map.get_downgrade_path(current, target)

        reverted = []
        for rev in path:
            self._execute_revision(rev, direction="downgrade")
            reverted.append(rev.revision)

        if target is None:
            self._clear_current_revision()
        else:
            self._set_current_revision(target)

        return reverted

    def _connect(self) -> None:
        self._client = Client()
        self._client.connect(self.config.hosts)

    def _close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _get_client(self) -> Client:
        if self._client is None:
            raise MigrationError("Not connected to Ignite cluster")
        return self._client

    def _ensure_version_table(self) -> None:
        cursor = self._get_client().sql(
            f"CREATE TABLE IF NOT EXISTS {self.config.version_table} ("
            f"  id INT,"
            f"  version_num CHAR(4),"
            f"  PRIMARY KEY (id)"
            f")",
            schema=self.config.schema,
        )
        list(cursor)

    def _set_current_revision(self, revision: str) -> None:
        cursor = self._get_client().sql(
            f"MERGE INTO {self.config.version_table} (id, version_num) VALUES (?, ?)",
            query_args=[1, revision],
            schema=self.config.schema,
        )
        list(cursor)

    def _clear_current_revision(self) -> None:
        cursor = self._get_client().sql(
            f"DELETE FROM {self.config.version_table}", schema=self.config.schema
        )
        list(cursor)

    def _execute_revision(self, rev: Revision, direction: str) -> None:
        func = getattr(rev.module, direction, None)
        if func is None:
            raise MigrationError(
                f"Revision {rev.revision} has no {direction}() function"
            )

        ops_context.configure(self._get_client(), self.config.schema)
        try:
            func()
        except Exception as e:
            raise MigrationError(
                f"Error running {direction}() for revision {rev.revision}: {e}"
            ) from e
        finally:
            ops_context.clear()
