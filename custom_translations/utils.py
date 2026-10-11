"""
Custom Translations - core logic.

Responsibilities
----------------
1. Own this app's curated ``translations/zh.csv`` (the override layer that
   Frappe merges over every other app).
2. Discover what every installed app actually ships (``locale/*.po``,
   ``translations/*.csv``, ``locale/main.pot``) - see
   :mod:`custom_translations.sources`.
3. Report coverage per app and log untranslated strings to the
   ``Missing Translation Log`` doctype.
4. Fill the gaps with the AI engine (:mod:`custom_translations.translate`),
   never overwriting an existing translation.
5. Repair terminology with context-aware rules
   (:mod:`custom_translations.terminology`) instead of blind replacement.

Everything that needs a site is imported lazily so the pure helpers can be
unit tested and used from the offline CLI.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import frappe
from frappe.utils import now_datetime

from custom_translations import csvio, po
from custom_translations.csvio import CsvEntry
from custom_translations.config import load_config
from custom_translations.sources import (
    SUPPORTED_LANG,
    AppSources,
    discover_app,
    read_official_translations,
    source_inventory,
)
from custom_translations.terminology import fix_translations

APP_NAME = "custom_translations"

#: Cache key / TTL defaults for the boot-time scan throttle
SCAN_CACHE_KEY = "custom_translations:missing_scan"
DEFAULT_SCAN_INTERVAL = 6 * 60 * 60  # 6 hours

#: Never insert more than this many rows in a single scan run
MAX_LOGGED_PER_RUN = 500

__all__ = [
    "APP_NAME",
    "SUPPORTED_LANG",
    "get_csv_path",
    "load_app_translations",
    "load_app_entries",
    "_append_to_csv",
    "get_coverage_report",
    "scan_app",
    "_scan_missing_translations",
    "_log_missing_translations",
    "_mark_logs_translated",
    "_auto_translate_via_api",
    "apply_manual_corrections",
    "fix_batch_terminology",
    "sync_to_po_files",
    "detect_missing_translations_bootinfo",
    "scheduled_translation_scan",
    "on_translation_update",
    "detect_site_version",
]


# --------------------------------------------------------------------------- #
# This app's own CSV (the override layer)
# --------------------------------------------------------------------------- #

def get_csv_path() -> Path:
    """Path to this app's ``translations/zh.csv``."""
    return Path(frappe.get_app_path(APP_NAME)) / "translations" / f"{SUPPORTED_LANG}.csv"


def load_app_entries() -> List[CsvEntry]:
    """Load this app's CSV as raw entries (context columns preserved)."""
    return csvio.read_csv_entries(get_csv_path())


def load_app_translations() -> Dict[str, str]:
    """Load this app's translations as ``{source: translation}``."""
    return csvio.read_csv_translations(get_csv_path())


def _append_to_csv(new_translations: Dict[str, str], overwrite: bool = False) -> int:
    """Merge translations into this app's CSV (deduped by key).

    Args:
        new_translations: ``{source_text: translated_text}``
        overwrite: ``False`` (default) preserves any existing translation, so
            automatic results can never clobber curated or manual ones.
            ``True`` replaces the value (used by the glossary, the manual
            corrections command and the ``Translation`` doctype hook).

    Returns the number of rows that actually changed. The file is left
    untouched when nothing changed, so the command does not rewrite 16k lines
    for a no-op.
    """
    csv_path = get_csv_path()
    entries = csvio.read_csv_entries(csv_path)
    position = {entry.key: index for index, entry in enumerate(entries)}

    changed = 0
    for key, value in new_translations.items():
        if value is None:
            continue
        value = str(value)
        if not value.strip():
            continue
        index = position.get(key)
        if index is None:
            position[key] = len(entries)
            entries.append(CsvEntry(msgid=key, msgstr=value))
            changed += 1
        elif overwrite and entries[index].msgstr != value:
            entries[index] = CsvEntry(
                msgid=entries[index].msgid, msgstr=value, context=entries[index].context
            )
            changed += 1

    if changed:
        entries.sort(key=lambda entry: entry.msgid)
        csvio.write_csv_entries(csv_path, entries)
    return changed


# --------------------------------------------------------------------------- #
# Coverage: what does every installed app ship, and what is missing?
# --------------------------------------------------------------------------- #

