"""
env.py - Migration environment script for pyignite-migrate.

This script is executed when pyignite-migrate commands are run.
It can be customized to modify connection behavior, add logging, etc.
"""
from pyignite_migrate.config import Config
from pyignite_migrate.migration import MigrationContext
from pyignite_migrate.script import ScriptDirectory


def run_migrations():
    """
    Configure and run the migration context.

    This is the default implementation. You can customize it to:
    - Add custom connection parameters
    - Set up logging
    - Add pre/post migration hooks
    """
    config = Config.from_file()
    script_dir = ScriptDirectory(config)

    with MigrationContext(config, script_dir) as context:
        pass


if __name__ == "__main__":
    run_migrations()
