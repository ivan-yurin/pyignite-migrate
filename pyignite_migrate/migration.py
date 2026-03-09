from typing import Optional, List

from pyignite.client import Client

from pyignite_migrate.config import Config
from pyignite_migrate.errors import MigrationError
from pyignite_migrate.operations import _context as ops_context
from pyignite_migrate.revision import Revision, RevisionMap
from pyignite_migrate.script import ScriptDirectory


class MigrationContext:
    """Manages the lifecycle of a migration session."""

    def __init__(self, config: Config, script_dir: ScriptDirectory):
        self.config = config
        self.script_dir = script_dir
        self._client: Optional[Client] = None

    def connect(self) -> None:
        self._client = Client()
        self._client.connect(self.config.hosts)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    @property
    def client(self) -> Client:
        if self._client is None:
            raise MigrationError("Not connected to Ignite cluster")
        return self._client

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def ensure_version_table(self) -> None:
        table = self.config.version_table
        schema = self.config.schema
        sql = (
            f"CREATE TABLE IF NOT EXISTS {table} ("
            f"  version_num VARCHAR(128),"
            f"  PRIMARY KEY (version_num)"
            f")"
        )
        cursor = self.client.sql(sql, schema=schema)
        list(cursor)

    def get_current_revision(self) -> Optional[str]:
        self.ensure_version_table()
        table = self.config.version_table
        schema = self.config.schema

        cursor = self.client.sql(
            f"SELECT version_num FROM {table}",
            schema=schema,
            include_field_names=False,
        )
        rows = list(cursor)
        if not rows:
            return None
        return rows[0][0]

    def set_current_revision(self, revision: Optional[str]) -> None:
        table = self.config.version_table
        schema = self.config.schema

        cursor = self.client.sql(f"DELETE FROM {table}", schema=schema)
        list(cursor)

        if revision is not None:
            cursor = self.client.sql(
                f"INSERT INTO {table} (version_num) VALUES (?)",
                query_args=[revision],
                schema=schema,
            )
            list(cursor)

    def stamp(self, revision: Optional[str]) -> None:
        self.ensure_version_table()
        self.set_current_revision(revision)

    def run_upgrade(self, target: Optional[str] = None) -> List[str]:
        self.ensure_version_table()
        rev_map = self.script_dir.get_revision_map()
        current = self.get_current_revision()

        if rev_map.is_empty():
            return []

        if target is None:
            heads = rev_map.get_heads()
            if len(heads) > 1:
                raise MigrationError(
                    f"Multiple heads detected: {heads}. "
                    f"Specify a target revision."
                )
            target = heads[0]

        if current == target:
            return []

        path = rev_map.get_upgrade_path(current, target)

        applied = []
        for rev in path:
            self._execute_revision(rev, direction="upgrade")
            self.set_current_revision(rev.revision)
            applied.append(rev.revision)

        return applied

    def run_downgrade(self, target: Optional[str] = None) -> List[str]:
        self.ensure_version_table()
        rev_map = self.script_dir.get_revision_map()
        current = self.get_current_revision()

        if current is None:
            return []

        path = rev_map.get_downgrade_path(current, target)

        reverted = []
        for rev in path:
            self._execute_revision(rev, direction="downgrade")
            reverted.append(rev.revision)

        self.set_current_revision(target)

        return reverted

    def _execute_revision(self, rev: Revision, direction: str) -> None:
        func = getattr(rev.module, direction, None)
        if func is None:
            raise MigrationError(
                f"Revision {rev.revision} has no {direction}() function"
            )

        ops_context.configure(self.client, self.config.schema)
        try:
            func()
        except Exception as e:
            raise MigrationError(
                f"Error running {direction}() for revision "
                f"{rev.revision}: {e}"
            ) from e
        finally:
            ops_context.clear()
