import configparser
import os
from dataclasses import dataclass

from pyignite_migrate.errors import ConfigurationError

DEFAULT_CONFIG_FILENAME = "pyignite_migrate.ini"
DEFAULT_SCHEMA = "PUBLIC"
DEFAULT_VERSION_TABLE = "__pyignite_migrate_version"


@dataclass
class Config:
    """Parsed configuration for pyignite-migrate."""

    hosts: list[tuple[str, int]]
    script_location: str
    version_table: str = DEFAULT_VERSION_TABLE
    schema: str = DEFAULT_SCHEMA
    file_template: str = "${rev}_${slug}"
    config_dir: str = ""

    @classmethod
    def from_file(cls, path: str | None = None) -> "Config":
        if path is None:
            path = cls._find_config_file()
        if not os.path.isfile(path):
            raise ConfigurationError(f"Configuration file not found: {path}")

        parser = configparser.ConfigParser()
        parser.read(path)

        config_dir = os.path.dirname(os.path.abspath(path))

        if not parser.has_section("pyignite_migrate"):
            raise ConfigurationError(
                "Missing [pyignite_migrate] section in config file"
            )
        section = parser["pyignite_migrate"]

        hosts_raw = section.get("hosts", "127.0.0.1:10800")
        hosts = cls._parse_hosts(hosts_raw)

        script_location = section.get("script_location", "migrations")
        version_table = section.get("version_table", DEFAULT_VERSION_TABLE)
        schema = section.get("schema", DEFAULT_SCHEMA)
        file_template = section.get("file_template", "${rev}_${slug}")

        return cls(
            hosts=hosts,
            script_location=script_location,
            version_table=version_table,
            schema=schema,
            file_template=file_template,
            config_dir=config_dir,
        )

    @staticmethod
    def _parse_hosts(hosts_raw: str) -> list[tuple[str, int]]:
        result = []
        for entry in hosts_raw.split(","):
            entry = entry.strip()
            if ":" in entry:
                host, port_str = entry.rsplit(":", 1)
                result.append((host.strip(), int(port_str.strip())))
            else:
                result.append((entry, 10800))
        return result

    @staticmethod
    def _find_config_file() -> str:
        current = os.getcwd()
        while True:
            candidate = os.path.join(current, DEFAULT_CONFIG_FILENAME)
            if os.path.isfile(candidate):
                return candidate
            parent = os.path.dirname(current)
            if parent == current:
                raise ConfigurationError(
                    f"Cannot find {DEFAULT_CONFIG_FILENAME} in any parent directory"
                )
            current = parent

    def get_script_location_abs(self) -> str:
        if os.path.isabs(self.script_location):
            return self.script_location
        return os.path.join(self.config_dir, self.script_location)
