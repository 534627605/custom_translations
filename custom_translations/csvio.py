"""
Frappe translation CSV reader/writer.

Frappe loads per-app translations from ``<app>/translations/<lang>.csv`` (see
``frappe.translate.get_translations_from_csv``). The file is a plain 2 column
CSV ``source,translation``; a 3rd column (``context``) is supported by the
framework and is addressed with the ``msgid:context`` key convention.

Behaviour kept identical to the framework:

* a literal newline inside a message is stored as the two characters ``\\n``
* the framework strips the *translation* (not the source) when loading

Unlike the original implementation this reader keeps 3 column rows intact so a
read-modify-write cycle can never silently drop a context column.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

__all__ = [
    "CsvEntry",
    "detect_lineterminator",
    "read_csv_entries",
    "write_csv_entries",
    "read_csv_translations",
    "entries_to_dict",
    "make_key",
]


@dataclass(frozen=True)
class CsvEntry:
    """A single row of a translation CSV."""

    msgid: str
    msgstr: str
    context: Optional[str] = None

    @property
    def key(self) -> str:
        return make_key(self.msgid, self.context)


def make_key(msgid: str, context: Optional[str] = None) -> str:
    """Return the lookup key Frappe uses for a message."""
    if context:
        return f"{msgid}:{context}"
    return msgid


def _unescape(value: str) -> str:
    return value.replace("\\n", "\n")


def _escape(value: str) -> str:
    return value.replace("\n", "\\n")


def read_csv_entries(path: Path | str) -> List[CsvEntry]:
    """Read a translation CSV into a list of :class:`CsvEntry`.

    Rows that are empty, malformed, or have an empty source are skipped.
    """
    entries: List[CsvEntry] = []
    try:
        with open(path, "r", encoding="utf-8", newline="") as handle:
            for row in csv.reader(handle):
                if not row or not row[0].strip():
                    continue
                msgid = _unescape(row[0])
                msgstr = _unescape(row[1]) if len(row) > 1 else ""
                context = row[2] if len(row) > 2 and row[2] else None
                entries.append(CsvEntry(msgid=msgid, msgstr=msgstr, context=context))
    except (OSError, UnicodeDecodeError, csv.Error):
        return []
    return entries


def read_csv_translations(path: Path | str) -> Dict[str, str]:
    """Read a translation CSV into a ``{key: translation}`` dict."""
    return entries_to_dict(read_csv_entries(path))


def entries_to_dict(entries: Iterable[CsvEntry]) -> Dict[str, str]:
    """Convert entries to the dict shape Frappe uses at runtime."""
    return {entry.key: entry.msgstr for entry in entries}


def detect_lineterminator(path: Path | str, default: str = "\n") -> str:
    """Return the line terminator a translation CSV currently uses.

    Rewriting a 16k line data file with different line endings would produce a
    whole-file diff, so the existing style is preserved.
    """
    try:
        with open(path, "rb") as handle:
            chunk = handle.read(8192)
    except OSError:
        return default
    if b"\r\n" in chunk:
        return "\r\n"
    if b"\n" in chunk:
        return "\n"
    return default


def write_csv_entries(
    path: Path | str,
    entries: Sequence[CsvEntry],
    lineterminator: Optional[str] = None,
) -> None:
    """Write entries to a translation CSV.

    When ``lineterminator`` is None the existing file's line ending is kept
    (new files use ``\n``, matching ``frappe.translate.write_csv_file``).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if lineterminator is None:
        lineterminator = detect_lineterminator(path)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator=lineterminator)
        for entry in entries:
            row = [_escape(entry.msgid), _escape(entry.msgstr)]
            if entry.context:
                row.append(entry.context)
            writer.writerow(row)
