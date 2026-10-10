"""
Frappe-free maintenance CLI.

Some maintenance tasks (terminology correction, CSV auditing) do not need a
site at all, so they can run in CI or on a laptop without ``bench``::

    python -m custom_translations.cli fix-csv --dry-run
    python -m custom_translations.cli fix-csv
    python -m custom_translations.cli audit-csv

Everything else (scanning installed apps, talking to the API, writing the
``Missing Translation Log``) needs a site and is exposed as ``bench`` commands
instead - see ``custom_translations/commands.py``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from custom_translations.csvio import CsvEntry, read_csv_entries, write_csv_entries
from custom_translations.terminology import fix_translation

__all__ = ["default_csv_path", "fix_csv", "audit_csv", "main"]

APP_DIR = Path(__file__).resolve().parent


def default_csv_path() -> Path:
    """Path of this app's own ``translations/zh.csv``."""
    return APP_DIR / "translations" / "zh.csv"


def fix_csv(path: Optional[Path | str] = None, dry_run: bool = False) -> int:
    """Apply the context-aware terminology rules to a translation CSV.

    Returns the number of rows that changed.
    """
    target_path = Path(path) if path else default_csv_path()
    entries = read_csv_entries(target_path)
    if not entries:
        print(f"No entries found in {target_path}")
        return 0

    changed: List[tuple] = []
    updated: List[CsvEntry] = []
    for entry in entries:
        new_value, notes = fix_translation(entry.msgid, entry.msgstr)
        if new_value != entry.msgstr:
            changed.append((entry.msgid, entry.msgstr, new_value, notes))
            entry = CsvEntry(msgid=entry.msgid, msgstr=new_value, context=entry.context)
        updated.append(entry)

    print(f"{target_path}: {len(entries)} entries, {len(changed)} corrections")
    for msgid, before, after, notes in changed:
        print(f"  {msgid[:70]!r}\n    - {before[:70]!r}\n    + {after[:70]!r}\n      ({', '.join(notes)})")

    if changed and not dry_run:
        write_csv_entries(target_path, updated)
        print(f"Written: {target_path}")
    elif changed:
        print("Dry run - nothing written")
    return len(changed)


def audit_csv(path: Optional[Path | str] = None) -> dict:
    """Report structural facts about a translation CSV."""
    target_path = Path(path) if path else default_csv_path()
    entries = read_csv_entries(target_path)
    keys = [entry.msgid for entry in entries]
    duplicates = len(keys) - len(set(keys))
    empty = [entry for entry in entries if not entry.msgstr.strip()]
    padded_keys = [entry for entry in entries if entry.msgid != entry.msgid.strip()]
    padded_values = [entry for entry in entries if entry.msgstr != entry.msgstr.strip()]
    report = {
        "path": str(target_path),
        "entries": len(entries),
        "unique": len(set(keys)),
        "duplicates": duplicates,
        "empty_translations": len(empty),
        "padded_keys": len(padded_keys),
        "padded_values": len(padded_values),
    }
    for key, value in report.items():
        print(f"{key}: {value}")
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m custom_translations.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    fix = sub.add_parser("fix-csv", help="apply terminology corrections to a CSV")
    fix.add_argument("--path", default=None, help="CSV path (default: translations/zh.csv)")
    fix.add_argument("--dry-run", action="store_true", help="only report changes")

    audit = sub.add_parser("audit-csv", help="report structural facts about a CSV")
    audit.add_argument("--path", default=None, help="CSV path (default: translations/zh.csv)")

    args = parser.parse_args(argv)
    if args.command == "fix-csv":
        fix_csv(args.path, dry_run=args.dry_run)
        return 0
    if args.command == "audit-csv":
        audit_csv(args.path)
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
