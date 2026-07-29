"""Custom bench commands for custom_translations app."""

import click

from custom_translations.utils import (
    sync_to_po_files,
    load_app_translations,
    _scan_missing_translations,
    _log_missing_translations,
    _auto_translate_via_api,
    apply_manual_corrections,
)
from custom_translations.config import load_config, get_setup_instructions, get_config_file_path
from custom_translations.professional_glossary import apply_professional_glossary, PROFESSIONAL_GLOSSARY


@click.command("custom-translations-sync")
@click.pass_context
def sync_translations(ctx):
    """Sync this app's zh.csv translations into all apps' zh.po files."""
    import frappe
    from frappe.commands import get_site

    site = get_site(ctx.obj)
    frappe.init(site=site)
    frappe.connect()
    sync_to_po_files()


@click.command("custom-translations-stats")
@click.pass_context
def show_stats(ctx):
    """Show translation statistics."""
    import frappe
    from frappe.commands import get_site

    site = get_site(ctx.obj)
    frappe.init(site=site)
    frappe.connect()

    translations = load_app_translations()
    click.echo(f"Total translations in custom_translations/translations/zh.csv: {len(translations)}")

    # Show config status
    cfg = load_config()
    click.echo(f"\nAuto-translation: {'enabled' if cfg.get('auto_translate') else 'disabled'}")
    click.echo(f"API configured: {'yes' if cfg.get('is_configured') else 'no'}")
    if cfg.get('is_configured'):
        click.echo(f"  Provider: {cfg.get('provider')}")
        click.echo(f"  Model: {cfg.get('model')}")


@click.command("custom-translations-config")
def show_config():
    """Show current configuration and setup instructions."""
    cfg = load_config()
    click.echo("=== Custom Translations Configuration ===\n")

    # Mask API key for security
    display_cfg = dict(cfg)
    if display_cfg.get("api_key"):
        key = display_cfg["api_key"]
        display_cfg["api_key"] = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"

    for key, value in display_cfg.items():
        click.echo(f"  {key}: {value}")

    config_path = get_config_file_path()
    click.echo(f"\nConfig file path: {config_path}")
    click.echo(f"Config file exists: {config_path.exists()}")

    if not cfg.get("is_configured"):
        click.echo("\n" + "=" * 50)
        click.echo("API NOT CONFIGURED - auto-translation disabled")
        click.echo("=" * 50)
        click.echo(get_setup_instructions())


@click.command("custom-translations-export")
@click.pass_context
def export_from_frappe(ctx):
    """Export current frappe/erpnext/hrms zh.po translations into this app's zh.csv."""
    from pathlib import Path
    from babel.messages.pofile import read_po
    import csv
    import frappe
    from frappe.commands import get_site

    site = get_site(ctx.obj)
    frappe.init(site=site)
    frappe.connect()

    apps = ["frappe", "erpnext", "hrms", "payments", "webshop"]
    all_translations = {}

    for app in apps:
        try:
            app_path = frappe.get_app_path(app)
        except Exception:
            continue
        po_path = Path(app_path) / "locale" / "zh.po"
        if not po_path.exists():
            continue

        with open(po_path, "rb") as f:
            catalog = read_po(f)

        count = 0
        for msg in catalog:
            if not msg.id:
                continue
            msgid = msg.id[0] if isinstance(msg.id, tuple) else msg.id
            if msg.string and str(msg.string).strip():
                all_translations[msgid] = str(msg.string)
                count += 1
        click.echo(f"  [{app}] extracted {count} translations")

    csv_path = Path(frappe.get_app_path("custom_translations")) / "translations" / "zh.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        for key, value in sorted(all_translations.items()):
            k = key.replace("\n", "\\n")
            v = value.replace("\n", "\\n")
            writer.writerow([k, v])

    click.echo(f"\nExported {len(all_translations)} translations to {csv_path}")


@click.command("custom-translations-scan")
@click.pass_context
def scan_missing(ctx):
    """Scan all apps for missing translations and log to Missing Translation Log."""
    import frappe
    from frappe.commands import get_site

    site = get_site(ctx.obj)
    frappe.init(site=site)
    frappe.connect()

    # Ensure doctype schema is migrated
    try:
        frappe.model.sync_file_to_doc("Missing Translation Log", "Missing Translation Log")
    except Exception:
        pass

    missing = _scan_missing_translations()
    click.echo(f"Detected {len(missing)} missing translations")
    if missing:
        _log_missing_translations(missing)
        frappe.db.commit()
        click.echo("Logged to Missing Translation Log doctype")


