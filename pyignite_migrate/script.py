import importlib.util
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from mako.template import Template

from pyignite_migrate.config import Config
from pyignite_migrate.errors import ScriptError, RevisionError
from pyignite_migrate.revision import Revision, RevisionMap

_MIGRATION_FILE_RE = re.compile(r"^([a-f0-9]+)_.*\.py$")


class ScriptDirectory:
    """Manages the migration scripts directory."""

    def __init__(self, config: Config):
        self.config = config
        self.dir = config.get_script_location_abs()
        self.versions_dir = os.path.join(self.dir, "versions")
        self._revision_map: Optional[RevisionMap] = None

    @property
    def env_py_path(self) -> str:
        return os.path.join(self.dir, "env.py")

    def get_revision_map(self) -> RevisionMap:
        if self._revision_map is None:
            revisions = self._load_revisions()
            self._revision_map = RevisionMap(revisions)
        return self._revision_map

    def invalidate(self) -> None:
        self._revision_map = None

    def _load_revisions(self) -> List[Revision]:
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
    def _load_module(filepath: str, filename: str) -> object:
        module_name = filename.replace(".py", "")
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None or spec.loader is None:
            raise ScriptError(f"Cannot create module spec for {filepath}")

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            raise ScriptError(
                f"Error loading migration {filepath}: {e}"
            ) from e

        return module

    @staticmethod
    def _module_to_revision(module: object, filepath: str) -> Revision:
        for attr in ("revision", "upgrade", "downgrade"):
            if not hasattr(module, attr):
                raise ScriptError(
                    f"Migration {filepath} is missing required attribute: {attr}"
                )

        revision_id = getattr(module, "revision")
        down_revision = getattr(module, "down_revision", None)
        description = getattr(module, "description", "")

        if not isinstance(revision_id, str) or not revision_id:
            raise ScriptError(
                f"Migration {filepath} has invalid 'revision' attribute"
            )

        return Revision(
            revision=revision_id,
            down_revision=down_revision,
            description=description,
            module=module,
        )

    def generate_revision(
        self,
        message: str,
        head: Optional[str] = None,
    ) -> str:
        rev_id = uuid.uuid4().hex[:12]

        if head is not None:
            down_revision = head
        else:
            rev_map = self.get_revision_map()
            if rev_map.is_empty():
                down_revision = None
            else:
                heads = rev_map.get_heads()
                if len(heads) > 1:
                    raise RevisionError(
                        f"Multiple heads found: {heads}. "
                        f"Specify --head to choose one."
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
            create_date=datetime.now(timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        )

        filename = f"{rev_id}_{slug}.py"
        output_path = os.path.join(self.versions_dir, filename)

        os.makedirs(self.versions_dir, exist_ok=True)

        with open(output_path, "w") as f:
            f.write(content)

        self.invalidate()

        return rev_id

    @staticmethod
    def _slugify(text: str) -> str:
        slug = text.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "_", slug)
        slug = slug.strip("_")
        return slug[:50]
