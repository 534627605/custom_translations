"""
Dependency-free PO (gettext) reader/writer helpers.

Why this module exists
----------------------
The original app relied on `babel` for every PO operation and silently did
nothing when babel was not installed (`_scan_missing_translations()` returned
`[]`). babel is *not* a Frappe dependency, so on most production benches the
whole "detect missing translations" feature was dead code.

This module provides:

* `parse_po_text()` / `read_po_file()` - a small, correct PO parser with no
  third-party dependency (used for reading).
* `fill_po_file()` - an **in-place, line based** writer that only replaces the
  `msgstr` of the entries we actually change. Comments, references, ordering
  and formatting of the original file are preserved byte for byte, which a
  babel round-trip does not guarantee.

The parser handles the subset of PO that gettext/Frappe actually emit:
msgctxt, msgid, msgid_plural, msgstr, msgstr[n], multi-line strings,
escapes, and `#, fuzzy` flags.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

__all__ = [
    "PoEntry",
    "parse_po_text",
    "read_po_file",
    "unescape",
    "escape",
    "fill_po_file",
    "iter_translated",
    "iter_untranslated",
]

_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "0": "\0"}
_UNESCAPES = {v: k for k, v in _ESCAPES.items()}

_FIELD_RE = re.compile(r'^(msgctxt|msgid|msgid_plural|msgstr)(?:\[(\d+)\])?\s+(.*)$')
_CONT_RE = re.compile(r'^\s*"(.*)"\s*$')


def unescape(text: str) -> str:
    """Turn PO escaped text into the real string."""
    out: List[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            out.append(_ESCAPES.get(nxt, nxt))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def escape(text: str) -> str:
    """Turn a real string into PO escaped text (single line, no quotes)."""
    out: List[str] = []
    for ch in text:
        if ch in _UNESCAPES:
            out.append("\\" + _UNESCAPES[ch])
        elif ch == "\n":
            out.append("\\n")
        else:
            out.append(ch)
    return "".join(out)


@dataclass
class PoEntry:
    """One message entry of a PO file."""

    msgid: str = ""
    msgstr: str = ""
    msgctxt: Optional[str] = None
    msgid_plural: Optional[str] = None
    msgstr_plural: Dict[int, str] = field(default_factory=dict)
    fuzzy: bool = False
    obsolete: bool = False
    #: 1-based line number of the `msgid` line in the source file
    lineno: int = 0
    #: 1-based line numbers of the `msgstr` (or `msgstr[n]`) lines
    msgstr_lines: List[int] = field(default_factory=list)

    @property
    def key(self) -> str:
        """Translation key, matching Frappe's `msgctxt:msgid` convention."""
        if self.msgctxt:
            return f"{self.msgctxt}:{self.msgid}"
        return self.msgid

    @property
    def is_header(self) -> bool:
        return self.msgid == "" and not self.msgctxt

    @property
    def translated(self) -> bool:
        if self.msgid_plural is not None:
            return bool(self.msgstr_plural) and all(
                str(v).strip() for v in self.msgstr_plural.values()
            )
        return bool(self.msgstr.strip())

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<PoEntry {self.key!r} -> {self.msgstr!r}>"



