"""Custom bench commands for the custom_translations app.

Commands are discovered by bench through this module's ``commands`` list
(``frappe.utils.bench_helper.get_app_commands`` imports ``<app>.commands``),
so no hook registration is needed.
"""

import click

from custom_translations.config import (
    get_config_file_path,
    get_setup_instructions,
    load_config,
)
from custom_translations.csvio import write_csv_entries
from custom_translations.professional_glossary import (
    PROFESSIONAL_GLOSSARY,
    apply_professional_glossary,
)
from custom_translations.sources import discover_app, read_official_translations
from custom_translations.utils import (
    _auto_translate_via_api,
    _log_missing_translations,
    _scan_missing_translations,
    apply_manual_corrections,
    fix_batch_terminology,
    get_coverage_report,
    get_csv_path,
    invalidate_scan_cache,
    load_app_entries,
    load_app_translations,
    sync_to_po_files,
)
from custom_translations.sync_po import sync_po


def _connect(ctx):
    """Initialise frappe for a bench command and return the site name."""
    import frappe
    from frappe.commands import get_site

    site = get_site(ctx.obj)
    frappe.init(site=site)
    frappe.connect()
    return site


@click.command("custom-translations-stats")
@click.pass_context
def show_stats(ctx):
    """Show translation statistics and configuration status."""
    _connect(ctx)
    translations = load_app_translations()
    click.echo(f"This app's CSV: {get_csv_path()}")
    click.echo(f"Curated translations: {len(translations)}")
    click.echo(f"Professional glossary terms: {len(PROFESSIONAL_GLOSSARY)}")

    cfg = load_config()
    click.echo(f"\nAuto-translation: {'enabled' if cfg.get('auto_translate') else 'disabled'}")
    click.echo(f"API configured: {'yes' if cfg.get('is_configured') else 'no'}")
    click.echo(f"Scan on boot: {'yes' if cfg.get('scan_on_boot') else 'no'}")
    click.echo(f"Scan cache TTL: {cfg.get('scan_interval_seconds')}s")
    if cfg.get("is_configured"):
        click.echo(f"  Provider: {cfg.get('provider')}")
        click.echo(f"  Model: {cfg.get('model')}")


@click.command("custom-translations-config")
def show_config():
    """Show the effective configuration (API key masked)."""
    cfg = load_config()
    click.echo("=== Custom Translations Configuration ===\n")

    display = dict(cfg)
    key = display.get("api_key") or ""
    if key:
        display["api_key"] = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"

    for name, value in display.items():
        click.echo(f"  {name}: {value}")

    config_path = get_config_file_path()
    click.echo(f"\nConfig file path: {config_path}")
    click.echo(f"Config file exists: {config_path.exists()}")

    if not cfg.get("is_configured"):
        click.echo("\n" + "=" * 50)
        click.echo("API NOT CONFIGURED - auto-translation disabled")
        click.echo("=" * 50)
        click.echo(get_setup_instructions())


@click.command("custom-translations-coverage")
@click.option("--app", "apps", multiple=True, help="Limit to specific apps (repeatable)")
@click.pass_context
def coverage(ctx, apps):
    """Show per-app Chinese coverage and where each app keeps its translations."""
    _connect(ctx)
    report = get_coverage_report(list(apps) if apps else None)

    if not report:
        click.echo("No installed apps found.")
        return

    click.echo(
        f"{'app':<12} {'layout':<10} {'inventory':>10} {'app zh':>8} {'our zh':>7} {'missing':>8}"
    )
    click.echo("-" * 60)
    totals = {"inventory": 0, "missing": 0}
    for row in report:
        click.echo(
            f"{row['app']:<12} {row['format']:<10} {row['inventory']:>10} "
            f"{row['translated_by_app']:>8} {row['covered_by_us']:>7} {row['missing_count']:>8}"
        )
        totals["inventory"] += row["inventory"]
        totals["missing"] += row["missing_count"]
    click.echo("-" * 60)
    click.echo(f"{'TOTAL':<12} {'':<10} {totals['inventory']:>10} {'':>8} {'':>7} {totals['missing']:>8}")
    click.echo("\n'inventory' = translatable strings found; 'app zh' = translated by the app itself;")
    click.echo("'our zh' = covered by this app's CSV; 'missing' = still untranslated everywhere.")


