import os

import pytest

from pyignite_migrate.config import DEFAULT_VERSION_TABLE, Config
from pyignite_migrate.errors import ConfigurationError


class TestConfigFromFile:
    def test_loads_valid_config(self, tmp_project):
        config = Config.from_file(str(tmp_project / "pyignite_migrate.ini"))
        assert config.hosts == [("127.0.0.1", 10800)]
        assert config.script_location == "migrations"
        assert config.schema == "PUBLIC"
        assert config.version_table == DEFAULT_VERSION_TABLE

    def test_missing_file_raises(self):
        with pytest.raises(ConfigurationError, match="not found"):
            Config.from_file("/nonexistent/path/config.ini")

    def test_missing_section_raises(self, tmp_path):
        config_path = tmp_path / "pyignite_migrate.ini"
        config_path.write_text("[other]\nfoo = bar\n")
        with pytest.raises(ConfigurationError, match="Missing.*section"):
            Config.from_file(str(config_path))

    def test_defaults(self, tmp_path):
        config_path = tmp_path / "pyignite_migrate.ini"
        config_path.write_text("[pyignite_migrate]\n")
        config = Config.from_file(str(config_path))
        assert config.hosts == [("127.0.0.1", 10800)]
        assert config.script_location == "migrations"
        assert config.schema == "PUBLIC"

    def test_find_config_file(self, tmp_project):
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_project / "migrations" / "versions")
            config = Config.from_file()
            assert config.hosts == [("127.0.0.1", 10800)]
        finally:
            os.chdir(old_cwd)


class TestParseHosts:
    def test_single_host_with_port(self):
        result = Config._parse_hosts("192.168.1.1:10801")
        assert result == [("192.168.1.1", 10801)]

    def test_single_host_without_port(self):
        result = Config._parse_hosts("192.168.1.1")
        assert result == [("192.168.1.1", 10800)]

    def test_multiple_hosts(self):
        result = Config._parse_hosts("host1:10800, host2:10801, host3:10802")
        assert result == [
            ("host1", 10800),
            ("host2", 10801),
            ("host3", 10802),
        ]


class TestGetScriptLocationAbs:
    def test_relative_path(self, tmp_project):
        config = Config.from_file(str(tmp_project / "pyignite_migrate.ini"))
        abs_path = config.get_script_location_abs()
        assert os.path.isabs(abs_path)
        assert abs_path.endswith("migrations")

    def test_absolute_path(self):
        config = Config(
            hosts=[("localhost", 10800)],
            script_location="/absolute/path/migrations",
            config_dir="/some/dir",
        )
        assert config.get_script_location_abs() == "/absolute/path/migrations"
