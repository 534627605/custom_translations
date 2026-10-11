"""Import official Chinese translations into the curated zh.csv.

Data source
-----------
The bench checkout already contains the upstream apps, and each app ships its
own Crowdin-maintained Chinese catalogue at ``<app>/<app>/locale/zh.po``.
Those files are the official translations *for the exact installed version*:
after every ``bench update`` they are refreshed together with the code, which
is precisely what "stay compatible with upstream releases" means.  Re-running
this command after an update pulls any new/changed upstream wording into the
override layer without any network access.

Merge semantics
---------------
* existing keys in ``zh.csv`` always win (hand-curated overrides are never
  clobbered) unless ``force=True`` is given;
* PO entries are matched with the same ``msgid:context`` key convention Frappe
  uses via :func:`custom_translations.csvio.make_key`;
* new entries are appended (existing row order is never reshuffled, keeping
  diffs minimal);
* untranslated (``msgstr ""``), fuzzy and obsolete PO entries are skipped.

Everything here is a pure function of the filesystem - no frappe import - so
it can be unit tested offline and reused by the bench command.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from custom_translations import csvio
from custom_translations.po import read_po_file

#: Upstream apps whose locale/zh.po is merged, in pull order.
OFFICIAL_APPS: Tuple[str, ...] = ("frappe", "erpnext", "hrms", "helpdesk")

#: Keyword set for the optional terminology-scoped import (``keywords=...``).
REQUIRED_KEYWORDS: Tuple[re.Pattern, ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bDoc ?Type\b",
        r"\bPayments?\b",
        r"\bInventory\b",
        r"\bLedgers?\b",
        r"\bReports?\b",
        r"\bJournals?\b",
        r"\bInvoices?\b",
        r"\bStock\b",
        r"\bWarehouses?\b",
        r"\bVouchers?\b",
        r"\bAccounts?\b",
        r"\bItems?\b",
        r"\bCustomers?\b",
        r"\bSuppliers?\b",
        r"\bEmployees?\b",
        r"\bPayrolls?\b",
        r"\bBOM\b",
    )
)


# --------------------------------------------------------------------------- #
# PO discovery & parsing
# --------------------------------------------------------------------------- #

def _bench_apps_dir() -> Path:
    """Return the bench ``apps/`` directory this module lives under."""
    # .../apps/custom_translations/custom_translations/sync_po.py -> .../apps
    return Path(__file__).resolve().parents[2]


def find_local_po(app: str, apps_dir: Optional[Path] = None) -> Optional[Path]:
    """Locate ``<app>/<app>/locale/zh.po`` inside the bench checkout."""
    apps_dir = apps_dir or _bench_apps_dir()
    candidates = (
        apps_dir / app / app / "locale" / "zh.po",
        apps_dir / app / "locale" / "zh.po",  # non-package layouts (rare)
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def default_po_paths(apps: Optional[Sequence[str]] = None) -> List[Path]:
    """Existing local official ``zh.po`` files for ``apps`` (default: known ones)."""
    wanted = tuple(apps) if apps else OFFICIAL_APPS
    paths: List[Path] = []
    for app in wanted:
        found = find_local_po(app)
        if found is not None:
            paths.append(found)
    return paths


def _parse_po(po_path: Path) -> Dict[str, str]:
    """Parse a PO file into ``{csv_key: translation}``.

    Returns an empty dict when the file does not exist.  Header, untranslated,
    fuzzy and obsolete entries are skipped.  Keys use the Frappe CSV
    convention ``msgid`` or ``msgid:context`` (:func:`csvio.make_key`).
    """
    po_path = Path(po_path)
    if not po_path.exists():
        return {}
    entries: Dict[str, str] = {}
    for entry in read_po_file(po_path):
        if entry.is_header or entry.fuzzy or entry.obsolete or not entry.translated:
            continue
        key = csvio.make_key(entry.msgid, entry.msgctxt)
        entries[key] = entry.msgstr
    return entries


def _filter_terms(entries: Dict[str, str]) -> Dict[str, str]:
    """Keep only entries whose source matches a professional keyword."""
    return {
        key: value
        for key, value in entries.items()
        if any(pattern.search(key) for pattern in REQUIRED_KEYWORDS)
    }


# --------------------------------------------------------------------------- #
# Merge
# --------------------------------------------------------------------------- #

def sync_po(
    csv_path: Optional[Path] = None,
    force: bool = False,
    *,
    apps: Optional[Sequence[str]] = None,
    po_paths: Optional[Sequence[Path]] = None,
    keywords: Optional[Iterable[re.Pattern]] = None,
) -> int:
    """Merge official translations into ``csv_path`` and return the change count.

    :param csv_path: destination CSV (defaults to this app's ``translations/zh.csv``)
    :param force: overwrite existing translations with the upstream wording
    :param apps: restrict to these apps' local PO files
    :param po_paths: explicit PO files (takes precedence over ``apps``)
    :param keywords: when given, only import entries matching one of these
        compiled patterns (e.g. :data:`REQUIRED_KEYWORDS`); ``None`` imports
        everything - which is what a *completion* sync should do.
    :return: number of added + updated rows
    """
    if csv_path is None:
        csv_path = Path(__file__).resolve().parent.parent / "translations" / "zh.csv"
    csv_path = Path(csv_path)

    paths = list(po_paths) if po_paths is not None else default_po_paths(apps)

    official: Dict[str, str] = {}
    for path in paths:
        official.update(_parse_po(path))

    if keywords is not None:
        patterns = tuple(keywords)
        official = {
            key: value
            for key, value in official.items()
            if any(pattern.search(key) for pattern in patterns)
        }

    existing: List[csvio.CsvEntry] = csvio.read_csv_entries(csv_path)
    by_key: Dict[str, csvio.CsvEntry] = {entry.key: entry for entry in existing}

    changed = 0
    merged: List[csvio.CsvEntry] = []
    for entry in existing:
        upstream = official.get(entry.key)
        if force and upstream and upstream != entry.msgstr:
            merged.append(
                csvio.CsvEntry(
                    msgid=entry.msgid, msgstr=upstream, context=entry.context
                )
            )
            changed += 1
        else:
            merged.append(entry)

    new_entries: List[csvio.CsvEntry] = []
    for key, value in official.items():
        if key not in by_key:
            new_entries.append(csvio.CsvEntry(msgid=key, msgstr=value))
            changed += 1

    merged.extend(new_entries)
    if changed:
        csvio.write_csv_entries(csv_path, merged)
    return changed