def get_installed_apps(include_self: bool = False) -> List[str]:
    """Installed apps, excluding this one by default."""
    try:
        apps = list(frappe.get_installed_apps())
    except Exception:
        return []
    if not include_self:
        apps = [app for app in apps if app != APP_NAME]
    return apps


def scan_app(app: str, ours: Optional[Dict[str, str]] = None) -> Dict:
    """Return coverage facts for a single app.

    ``missing`` is the list of source strings the app does not translate and
    that this app does not translate either - i.e. the real work list.
    """
    ours = load_app_translations() if ours is None else ours
    sources: AppSources = discover_app(app)
    official = read_official_translations(app) if sources.has_any else {}
    inventory = source_inventory(app) if sources.module_dir else None

    msgids = set(inventory.msgids) if inventory else set()
    missing = sorted(
        msgid for msgid in msgids if not official.get(msgid) and not ours.get(msgid)
    )
    return {
        "app": app,
        "format": sources.format,
        "inventory_origin": inventory.origin if inventory else "none",
        "inventory": len(msgids),
        "translated_by_app": len(official),
        "covered_by_us": len([m for m in msgids if ours.get(m)]),
        "missing": missing,
        "missing_count": len(missing),
    }


def get_coverage_report(apps: Optional[Sequence[str]] = None) -> List[Dict]:
    """Coverage report for every installed app (or an explicit list)."""
    ours = load_app_translations()
    targets = list(apps) if apps is not None else get_installed_apps()
    return [scan_app(app, ours=ours) for app in targets]


def _scan_missing_translations(apps: Optional[Sequence[str]] = None) -> List[Dict]:
    """Return ``[{"app": app, "msgid": text}, ...]`` for every untranslated string.

    Works for PO based apps (frappe, hrms, helpdesk) *and* CSV based apps
    (erpnext, payments, webshop, telephony, wiki) - the layout is discovered,
    not assumed.
    """
    missing: List[Dict] = []
    for report in get_coverage_report(apps):
        for msgid in report["missing"]:
            if msgid:
                missing.append({"app": report["app"], "msgid": msgid})
    return missing


# --------------------------------------------------------------------------- #
# Missing Translation Log
# --------------------------------------------------------------------------- #

def _row(record, field, default=None):
    """Read a field from a query row (frappe._dict, dict or object)."""
    if isinstance(record, dict):
        return record.get(field, default)
    return getattr(record, field, default)


def _existing_log_keys() -> set:
    """Every source_text already present in the log, whatever its status."""
    try:
        rows = frappe.get_all("Missing Translation Log", fields=["source_text"], limit_page_length=0)
    except Exception:
        return set()
    return {row.get("source_text") for row in rows if row.get("source_text")}


def _log_missing_translations(missing: Iterable[Dict], limit: int = MAX_LOGGED_PER_RUN) -> int:
    """Insert new missing translations into the log (deduped, capped).

    De-duplication is done against *every* record, not just the ``Open`` ones:
    Frappe does not enforce ``unique`` on Text columns, so the previous
    ``status="Open"`` filter allowed a string to be logged again as soon as it
    was marked Translated/Reviewed/Ignored.
    """
    existing = _existing_log_keys()
    inserted = 0
    for item in missing:
        if inserted >= limit:
            frappe.logger(APP_NAME).warning(
                f"Missing Translation Log cap of {limit} rows reached, remaining entries skipped"
            )
            break
        msgid = item["msgid"]
        if len(msgid) > 2000 or msgid in existing:
            continue
        try:
            doc = frappe.get_doc(
                {
                    "doctype": "Missing Translation Log",
                    "source_text": msgid,
                    "app": item.get("app"),
                    "language": SUPPORTED_LANG,
                    "status": "Open",
                    "detected_on": now_datetime(),
                }
            )
            doc.insert(ignore_permissions=True)
            existing.add(msgid)
            inserted += 1
        except Exception as exc:  # noqa: BLE001
            frappe.logger(APP_NAME).error(
                f"Failed to log missing translation {msgid[:50]!r}: {exc}"
            )
    return inserted


def _mark_logs_translated(translations: Dict[str, str]) -> None:
    """Mark the log records of freshly translated strings as Translated."""
    for source_text, translated_text in translations.items():
        try:
            logs = frappe.get_all(
                "Missing Translation Log",
                filters={"source_text": source_text, "status": "Open"},
                pluck="name",
            )
            for log_name in logs:
                frappe.db.set_value(
                    "Missing Translation Log",
                    log_name,
                    {
                        "translated_text": translated_text,
                        "status": "Translated",
                        "translation_source": "Auto",
                        "translated_on": now_datetime(),
                    },
                    update_modified=False,
                )
        except Exception:  # noqa: BLE001 - logging must never break a boot
            frappe.logger(APP_NAME).error(
                f"Failed to mark log {source_text[:40]!r} as translated", exc_info=True
            )


