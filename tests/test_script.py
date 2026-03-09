import os

import pytest

from pyignite_migrate.config import Config
from pyignite_migrate.errors import ScriptError
from pyignite_migrate.script import ScriptDirectory


class TestScriptDirectory:
    def test_empty_versions(self, tmp_project):
        config = Config.from_file(
            str(tmp_project / "pyignite_migrate.ini")
        )
        sd = ScriptDirectory(config)
        rev_map = sd.get_revision_map()
        assert rev_map.is_empty()

    def test_load_migration_files(
        self, sample_migration_files
    ):
        config = Config.from_file(
            str(
                sample_migration_files
                / "pyignite_migrate.ini"
            )
        )
        sd = ScriptDirectory(config)
        rev_map = sd.get_revision_map()
        assert not rev_map.is_empty()
        assert rev_map.get_heads() == ["bbb444555666"]
        assert rev_map.get_bases() == ["aaa111222333"]

    def test_generate_revision_first(self, tmp_project):
        config = Config.from_file(
            str(tmp_project / "pyignite_migrate.ini")
        )
        sd = ScriptDirectory(config)
        rev_id = sd.generate_revision("create users table")
        assert len(rev_id) == 12

        versions_dir = tmp_project / "migrations" / "versions"
        files = [
            f
            for f in os.listdir(versions_dir)
            if f.endswith(".py") and f != "__init__.py"
        ]
        assert len(files) == 1
        assert files[0].startswith(rev_id)
        assert "create_users_table" in files[0]

    def test_generate_revision_chained(
        self, sample_migration_files
    ):
        config = Config.from_file(
            str(
                sample_migration_files
                / "pyignite_migrate.ini"
            )
        )
        sd = ScriptDirectory(config)
        rev_id = sd.generate_revision("add phone column")

        rev_map = sd.get_revision_map()
        rev = rev_map.get_revision(rev_id)
        assert rev.down_revision == "bbb444555666"

    def test_invalidate_clears_cache(self, tmp_project):
        config = Config.from_file(
            str(tmp_project / "pyignite_migrate.ini")
        )
        sd = ScriptDirectory(config)
        rev_map1 = sd.get_revision_map()
        assert rev_map1.is_empty()

        sd.generate_revision("test")
        rev_map2 = sd.get_revision_map()
        assert not rev_map2.is_empty()

    def test_missing_versions_dir(self, tmp_path):
        config_content = """\
[pyignite_migrate]
hosts = 127.0.0.1:10800
script_location = nonexistent
"""
        config_path = tmp_path / "pyignite_migrate.ini"
        config_path.write_text(config_content)
        config = Config.from_file(str(config_path))
        sd = ScriptDirectory(config)
        rev_map = sd.get_revision_map()
        assert rev_map.is_empty()


class TestSlugify:
    def test_basic(self):
        assert (
            ScriptDirectory._slugify("Create users table")
            == "create_users_table"
        )

    def test_special_chars(self):
        assert (
            ScriptDirectory._slugify("add email@column!")
            == "add_email_column"
        )

    def test_truncation(self):
        long_text = "a" * 100
        slug = ScriptDirectory._slugify(long_text)
        assert len(slug) <= 50

    def test_strips_underscores(self):
        assert (
            ScriptDirectory._slugify("  hello world  ")
            == "hello_world"
        )
