"""
Translation source discovery for every Frappe app layout.

The original app hardcoded one single path - ``<app>/locale/zh.po`` - and
therefore silently did nothing for any app that ships its Chinese translations
differently. That is no longer a corner case: today the ecosystem uses at least
these layouts (verified against the upstream repositories):

    frappe        <app>/locale/zh.po            + <app>/locale/main.pot
    erpnext       <app>/translations/zh.csv     (no locale/ dir at all)
    hrms          <app>/locale/zh.po
    payments      <app>/translations/zh.csv
    wiki          <app>/translations/zh.csv
    helpdesk      <app>/translations/zh.csv
    webshop       <app>/translations/zh.csv
    telephony     <app>/translations/zh.csv

This module probes all known locations (``translations/``, ``locale/`` and
``translations/locale/``, both inside the app module and at the app source
root) and all known Chinese file names, so coverage detection works for PO
based *and* CSV based apps.

When an app ships no PO/POT inventory at all (the CSV-only apps), the list of
translatable source strings is recovered by scanning the app's own source files
for ``_("...")`` / ``__("...")`` calls - the same strings ``bench
generate-pot-file`` would collect.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from custom_translations.csvio import read_csv_translations
from custom_translations.po import iter_translated, read_po_file

__all__ = [
    "AppSources",
    "SourceInventory",
    "discover_app",
    "get_module_dir",
    "read_official_translations",
    "source_inventory",
    "extract_msgids",
    "extract_msgids_from_dir",
    "SUPPORTED_LANG",
]

SUPPORTED_LANG = "zh"

#: Directories (relative to the app module / source root) that may hold translations
TRANSLATION_DIRS: Tuple[str, ...] = (
    "translations",
    "locale",
    os.path.join("translations", "locale"),
)

#: Chinese PO file names used by Frappe / ERPNext ecosystem apps
CHINESE_PO_NAMES: Tuple[str, ...] = (
    "zh.po",
    "zh_CN.po",
    "zh_Hans.po",
    "zh_CN.UTF-8.po",
    "zh_Hans_CN.po",
)

#: Chinese CSV file names
CHINESE_CSV_NAMES: Tuple[str, ...] = ("zh.csv", "zh_CN.csv", "zh_Hans.csv")

#: POT templates that carry the "all translatable strings" inventory
POT_NAMES: Tuple[str, ...] = ("main.pot", "messages.pot")

#: File extensions scanned when no POT/PO inventory is available
SOURCE_EXTENSIONS: Tuple[str, ...] = (".py", ".js", ".html", ".vue")

#: Directories never scanned for source strings
SKIP_DIRS: Set[str] = {
    ".git",
    ".github",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    "docs",
    "e2e",
}

#: `_(` / `__(` / `frappe._(` call sites
_CALL_RE = re.compile(r"(?:frappe\s*\.\s*)?(__|_)\s*\(")
_PRECEDING_RE = re.compile(r"[\w.]")


def get_module_dir(app: str) -> Optional[Path]:
    """Return the Python module directory of an installed app, or None."""
    try:
        import frappe  # noqa: WPS433 (optional import by design)

        return Path(frappe.get_app_path(app))
    except Exception:
        return None


@dataclass
class AppSources:
    """Translation files found for a single app."""

    app: str
    module_dir: Optional[Path] = None
    po_files: List[Path] = field(default_factory=list)
    csv_files: List[Path] = field(default_factory=list)
    pot_files: List[Path] = field(default_factory=list)
    searched: List[Path] = field(default_factory=list)

    @property
    def has_any(self) -> bool:
        return bool(self.po_files or self.csv_files or self.pot_files)

    @property
    def format(self) -> str:
        """Human readable format description, e.g. ``csv`` or ``po+csv``."""
        kinds = []
        if self.po_files:
            kinds.append("po")
        if self.csv_files:
            kinds.append("csv")
        if self.pot_files:
            kinds.append("pot")
        return "+".join(kinds) if kinds else "none"

    def describe(self) -> str:
        parts = [f"module_dir={self.module_dir}"]
        for label, files in (
            ("po", self.po_files),
            ("csv", self.csv_files),
            ("pot", self.pot_files),
        ):
            if files:
                parts.append(f"{label}={', '.join(str(f) for f in files)}")
        return f"[{self.app}] " + "; ".join(parts)


def _candidate_roots(module_dir: Path) -> List[Path]:
    roots = [module_dir]
    parent = module_dir.parent
    if parent != module_dir:
        roots.append(parent)
    return roots


def discover_app(app: str, module_dir: Optional[Path | str] = None) -> AppSources:
    """Locate every Chinese translation file of ``app``."""
    sources = AppSources(app=app)
    resolved = Path(module_dir) if module_dir else get_module_dir(app)
    if not resolved or not resolved.exists():
        return sources
    sources.module_dir = resolved

    seen: Set[Path] = set()
    for root in _candidate_roots(resolved):
        for sub in TRANSLATION_DIRS:
            directory = root / sub
            if not directory.is_dir():
                continue
            sources.searched.append(directory)
            for name in CHINESE_PO_NAMES:
                candidate = directory / name
                if candidate.is_file() and candidate not in seen:
                    seen.add(candidate)
                    sources.po_files.append(candidate)
            for name in CHINESE_CSV_NAMES:
                candidate = directory / name
                if candidate.is_file() and candidate not in seen:
                    seen.add(candidate)
                    sources.csv_files.append(candidate)
            for name in POT_NAMES + (f"{app}.pot",):
                candidate = directory / name
                if candidate.is_file() and candidate not in seen:
                    seen.add(candidate)
                    sources.pot_files.append(candidate)
    return sources


def read_official_translations(
    app: str, module_dir: Optional[Path | str] = None
) -> Dict[str, str]:
    """Return the app's *own* Chinese translations (CSV first, then PO)."""
    sources = discover_app(app, module_dir)
    translations: Dict[str, str] = {}
    for csv_path in sources.csv_files:
        translations.update(read_csv_translations(csv_path))
    for po_path in sources.po_files:
        for msgid, msgstr in iter_translated(read_po_file(po_path)):
            translations.setdefault(msgid, msgstr)
    return translations



