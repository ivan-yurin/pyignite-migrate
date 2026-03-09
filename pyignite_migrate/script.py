import importlib.util
import os
import re
import types
from datetime import datetime, timezone

from mako.template import Template

from pyignite_migrate.config import Config
from pyignite_migrate.errors import RevisionError, ScriptError
from pyignite_migrate.revision import Revision, RevisionMap

_MIGRATION_FILE_RE = re.compile(r"^([a-f0-9]+)_.*\.py$")


class ScriptDirectory:
    """Manages the migration scripts directory."""

    def __init__(self, config: Config):
        self.config = config
        self.dir = config.get_script_location_abs()
        self.versions_dir = os.path.join(self.dir, "versions")
        self._revision_map: RevisionMap | None = None

    def get_revision_map(self) -> RevisionMap:
        if self._revision_map is None:
            revisions = self._load_revisions()
            self._revision_map = RevisionMap(revisions)
        return self._revision_map

    def generate_revision(
        self,
        message: str,
        head: str | None = None,
    ) -> str:
        rev_map = self.get_revision_map()
        rev_id = self._next_revision_id(rev_map)

        if head is not None:
            down_revision = head
        else:
            if rev_map.is_empty():
                down_revision = None
            else:
                heads = rev_map.get_heads()
                if len(heads) > 1:
                    raise RevisionError(
                        f"Multiple heads found: {heads}. Specify --head to choose one."
                    )
                down_revision = heads[0]

        slug = self._slugify(message) if message else "migration"

        template_path = os.path.join(
            os.path.dirname(__file__), "templates", "script.py.mako"
        )
        template = Template(filename=template_path)
        content = template.render(
            revision=rev_id,
            down_revision=repr(down_revision),
            description=message or "",
            create_date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        )

        filename = f"{rev_id}_{slug}.py"
        output_path = os.path.join(self.versions_dir, filename)

        os.makedirs(self.versions_dir, exist_ok=True)

        with open(output_path, "w") as f:
            f.write(content)

        self._invalidate()

        return rev_id

    def _invalidate(self) -> None:
        self._revision_map = None

    def _next_revision_id(self, rev_map: RevisionMap) -> str:
        existing_ids = {rev.revision for rev in rev_map.get_all_revisions()}
        numeric_ids = [int(rev_id) for rev_id in existing_ids if rev_id.isdigit()]

        next_id = max(numeric_ids, default=0) + 1
        if next_id > 9999:
            raise ScriptError(
                "Cannot generate revision ID: maximum 4-digit "
                "revision number (9999) reached"
            )

        return f"{next_id:04d}"

    def _load_revisions(self) -> list[Revision]:
        if not os.path.isdir(self.versions_dir):
            return []

        revisions = []
        for filename in sorted(os.listdir(self.versions_dir)):
            match = _MIGRATION_FILE_RE.match(filename)
            if match is None:
                continue

            filepath = os.path.join(self.versions_dir, filename)
            if not os.path.isfile(filepath):
                continue

            module = self._load_module(filepath, filename)
            rev = self._module_to_revision(module, filepath)
            revisions.append(rev)

        return revisions

    @staticmethod
    def _load_module(filepath: str, filename: str) -> types.ModuleType:
        module_name = filename.replace(".py", "")
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        try:
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except Exception as e:
            raise ScriptError(f"Error loading migration {filepath}: {e}") from e

        return module

    @staticmethod
    def _module_to_revision(module: types.ModuleType, filepath: str) -> Revision:
        for attr in ("revision", "upgrade", "downgrade"):
            if not hasattr(module, attr):
                raise ScriptError(
                    f"Migration {filepath} is missing required attribute: {attr}"
                )

        revision_id = module.revision
        down_revision = getattr(module, "down_revision", None)
        description = getattr(module, "description", "")

        if not isinstance(revision_id, str) or not revision_id:
            raise ScriptError(f"Migration {filepath} has invalid 'revision' attribute")

        return Revision(
            revision=revision_id,
            down_revision=down_revision,
            description=description,
            module=module,
        )

    @staticmethod
    def _slugify(text: str) -> str:
        slug = text.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "_", slug)
        slug = slug.strip("_")
        return slug[:50]
