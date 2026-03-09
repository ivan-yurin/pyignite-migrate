import os
import sys

import click

from pyignite_migrate.config import DEFAULT_CONFIG_FILENAME, Config
from pyignite_migrate.errors import PyIgniteMigrateError
from pyignite_migrate.migration import MigrationContext
from pyignite_migrate.script import ScriptDirectory


@click.group()
@click.option(
    "-c",
    "--config",
    default=None,
    type=click.Path(),
    help=f"Path to configuration file (default: search for {DEFAULT_CONFIG_FILENAME})",
)
@click.pass_context
def cli(ctx: click.Context, config: str | None) -> None:
    """pyignite-migrate: Database migration tool for Apache Ignite."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config


def _load_config(ctx: click.Context) -> Config:
    config_path = ctx.obj.get("config_path")
    return Config.from_file(config_path)


@cli.command()
@click.option(
    "-d",
    "--directory",
    default="migrations",
    help="Directory name for migration scripts (default: migrations)",
)
@click.pass_context
def init(ctx: click.Context, directory: str) -> None:
    """Initialize a new migration environment."""
    from mako.template import Template

    templates_dir = os.path.join(os.path.dirname(__file__), "templates")
    target_dir = os.path.join(os.getcwd(), directory)

    versions_dir = os.path.join(target_dir, "versions")
    os.makedirs(versions_dir, exist_ok=True)

    ini_path = os.path.join(os.getcwd(), DEFAULT_CONFIG_FILENAME)
    if os.path.exists(ini_path):
        click.echo(f"Config file already exists: {ini_path}")
    else:
        ini_template = Template(
            filename=os.path.join(templates_dir, "pyignite_migrate.ini.mako")
        )
        with open(ini_path, "w") as f:
            f.write(ini_template.render(script_location=directory))
        click.echo(f"Created config: {ini_path}")

    env_path = os.path.join(target_dir, "env.py")
    if os.path.exists(env_path):
        click.echo(f"env.py already exists: {env_path}")
    else:
        env_template = Template(filename=os.path.join(templates_dir, "env.py.mako"))
        with open(env_path, "w") as f:
            f.write(env_template.render())
        click.echo(f"Created env.py: {env_path}")

    init_path = os.path.join(versions_dir, "__init__.py")
    if not os.path.exists(init_path):
        with open(init_path, "w") as f:
            f.write("")

    click.echo(f"Migration environment initialized in '{directory}/'")


@cli.command()
@click.option("-m", "--message", default=None, help="Migration description")
@click.option("--head", default=None, help="Head revision to branch from")
@click.pass_context
def revision(ctx: click.Context, message: str | None, head: str | None) -> None:
    """Create a new migration revision file."""
    try:
        config = _load_config(ctx)
        script_dir = ScriptDirectory(config)
        rev_id = script_dir.generate_revision(message=message or "", head=head)
        click.echo(f"Generated new revision: {rev_id}")
    except PyIgniteMigrateError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("target", default="head")
@click.pass_context
def upgrade(ctx: click.Context, target: str) -> None:
    """Upgrade to a target revision.

    TARGET can be a revision ID or 'head' (default) for latest.
    """
    try:
        config = _load_config(ctx)
        script_dir = ScriptDirectory(config)

        resolved_target = None
        if target != "head":
            resolved_target = target

        with MigrationContext(config, script_dir) as mctx:
            applied = mctx.run_upgrade(target=resolved_target)

        if applied:
            click.echo(f"Applied {len(applied)} migration(s):")
            for rev_id in applied:
                rev = script_dir.get_revision_map().get_revision(rev_id)
                click.echo(f"  -> {rev_id}: {rev.description}")
        else:
            click.echo("No migrations to apply.")

    except PyIgniteMigrateError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("target")
@click.pass_context
def downgrade(ctx: click.Context, target: str) -> None:
    """Downgrade to a target revision.

    TARGET can be a revision ID, 'base' (revert all), or '-1' (revert one).
    """
    try:
        config = _load_config(ctx)
        script_dir = ScriptDirectory(config)

        with MigrationContext(config, script_dir) as mctx:
            resolved_target = None

            if target == "base":
                resolved_target = None
            elif target.startswith("-"):
                steps = int(target)
                current = mctx.get_current_revision()
                if current is None:
                    click.echo("Already at base, nothing to downgrade.")
                    return
                rev_map = script_dir.get_revision_map()
                rev = rev_map.get_revision(current)
                for _ in range(abs(steps)):
                    if rev.down_revision is None:
                        resolved_target = None
                        break
                    resolved_target = rev.down_revision
                    rev = rev_map.get_revision(rev.down_revision)
            else:
                resolved_target = target

            reverted = mctx.run_downgrade(target=resolved_target)

        if reverted:
            click.echo(f"Reverted {len(reverted)} migration(s):")
            for rev_id in reverted:
                rev = script_dir.get_revision_map().get_revision(rev_id)
                click.echo(f"  <- {rev_id}: {rev.description}")
        else:
            click.echo("No migrations to revert.")

    except PyIgniteMigrateError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def current(ctx: click.Context) -> None:
    """Show the current migration revision."""
    try:
        config = _load_config(ctx)
        script_dir = ScriptDirectory(config)

        with MigrationContext(config, script_dir) as mctx:
            rev_id = mctx.get_current_revision()

        if rev_id is None:
            click.echo("Current revision: (base) - no migrations applied")
        else:
            rev_map = script_dir.get_revision_map()
            rev = rev_map.get_revision(rev_id)
            head_marker = " (head)" if rev.is_head else ""
            click.echo(f"Current revision: {rev_id}{head_marker}")
            if rev.description:
                click.echo(f"  Description: {rev.description}")

    except PyIgniteMigrateError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def history(ctx: click.Context) -> None:
    """Show the full migration history in topological order."""
    try:
        config = _load_config(ctx)
        script_dir = ScriptDirectory(config)

        rev_map = script_dir.get_revision_map()

        if rev_map.is_empty():
            click.echo("No migration revisions found.")
            return

        try:
            with MigrationContext(config, script_dir) as mctx:
                current_rev = mctx.get_current_revision()
        except Exception:
            current_rev = None

        all_revs = rev_map.get_all_revisions()

        for rev in all_revs:
            markers = []
            if rev.is_base:
                markers.append("base")
            if rev.is_head:
                markers.append("head")
            if rev.revision == current_rev:
                markers.append("current")

            marker_str = f" ({', '.join(markers)})" if markers else ""
            down = rev.down_revision or "(base)"
            click.echo(
                f"{rev.revision} -> {down}{marker_str}: "
                f"{rev.description or '(no description)'}"
            )

    except PyIgniteMigrateError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def heads(ctx: click.Context) -> None:
    """Show current head revision(s)."""
    try:
        config = _load_config(ctx)
        script_dir = ScriptDirectory(config)

        rev_map = script_dir.get_revision_map()

        if rev_map.is_empty():
            click.echo("No migration revisions found.")
            return

        head_ids = rev_map.get_heads()
        click.echo(f"Head revision(s) ({len(head_ids)}):")
        for head_id in head_ids:
            rev = rev_map.get_revision(head_id)
            click.echo(f"  {head_id}: {rev.description or '(no description)'}")

    except PyIgniteMigrateError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("revision_id")
@click.pass_context
def stamp(ctx: click.Context, revision_id: str) -> None:
    """Set the version tracking table without running migrations."""
    try:
        config = _load_config(ctx)
        script_dir = ScriptDirectory(config)

        rev_map = script_dir.get_revision_map()
        if revision_id != "base":
            rev_map.get_revision(revision_id)

        with MigrationContext(config, script_dir) as mctx:
            if revision_id == "base":
                mctx.stamp(None)
                click.echo("Stamped database as: (base)")
            else:
                mctx.stamp(revision_id)
                click.echo(f"Stamped database as: {revision_id}")

    except PyIgniteMigrateError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