# --------------------------------------------------------------------------- #
# Source string extraction (inventory for CSV-only apps)
# --------------------------------------------------------------------------- #

def _read_string_literals(text: str, pos: int) -> Optional[str]:
    """Read a (possibly implicitly concatenated) string literal at ``pos``."""
    length = len(text)
    pieces: List[str] = []
    found = False
    while pos < length:
        while pos < length and text[pos] in " \t\r\n":
            pos += 1
        if pos >= length or text[pos] not in "\"'":
            break
        quote = text[pos]
        pos += 1
        buffer: List[str] = []
        closed = False
        while pos < length:
            char = text[pos]
            if char == "\\" and pos + 1 < length:
                buffer.append(char)
                buffer.append(text[pos + 1])
                pos += 2
                continue
            if char == quote:
                closed = True
                pos += 1
                break
            buffer.append(char)
            pos += 1
        if not closed:
            break
        found = True
        pieces.append("".join(buffer))
    if not found:
        return None
    return "".join(pieces)


def _unescape_python(value: str) -> str:
    """Best effort unescape of a Python/JS string literal body."""
    out: List[str] = []
    i = 0
    while i < len(value):
        char = value[i]
        if char == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            out.append({"n": "\n", "t": "\t", "r": "\r"}.get(nxt, nxt))
            i += 2
            continue
        out.append(char)
        i += 1
    return "".join(out)


def extract_msgids(text: str) -> Set[str]:
    """Extract every ``_("...")`` / ``__("...")`` string of a source file."""
    found: Set[str] = set()
    for match in _CALL_RE.finditer(text):
        start = match.start()
        if start > 0 and _PRECEDING_RE.match(text[start - 1]):
            continue
        raw = _read_string_literals(text, match.end())
        if raw is None:
            continue
        value = _unescape_python(raw)
        if value.strip():
            found.add(value)
    return found


def extract_msgids_from_dir(module_dir: Path | str) -> Set[str]:
    """Extract source strings from every Python/JS/HTML/Vue file of an app."""
    found: Set[str] = set()
    root = Path(module_dir)
    if not root.is_dir():
        return found
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name for name in dirnames if name not in SKIP_DIRS and not name.startswith(".")
        ]
        for filename in filenames:
            if not filename.endswith(SOURCE_EXTENSIONS):
                continue
            path = Path(dirpath) / filename
            try:
                if path.stat().st_size > 2_000_000:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if "_(" not in text:
                continue
            found |= extract_msgids(text)
    return found


@dataclass
class SourceInventory:
    """All translatable strings of an app plus where they came from."""

    app: str
    msgids: Set[str] = field(default_factory=set)
    origin: str = "none"  # pot | po | source | none
    sources: Optional[AppSources] = None

    def __len__(self) -> int:
        return len(self.msgids)


def source_inventory(app: str, module_dir: Optional[Path | str] = None) -> SourceInventory:
    """Return every translatable string of ``app``.

    Priority: POT template > PO file > source scan. POT/PO are authoritative
    because they are generated by the framework; the source scan is the
    fallback for CSV-only apps that ship no template at all.
    """
    sources = discover_app(app, module_dir)
    inventory = SourceInventory(app=app, sources=sources)

    for pot_path in sources.pot_files:
        entries = read_po_file(pot_path)
        msgids = {entry.msgid for entry in entries if entry.msgid and not entry.is_header}
        if msgids:
            inventory.msgids = msgids
            inventory.origin = "pot"
            return inventory

    for po_path in sources.po_files:
        entries = read_po_file(po_path)
        msgids = {entry.msgid for entry in entries if entry.msgid and not entry.is_header}
        if msgids:
            inventory.msgids = msgids
            inventory.origin = "po"
            return inventory

    if sources.module_dir:
        msgids = extract_msgids_from_dir(sources.module_dir)
        if msgids:
            inventory.msgids = msgids
            inventory.origin = "source"
    return inventory

    if parent != module_dir:
        roots.append(parent)
    return roots