@click.command("custom-translations-auto-translate")
@click.option("--limit", default=0, help="Max number of entries to translate (0 = all)")
@click.pass_context
def auto_translate(ctx, limit):
    """Auto-translate open Missing Translation Log entries via configured API."""
    import frappe
    from frappe.commands import get_site

    # bench commands need manual frappe init + connect
    site = get_site(ctx.obj)
    frappe.init(site=site)
    frappe.connect()

    # Load config from all sources (env vars, config.json, site_config.json)
    api_cfg = load_config()

    if not api_cfg.get("is_configured"):
        click.echo(f"ERROR: API not configured. Run `bench --site {site} custom-translations-config` for setup instructions.")
        click.echo("")
        click.echo(get_setup_instructions())
        return

    if not api_cfg.get("auto_translate"):
        click.echo("Auto-translation is disabled. Set auto_translate=true in config or CUSTOM_TRANSLATIONS_AUTO_TRANSLATE=1 env var.")
        return

    click.echo(f"Provider: {api_cfg.get('provider')}, Model: {api_cfg.get('model')}")

    # Get open entries from Missing Translation Log (priority: oldest first)
    filters = {"status": "Open"}
    open_entries = frappe.get_all(
        "Missing Translation Log",
        filters=filters,
        fields=["source_text", "app"],
        order_by="detected_on asc",
        limit=limit if limit > 0 else 100000,
    )
    # Map source_text -> msgid for _auto_translate_via_api
    for e in open_entries:
        e["msgid"] = e.pop("source_text")

    if not open_entries:
        click.echo("No open missing translations to process")
        return

    click.echo(f"Processing {len(open_entries)} entries via {api_cfg.get('provider')} API...")

    # Also include any missing entries not yet logged
    scanned = _scan_missing_translations()
    scanned_keys = {m["msgid"] for m in scanned}
    logged_keys = {e["msgid"] for e in open_entries}
    extra = [m for m in scanned if m["msgid"] not in logged_keys]
    if extra:
        click.echo(f"  (including {len(extra)} newly detected entries)")
        _log_missing_translations(extra)
        open_entries.extend(extra)

    if limit > 0:
        open_entries = open_entries[:limit]

    _auto_translate_via_api(open_entries, api_cfg)
    frappe.db.commit()

    # Show results
    translated_count = frappe.db.count("Missing Translation Log", filters={"status": "Translated"})
    open_count = frappe.db.count("Missing Translation Log", filters={"status": "Open"})
    csv_count = len(load_app_translations())
    click.echo(f"\nResults:")
    click.echo(f"  Translated: {translated_count}")
    click.echo(f"  Still open: {open_count}")
    click.echo(f"  CSV total: {csv_count}")

    if translated_count > 0:
        click.echo("\nNext steps:")
        click.echo(f"  1. Review translations in Missing Translation Log doctype")
        click.echo(f"  2. Run: bench --site {site} custom-translations-sync")
        click.echo(f"  3. After manual corrections: bench --site {site} custom-translations-apply-corrections")


@click.command("custom-translations-apply-corrections")
@click.pass_context
def apply_corrections(ctx):
    """Apply manual corrections from Missing Translation Log to CSV.

    Use this after manually reviewing/editing translations in the
    Missing Translation Log doctype. Records marked as 'Reviewed' or
    with translation_source='Manual' will override auto-translations.
    """
    import frappe
    from frappe.commands import get_site

    site = get_site(ctx.obj)
    frappe.init(site=site)
    frappe.connect()

    count = apply_manual_corrections()
    if count > 0:
        frappe.db.commit()
        click.echo(f"Applied {count} manual corrections to CSV")
        click.echo(f"Run `bench --site {site} custom-translations-sync` to apply to .po files")
    else:
        click.echo("No manual corrections found (mark records as 'Reviewed' in Missing Translation Log)")


@click.command("custom-translations-apply-glossary")
@click.pass_context
def apply_glossary(ctx):
    """Apply professional ERP glossary to translations CSV.

    Overwrites auto-translated and locale-pack translations with
    professionally-curated Chinese ERP terminology that follows
    Chinese accounting standards (企业会计准则).

    This is safe to run multiple times - only glossary terms are affected.
    Other translations remain unchanged.
    """
    import frappe
    from frappe.commands import get_site

    site = get_site(ctx.obj)
    frappe.init(site=site)
    frappe.connect()

    count = apply_professional_glossary()
    click.echo(f"Applied {count} professional glossary entries to zh.csv")
    click.echo(f"These translations override auto-translated and locale-pack versions.")
    click.echo(f"Run `bench --site {site} clear-cache` to apply changes in browser.")
    click.echo(f"Optional: `bench --site {site} custom-translations-sync` to sync to .po files")


commands = [
    sync_translations,
    show_stats,
    show_config,
    export_from_frappe,
    scan_missing,
    auto_translate,
    apply_corrections,
    apply_glossary,
]
