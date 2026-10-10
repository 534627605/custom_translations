"""
Setup hooks for the Custom Translations app.

Called after ``bench install-app``. Prints a short guide so users know the
basics work with no configuration at all, and how to opt into the AI auto-fill.
"""

import click

from custom_translations.config import (
    get_config_file_path,
    get_setup_instructions,
    load_config,
)


def after_install():
    """Called by Frappe after app installation. Shows the setup guide."""
    click.echo("\n" + "=" * 60)
    click.echo("Custom Translations installed successfully!")
    click.echo("=" * 60)
    click.echo("\nThis app provides Chinese translations that survive framework upgrades.")
    click.echo("Translations work immediately - no configuration required for basic use.\n")

    click.echo("Optional: enable automatic translation of newly detected entries.")
    click.echo("This is useful when new framework versions add untranslated strings.\n")

    cfg = load_config()
    if cfg.get("is_configured"):
        click.echo(f"Auto-translation is already configured (provider: {cfg.get('provider')}).")
    else:
        click.echo("To enable auto-translation, configure your API key:\n")
        click.echo(get_setup_instructions())
        click.echo(f"\nConfig file location: {get_config_file_path()}")
        click.echo("Copy config.example.json to config.json and fill in your API key.")

    click.echo("\nAvailable commands (run with `bench --site <site> <command>`):")
    for line in (
        "custom-translations-stats             # translation + config summary",
        "custom-translations-config            # effective configuration",
        "custom-translations-coverage          # per-app Chinese coverage",
        "custom-translations-scan              # find and log missing strings",
        "custom-translations-auto-translate    # AI fill (needs an API key)",
        "custom-translations-apply-glossary    # apply the curated glossary",
        "custom-translations-fix-terminology   # fix Taiwan wording",
        "custom-translations-apply-corrections # apply manual corrections",
        "custom-translations-sync              # optional: fill .po files",
    ):
        click.echo("  " + line)
    click.echo("\n" + "=" * 60 + "\n")