@click.command("custom-translations-export")
@click.option("--output", default=None, help="Output CSV path (default: translations/zh.imported.csv)")
@click.option("--merge", is_flag=True, help="Merge into this app's zh.csv instead of a side file")
@click.option("--overwrite", is_flag=True, help="With --merge: replace existing values too")
@click.pass_context
def export_from_frappe(ctx, output, merge, overwrite):
    """Export the installed apps' own Chinese translations.

    SAFETY: this never overwrites the curated zh.csv unless you ask for it.
    The original implementation opened that file with mode "w" and wrote only
    what it could scrape from frappe's zh.po, which silently deleted every
    ERPNext/HRMS string, the glossary and all manual corrections.
    """
    _connect(ctx)
    from pathlib import Path

    import frappe

    collected = {}
    scanned = []
    for app in frappe.get_installed_apps():
        sources = discover_app(app)
        if not sources.has_any:
            scanned.append((app, "none", 0))
            continue
        official = read_official_translations(app)
        collected.update({k: v for k, v in official.items() if k and v})
        scanned.append((app, sources.format, len(official)))

    for app, layout, count in scanned:
        click.echo(f"  [{app}] {layout}: {count} translations")
    click.echo(f"\nCollected {len(collected)} translations from installed apps")

    if not collected:
        click.echo("Nothing to export.")
        return

    if merge:
        from custom_translations.utils import _append_to_csv

        changed = _append_to_csv(collected, overwrite=overwrite)
        click.echo(f"Merged into {get_csv_path()} ({changed} rows changed)")
        return

    target = Path(output) if output else get_csv_path().with_name("zh.imported.csv")
    entries = load_app_entries()
    from custom_translations.csvio import CsvEntry

    merged = {entry.key: entry for entry in entries}
    for key, value in collected.items():
        merged.setdefault(key, CsvEntry(msgid=key, msgstr=value))
    write_csv_entries(target, sorted(merged.values(), key=lambda e: e.msgid))
    click.echo(f"Wrote {len(merged)} entries to {target}")
    click.echo("The curated zh.csv was NOT modified.")


@click.command("custom-translations-scan")
@click.option("--app", "apps", multiple=True, help="Limit to specific apps (repeatable)")
@click.pass_context
def scan_missing(ctx, apps):
    """Scan every installed app for untranslated strings and log them."""
    _connect(ctx)
    import frappe

    missing = _scan_missing_translations(list(apps) if apps else None)
    click.echo(f"Detected {len(missing)} missing translations")
    if missing:
        inserted = _log_missing_translations(missing)
        frappe.db.commit()
        invalidate_scan_cache()
        click.echo(f"Logged {inserted} new entries to Missing Translation Log")
    else:
        click.echo("Nothing missing - every detected string is already translated.")


@click.command("custom-translations-auto-translate")
@click.option("--limit", default=0, help="Max number of entries to translate (0 = all)")
@click.option("--app", "apps", multiple=True, help="Limit to specific apps (repeatable)")
@click.pass_context
def auto_translate(ctx, limit, apps):
    """Auto-translate missing entries via the configured API."""
    site = _connect(ctx)
    import frappe

    api_cfg = load_config()
    if not api_cfg.get("is_configured"):
        click.echo(f"ERROR: API not configured. Run `bench --site {site} custom-translations-config`.")
        click.echo("")
        click.echo(get_setup_instructions())
        return
    if not api_cfg.get("auto_translate"):
        click.echo(
            "Auto-translation is disabled. Set auto_translate=true in config or "
            "CUSTOM_TRANSLATIONS_AUTO_TRANSLATE=1 in the environment."
        )
        return

    click.echo(f"Provider: {api_cfg.get('provider')}, Model: {api_cfg.get('model')}")

    open_entries = frappe.get_all(
        "Missing Translation Log",
        filters={"status": "Open"},
        fields=["source_text", "app"],
        order_by="detected_on asc",
        limit_page_length=limit if limit > 0 else 0,
    )
    work = [{"msgid": row["source_text"], "app": row["app"]} for row in open_entries]

    # Also include entries that are missing but not logged yet.
    scanned = _scan_missing_translations(list(apps) if apps else None)
    known = {item["msgid"] for item in work}
    extra = [item for item in scanned if item["msgid"] not in known]
    if extra:
        click.echo(f"  (including {len(extra)} newly detected entries)")
        _log_missing_translations(extra)
        work.extend(extra)

    if not work:
        click.echo("No missing translations to process.")
        return
    if limit > 0:
        work = work[:limit]

    click.echo(f"Processing {len(work)} entries via {api_cfg.get('provider')} API...")
    translated = _auto_translate_via_api(work, api_cfg)
    frappe.db.commit()
    invalidate_scan_cache()

    click.echo("\nResults:")
    click.echo(f"  Translated now: {len(translated)}")
    click.echo(f"  Open in log: {frappe.db.count('Missing Translation Log', filters={'status': 'Open'})}")
    click.echo(f"  CSV total: {len(load_app_translations())}")
    if translated:
        click.echo("\nNext steps:")
        click.echo("  1. Review the new rows in the Missing Translation Log")
        click.echo(f"  2. bench --site {site} custom-translations-apply-corrections   # after manual edits")
        click.echo(f"  3. bench --site {site} clear-cache")