# --------------------------------------------------------------------------- #
# AI auto-fill
# --------------------------------------------------------------------------- #

def _app_memory(app: str) -> Dict[str, str]:
    """Translation memory for an app: its own newest translations."""
    try:
        return read_official_translations(app)
    except Exception:  # noqa: BLE001
        return {}


def _auto_translate_via_api(missing, api_cfg: Optional[Dict] = None) -> Dict[str, str]:
    """Translate the missing entries with the configured provider.

    Configuration always comes from :func:`custom_translations.config.load_config`
    (env vars > ``config.json`` > ``site_config.json`` > defaults). A partial
    dict passed by a caller is merged over it rather than used as-is - that was
    the bug which made the boot-time path a permanent no-op.

    Existing translations are never overwritten (``overwrite=False``).
    Returns the accepted ``{source: translation}`` mapping.
    """
    from custom_translations.professional_glossary import PROFESSIONAL_GLOSSARY
    from custom_translations.translate import translate_entries

    config = load_config()
    if api_cfg:
        config = {**config, **{k: v for k, v in api_cfg.items() if v is not None}}
        config["is_configured"] = bool(
            config.get("api_key") and config.get("api_endpoint") and config.get("model")
        )

    logger = frappe.logger(APP_NAME)
    if not config.get("is_configured"):
        from custom_translations.config import get_setup_instructions

        logger.warning("Auto-translation skipped: API not configured.\n" + get_setup_instructions())
        return {}

    max_length = int(config.get("max_length") or 500)
    existing = load_app_translations()
    entries: List[str] = []
    for item in missing:
        msgid = item["msgid"] if isinstance(item, dict) else str(item)
        if not msgid or msgid in existing or len(msgid) > max_length:
            continue
        entries.append(msgid)

    if not entries:
        logger.info("No new entries to translate (all already translated)")
        return {}

    # Translation memory: the app that owns the string knows its own vocabulary.
    app_of = {}
    for item in missing:
        if isinstance(item, dict) and item.get("app"):
            app_of.setdefault(item["app"], None)
    memory: Dict[str, str] = {}
    for app in app_of:
        memory.update(_app_memory(app))

    try:
        result = translate_entries(
            entries,
            config,
            glossary=PROFESSIONAL_GLOSSARY,
            memory=memory,
            logger=logger,
        )
    except Exception:  # noqa: BLE001
        logger.error("API auto-translation failed", exc_info=True)
        return {}

    if result.translations:
        _append_to_csv(result.translations, overwrite=False)
        _mark_logs_translated(result.translations)
        logger.info(
            f"Auto-translated {len(result.translations)} entries "
            f"({result.repaired} repaired, {result.rejected_count} rejected, "
            f"{result.api_calls} API calls); preserved {len(existing)} existing translations"
        )
    return result.translations


def _translate_via_openai_compat(entries: Sequence[str], api_cfg: Dict) -> List[str]:
    """Backwards-compatible helper: translate a list, return a list."""
    from custom_translations.translate import translate_entries

    result = translate_entries(list(entries), api_cfg)
    return [result.translations.get(entry, "") for entry in entries]


#: old name kept so third-party imports keep working
_translate_via_deepseek = _translate_via_openai_compat


# --------------------------------------------------------------------------- #
# Manual corrections and terminology repair
# --------------------------------------------------------------------------- #

def on_translation_update(doc, method=None):
    """Persist manual ``Translation`` records into this app's CSV.

    Manual edits always win (``overwrite=True``), so they survive cache clears
    and framework upgrades.
    """
    if doc.language != SUPPORTED_LANG:
        return
    if not doc.source_text or not doc.translated_text:
        return
    _append_to_csv({doc.source_text: doc.translated_text}, overwrite=True)