def parse_po_text(text: str) -> List[PoEntry]:
    """Parse PO text into a list of :class:`PoEntry`.

    Tolerant by design: malformed lines are skipped instead of raising, so a
    partially translated / hand-edited PO file never breaks a site boot.
    """
    entries: List[PoEntry] = []
    entry: Optional[PoEntry] = None
    current: Optional[str] = None  # which field the last line belonged to
    current_plural: Optional[int] = None
    fuzzy = False

    def flush() -> None:
        nonlocal entry, current, current_plural, fuzzy
        if entry is not None:
            entry.fuzzy = entry.fuzzy or fuzzy
            entries.append(entry)
        entry = None
        current = None
        current_plural = None
        fuzzy = False

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            # A blank line terminates the current entry.
            if entry is not None:
                flush()
            continue

        if line.startswith("#"):
            if line.startswith("#~"):
                if entry is not None:
                    entry.obsolete = True
            elif line.startswith("#,") and "fuzzy" in line:
                fuzzy = True
            continue

        match = _FIELD_RE.match(line)
        if match:
            name, plural_index, rest = match.group(1), match.group(2), match.group(3)
            value = ""
            quoted = _CONT_RE.match(rest)
            if quoted:
                value = unescape(quoted.group(1))
            if name == "msgctxt":
                entry = entry or PoEntry(lineno=lineno)
                entry.msgctxt = value
                current, current_plural = "msgctxt", None
            elif name == "msgid":
                if entry is not None and entry.msgid:
                    # a second msgid starts a new entry
                    flush()
                entry = entry or PoEntry()
                entry.lineno = lineno
                entry.msgid = value
                current, current_plural = "msgid", None
            elif name == "msgid_plural":
                entry = entry or PoEntry(lineno=lineno)
                entry.msgid_plural = value
                current, current_plural = "msgid_plural", None
            elif name == "msgstr":
                entry = entry or PoEntry(lineno=lineno)
                entry.msgstr_lines.append(lineno)
                if plural_index is None:
                    entry.msgstr = value
                    current, current_plural = "msgstr", None
                else:
                    idx = int(plural_index)
                    entry.msgstr_plural[idx] = value
                    current, current_plural = "msgstr", idx
            continue

        cont = _CONT_RE.match(line)
        if cont and entry is not None and current is not None:
            value = unescape(cont.group(1))
            if current == "msgctxt":
                entry.msgctxt = (entry.msgctxt or "") + value
            elif current == "msgid":
                entry.msgid += value
            elif current == "msgid_plural":
                entry.msgid_plural = (entry.msgid_plural or "") + value
            elif current == "msgstr":
                if current_plural is None:
                    entry.msgstr += value
                else:
                    entry.msgstr_plural[current_plural] = (
                        entry.msgstr_plural.get(current_plural, "") + value
                    )
            continue

    if entry is not None:
        flush()

    return entries


def read_po_file(path: Path | str) -> List[PoEntry]:
    """Read a PO file, returning `[]` when it cannot be read."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return parse_po_text(text)


def iter_translated(entries: Iterable[PoEntry]) -> Iterator[Tuple[str, str]]:
    """Yield `(msgid, msgstr)` for entries that have a translation."""
    for entry in entries:
        if entry.is_header or entry.obsolete:
            continue
        if entry.translated:
            yield entry.msgid, entry.msgstr


def iter_untranslated(entries: Iterable[PoEntry]) -> Iterator[PoEntry]:
    """Yield entries whose msgstr is empty."""
    for entry in entries:
        if entry.is_header or entry.obsolete:
            continue
        if not entry.translated:
            yield entry



def _render_msgstr_line(prefix: str, value: str) -> List[str]:
    """Render `msgstr "..."` lines, keeping single-line entries single-line."""
    if "\n" not in value:
        return [f'{prefix} "{escape(value)}"']
    parts = value.split("\n")
    out = [f'{prefix} ""']
    for i, part in enumerate(parts):
        suffix = "\\n" if i < len(parts) - 1 else ""
        out.append(f'"{escape(part)}{suffix}"')
    return out


def fill_po_file(path: Path | str, translations: Dict[str, str]) -> int:
    """Fill empty `msgstr` entries of a PO file **in place**.

    Only entries that are currently untranslated and present in
    ``translations`` are touched; every other byte of the file (comments,
    source references, ordering, header) is preserved. Returns the number of
    entries that were filled.
    """
    path = Path(path)
    try:
        original = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0

    targets: Dict[int, List[str]] = {}
    for entry in parse_po_text(original):
        if entry.is_header or entry.obsolete or entry.translated:
            continue
        if entry.msgid_plural is not None:
            continue  # plurals need per-index handling, skip for safety
        value = translations.get(entry.msgid)
        if value is None or not str(value).strip():
            continue
        if not entry.msgstr_lines:
            continue
        targets[entry.msgstr_lines[0]] = _render_msgstr_line("msgstr", str(value))

    if not targets:
        return 0

    out_lines: List[str] = []
    for lineno, line in enumerate(original.splitlines(), start=1):
        if lineno in targets:
            out_lines.extend(targets[lineno])
        else:
            out_lines.append(line)

    newline = "\r\n" if "\r\n" in original else "\n"
    path.write_text(newline.join(out_lines) + newline, encoding="utf-8")
    return len(targets)