@click.command("custom-translations-apply-corrections")
@click.pass_context
def apply_corrections(ctx):
    """Apply manual corrections from Missing Translation Log to the CSV.

    Records marked ``Reviewed``, or whose ``translation_source`` is ``Manual``,
    override the automatic translations.
    """
    site = _connect(ctx)
    import frappe

    count = apply_manual_corrections()
    if count > 0:
        frappe.db.commit()
        invalidate_scan_cache()
        click.echo(f"Applied {count} manual corrections to the CSV")
        click.echo(f"Run `bench --site {site} clear-cache` to apply them in the browser")
    else:
        click.echo(
            "No manual corrections found (set status='Reviewed' or "
            "translation_source='Manual' in the Missing Translation Log)"
        )


@click.command("custom-translations-apply-glossary")
@click.pass_context
def apply_glossary(ctx):
    """Apply the curated ERP glossary (overrides auto/locale translations)."""
    site = _connect(ctx)

    count = apply_professional_glossary()
    click.echo(f"Applied {count} professional glossary entries to the CSV")
    click.echo("Run `bench --site %s clear-cache` to apply them in the browser" % site)


@click.command("custom-translations-fix-terminology")
@click.option("--dry-run", is_flag=True, help="Only report what would change")
@click.pass_context
def fix_terminology(ctx, dry_run):
    """Repair Taiwan wording and systematic mistranslations in the CSV.

    Rules are guarded by the English source string, so verb senses are not
    corrupted (the previous blind 报告->报表 replacement turned
    'Reporting Currency' into '报表货币' and '... can be reported' into
    '可以报表漏洞' - see docs/ for the audit).
    """
    site = _connect(ctx)
    import frappe

    existing = load_app_translations()
    from custom_translations.terminology import audit_translations

    changes = audit_translations(existing)
    if not changes:
        click.echo("No terminology issues found - all entries already use mainland wording.")
        return

    click.echo(f"{len(changes)} entries need correction:")
    for source, before, after, notes in changes:
        click.echo(f"  {source[:70]!r}\n    - {before[:70]!r}\n    + {after[:70]!r}\n      ({', '.join(notes)})")

    if dry_run:
        click.echo("\nDry run - nothing written.")
        return

    count = fix_batch_terminology()
    frappe.db.commit()
    invalidate_scan_cache()
    click.echo(f"\nCorrected {count} entries")
    click.echo(f"Run `bench --site {site} clear-cache` to apply them in the browser")


@click.command("custom-translations-sync")
@click.option("--app", "apps", multiple=True, help="Limit to specific apps (repeatable)")
@click.option("--yes", is_flag=True, help="Skip the confirmation delay")
@click.pass_context
def sync_translations(ctx, apps, yes):
    """OPTIONAL: fill empty msgstr entries of the apps' own PO files.

    Translations already work through this app's CSV; this only compiles them
    into the .mo binaries. It edits official files - skip it unless you need it.
    """
    _connect(ctx)
    results = sync_to_po_files(
        list(apps) if apps else None,
        force=yes,
    )
    if results:
        total = sum(results.values())
        click.echo(f"Filled {total} entries across {len(results)} PO file(s)")


@click.command("custom-translations-sync-po")
@click.option("--force", is_flag=True, help="Overwrite existing translations with upstream wording")
@click.option("--app", "apps", multiple=True, help="Limit to specific apps (repeatable)")
@click.pass_context
def sync_po_cmd(ctx, force, apps):
    """Import official Chinese translations from the local upstream apps.

    Reads the Crowdin-maintained ``locale/zh.po`` catalogues that ship inside
    the bench checkout (frappe, erpnext, hrms, helpdesk) and merges every
    translated entry into this app's override CSV ``translations/zh.csv``.

    * Existing (hand-curated) rows always win; ``--force`` lets upstream win.
    * Untranslated/fuzzy PO entries are skipped.
    * Run it again after ``bench update`` to pick up new upstream wording.

    Usage:
        bench --site <site> custom-translations-sync-po [--force] [--app erpnext]
    """
    _connect(ctx)
    csv_fn = get_csv_path()
    added = sync_po(csv_fn, force=force, apps=list(apps) if apps else None)
    click.echo(f"Synced {added} new/updated translation entries into {csv_fn}")
    if added:
        click.echo(f"Run `bench --site {ctx.obj} clear-cache` to apply them in the browser")


commands = [
    sync_translations,
    sync_po_cmd,
    show_stats,
    show_config,
    coverage,
    export_from_frappe,
    scan_missing,
    auto_translate,
    apply_corrections,
    apply_glossary,
    fix_terminology,
]