def apply_manual_corrections() -> int:
    """Copy reviewed/manual log records into the CSV (overwriting auto results).

    A record qualifies when ``status == "Reviewed"`` **or**
    ``translation_source == "Manual"``. The original code passed both
    ``filters`` and ``or_filters``; Frappe ANDs those, so every record whose
    status was not exactly ``Reviewed`` was silently dropped.
    """
    manual_records = frappe.get_all(
        "Missing Translation Log",
        or_filters=[
            {"status": "Reviewed"},
            {"translation_source": "Manual"},
        ],
        fields=["source_text", "translated_text"],
        limit_page_length=0,
    )

    corrections = {
        _row(record, "source_text"): _row(record, "translated_text")
        for record in manual_records
        if _row(record, "source_text") and _row(record, "translated_text")
    }
    if not corrections:
        return 0

    changed = _append_to_csv(corrections, overwrite=True)
    frappe.logger(APP_NAME).info(
        f"Applied {changed} manual corrections to CSV ({len(corrections)} candidates)"
    )
    return changed


def fix_batch_terminology(dry_run: bool = False) -> int:
    """Repair Taiwan wording / systematic mistranslations in this app's CSV.

    Rules are guarded by the English source string (see
    :mod:`custom_translations.terminology`), so - unlike the previous blind
    ``str.replace`` - ``Reporting Currency`` is not turned into ``报表货币``
    and ``... can be reported`` is not turned into ``报表漏洞``.

    Returns the number of entries corrected.
    """
    existing = load_app_translations()
    if not existing:
        return 0

    fixed, changes = fix_translations(existing)
    if changes and not dry_run:
        _append_to_csv(fixed, overwrite=True)
        frappe.logger(APP_NAME).info(f"Fixed {len(changes)} entries with terminology rules")
    return len(changes)


# --------------------------------------------------------------------------- #
# Boot hook (throttled) + scheduler
# --------------------------------------------------------------------------- #

def _cache_get(key):
    try:
        return frappe.cache.get_value(key)
    except Exception:  # noqa: BLE001
        try:
            return frappe.cache().get_value(key)
        except Exception:  # noqa: BLE001
            return None


def _cache_set(key, value, ttl: int) -> None:
    try:
        frappe.cache.set_value(key, value, expires_in_sec=ttl)
    except Exception:  # noqa: BLE001
        try:
            frappe.cache().set_value(key, value, expires_in_sec=ttl)
        except Exception:  # noqa: BLE001
            pass


def _scan_cache_key(apps: Sequence[str]) -> str:
    return SCAN_CACHE_KEY + ":" + ",".join(sorted(apps))


def _get_missing_cached(config: Dict, apps: Optional[Sequence[str]] = None):
    """Scan (and cache) the missing translations of the installed apps.

    Parsing every app's PO/POT plus this app's 16k CSV on every desk boot is
    far too expensive, so the result is cached for ``scan_interval_seconds``.
    """
    apps = list(apps) if apps is not None else get_installed_apps()
    ttl = int(config.get("scan_interval_seconds") or DEFAULT_SCAN_INTERVAL)
    key = _scan_cache_key(apps)
    cached = _cache_get(key)
    if cached is not None:
        return cached
    missing = _scan_missing_translations(apps)
    _cache_set(key, missing, ttl)
    return missing


def invalidate_scan_cache() -> None:
    """Drop the cached scan so the next boot rescans."""
    for app in get_installed_apps(include_self=True):
        _cache_set(_scan_cache_key([app]), None, 1)
    _cache_set(_scan_cache_key(get_installed_apps()), None, 1)


