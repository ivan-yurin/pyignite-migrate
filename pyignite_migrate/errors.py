class PyIgniteMigrateError(Exception):
    """Base exception for all pyignite-migrate errors."""


class ConfigurationError(PyIgniteMigrateError):
    """Raised when configuration is invalid or missing."""


class RevisionError(PyIgniteMigrateError):
    """Raised for revision graph problems: cycles, missing revisions, multiple heads."""


class MigrationError(PyIgniteMigrateError):
    """Raised when a migration fails during upgrade/downgrade."""


class ScriptError(PyIgniteMigrateError):
    """Raised when a migration script cannot be loaded or parsed."""