def _enqueue_auto_translate(missing) -> bool:
    """Run the API translation in a background job (never inside a request)."""
    try:
        frappe.enqueue(
            "custom_translations.utils._auto_translate_via_api",
            queue="long",
            timeout=3600,
            job_name="custom_translations_auto_translate",
            missing=missing,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        frappe.logger(APP_NAME).warning(f"Could not enqueue auto-translation: {exc}")
        return False


def detect_app_versions() -> Dict[str, str]:
    """Return ``{app: __version__}`` for the installed upstream apps.

    Reads each app's Python package ``__version__`` attribute - the same value
    ``bench version`` reports.  Apps that are not installed (or fail to
    import) are simply omitted, so this function never raises.
    """
    import importlib

    versions: Dict[str, str] = {}
    for app in get_installed_apps(include_self=False) or ("frappe", "erpnext", "hrms", "helpdesk"):
        try:
            module = importlib.import_module(app)
        except Exception:  # noqa: BLE001 - app not importable in this env
            continue
        version = str(getattr(module, "__version__", "") or "")
        if version:
            versions[app] = version
    return versions


def detect_site_version() -> str:
    """Version of the frappe framework running this bench (e.g. ``16.8.0``).

    Historically this read ``site_config['frappe_version']``, but that key
    does not exist in site_config.json, and the fallback ``frappe.get_var``
    is not a real API - the function could only ever return ``""``.  The
    framework package version is available offline and always correct.
    """
    return detect_app_versions().get("frappe", "")


def detect_missing_translations_bootinfo(bootinfo=None):
    """``extend_bootinfo`` hook: log newly missing Chinese strings.

    Cheap by design: the expensive scan is cached (default 6h) and the API is
    never called synchronously - it is queued as a background job instead, so a
    desk boot can never block on a 120s HTTP timeout.
    """
    try:
        if frappe.session.user == "Guest":
            return

        lang = getattr(frappe.local, "lang", None) or frappe.db.get_default("language")
        if not lang or not str(lang).startswith("zh"):
            return

        config = load_config()
        if not config.get("scan_on_boot", True):
            return

        missing = _get_missing_cached(config)
        if not missing:
            return

        _log_missing_translations(missing)

        if config.get("auto_translate") and config.get("is_configured"):
            _enqueue_auto_translate(missing)
    except Exception:  # noqa: BLE001 - a boot hook must never break the desk
        frappe.logger(APP_NAME).error("Failed to detect missing translations", exc_info=True)


def scheduled_translation_scan() -> Dict:
    """Daily scheduler job: scan, log and optionally auto-translate."""
    config = load_config()
    missing = _scan_missing_translations()
    logged = _log_missing_translations(missing) if missing else 0
    translated = {}
    if missing and config.get("auto_translate") and config.get("is_configured"):
        translated = _auto_translate_via_api(missing)
    frappe.db.commit()
    summary = {
        "missing": len(missing),
        "logged": logged,
        "translated": len(translated),
    }
    frappe.logger(APP_NAME).info(f"Scheduled translation scan: {summary}")
    return summary


# --------------------------------------------------------------------------- #
# Optional: fill the apps' own PO files
# --------------------------------------------------------------------------- #

def sync_to_po_files(
    apps: Optional[Sequence[str]] = None,
    force: bool = False,
    wait_seconds: int = 3,
) -> Dict[str, int]:
    """OPTIONAL: fill empty ``msgstr`` entries of the apps' own PO files.

    Translations already work through this app's CSV; this only compiles them
    into the ``.mo`` binaries for a marginal speed-up. It edits official files,
    so it is opt-in and never touches a file it cannot find.

    The previous version hardcoded ``frappe, erpnext, hrms, payments, webshop``
    and ``<app>/locale/zh.po``; it therefore did nothing for ERPNext/HRMS on
    v14/v15 (which ship ``translations/zh.csv`` and no ``locale/`` at all) and
    skipped helpdesk/wiki/telephony entirely. This version discovers the files.

    Returns ``{po_path: filled_count}``.
    """
    import time

    ours = load_app_translations()
    if not ours:
        print(f"No translations found in {get_csv_path()}")
        return {}

    targets = list(apps) if apps is not None else get_installed_apps()
    po_targets = []
    for app in targets:
        sources = discover_app(app)
        for po_path in sources.po_files:
            po_targets.append((app, po_path))

    if not po_targets:
        print("No PO based translation files found for the installed apps.")
        print("Nothing to do - translations are already served from this app's CSV.")
        return {}

    print(f"Loaded {len(ours)} translations from {get_csv_path()}")
    print("Will fill empty msgstr entries in:")
    for app, po_path in po_targets:
        print(f"  [{app}] {po_path}")
    if not force:
        print(f"Proceeding in {wait_seconds} seconds... (Ctrl+C to cancel)\n")
        time.sleep(wait_seconds)

    results: Dict[str, int] = {}
    touched_apps: List[str] = []
    for app, po_path in po_targets:
        filled = po.fill_po_file(po_path, ours)
        results[str(po_path)] = filled
        if filled:
            touched_apps.append(app)
            print(f"  [{app}] filled {filled} entries")
        else:
            print(f"  [{app}] nothing to fill")

    if touched_apps:
        print("\nRecompiling .mo files...")
        for app in dict.fromkeys(touched_apps):
            os.system(f"bench compile-po-to-mo --app {app}")
        print("Clearing cache...")
        os.system("bench --site all clear-cache")
    else:
        print("\nNothing to sync - all translations already in place.")
    return results
