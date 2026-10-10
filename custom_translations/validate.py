"""
Translation quality validation.

Machine translation of UI strings fails in predictable ways: placeholders get
translated, HTML tags get dropped, identifiers get "translated", or the model
just echoes the English back. The original app accepted whatever the API
returned, which is how garbage such as ``贷方金额（报表货币）`` for
*Reporting Currency* ended up in the shipped CSV.

This module provides cheap, deterministic checks that run on every translated
string *before* it is written to ``zh.csv``:

* placeholders (``{0}``, ``{}``, ``{name}``, ``%s``, ``%(name)s``) must survive
* Jinja blocks (``{{ ... }}``, ``{% ... %}``) must survive
* HTML/XML tags must survive with the same counts
* newline layout must survive
* prose must actually be translated (no English echo)
* no stray leading/trailing whitespace

``validate()`` returns a list of :class:`Issue`; ``is_acceptable()`` is the
boolean convenience used by the translation pipeline to decide whether an
entry is good enough to be written, retried, or dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Sequence

__all__ = [
    "Issue",
    "validate",
    "is_acceptable",
    "extract_placeholders",
    "extract_tags",
    "looks_like_prose",
    "is_sentence",
    "normalize",
]

# {0} {name} {} {0:,.2f}
_BRACE_PLACEHOLDER_RE = re.compile(r"\{(?:\d+|[a-zA-Z_][\w.]*)?(?:[!:][^{}]*)?\}")
# %s %d %(name)s %%
_PERCENT_PLACEHOLDER_RE = re.compile(r"%(?:\((?P<name>[^)]+)\))?[-+ #0]*[\d*]*(?:\.\d+)?[diouxXeEfFgGcrsa%]")
# {{ jinja }} and {% jinja %}
_JINJA_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.DOTALL)
# <b>, <br/>, </p>
_TAG_RE = re.compile(r"</?\s*[a-zA-Z][a-zA-Z0-9:-]*(?:\s[^<>]*)?/?>")
# URLs / emails / code identifiers
_URL_RE = re.compile(r"https?://\S+|[\w.+-]+@[\w-]+\.[\w.]+")
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff]")
_LATIN_WORD_RE = re.compile(r"[A-Za-z]{2,}")

#: words that are legitimately left in English inside a Chinese UI
_KEEP_ENGLISH = {
    "api", "json", "csv", "url", "uri", "pdf", "html", "css", "sql", "ssh", "smtp", "imap",
    "ldap", "oauth", "saml", "rest", "wsdl", "xml", "yaml", "http", "https", "ip", "uuid",
    "frappe", "erpnext", "doctype", "doctypes", "javascript", "python", "docker", "git",
    "id", "ids", "ok", "ui", "ux", "pos", "sku", "uom", "bom", "gst", "vat", "hsn", "ein",
    "sku", "qr", "sms", "otp", "tcs", "tds", "kpi", "crm", "hrms", "saas", "sdk", "cdn",
}


@dataclass(frozen=True)
class Issue:
    """A single validation problem."""

    code: str
    detail: str
    severity: str = "error"  # error | warning

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"{self.severity}:{self.code}({self.detail})"


def extract_placeholders(text: str) -> List[str]:
    """Return every placeholder of a message, sorted."""
    found = _BRACE_PLACEHOLDER_RE.findall(text)
    found += [m.group(0) for m in _PERCENT_PLACEHOLDER_RE.finditer(text)]
    found += _JINJA_RE.findall(text)
    return sorted(found)


def extract_tags(text: str) -> List[str]:
    """Return the lower-cased tag names of a message, sorted."""
    return sorted(match.group(0).lower() for match in _TAG_RE.finditer(text))


def _latin_words(text: str) -> List[str]:
    stripped = _TAG_RE.sub("", _URL_RE.sub("", text))
    return [w for w in _LATIN_WORD_RE.findall(stripped) if w.lower() not in _KEEP_ENGLISH]


def is_sentence(text: str) -> bool:
    """True for real sentences (2+ latin words), False for single labels."""
    return len(_latin_words(text)) >= 2


def looks_like_prose(text: str) -> bool:
    """True when the string is a sentence/label worth translating."""
    words = _latin_words(text)
    if not words:
        return False
    # A single short word can be a technical identifier ("Folio"); a sentence is prose.
    return len(words) >= 2 or len(max(words, key=len)) >= 4


def normalize(text: str) -> str:
    """Normalise whitespace around a translated string."""
    if "\n" in text:
        return "\n".join(line.rstrip() for line in text.split("\n")).strip("\n").strip()
    return text.strip()


def validate(source: str, target: str, *, strict: bool = True) -> List[Issue]:
    """Check a translated string against its source.

    Returns an empty list when the translation is acceptable.
    """
    issues: List[Issue] = []
    if not target or not target.strip():
        issues.append(Issue("empty", "translation is empty"))
        return issues

    if target != target.strip():
        issues.append(
            Issue("whitespace", "leading/trailing whitespace", severity="warning")
        )

    source_placeholders = extract_placeholders(source)
    target_placeholders = extract_placeholders(target)
    if source_placeholders != target_placeholders:
        missing = [p for p in source_placeholders if p not in target_placeholders]
        extra = [p for p in target_placeholders if p not in source_placeholders]
        issues.append(
            Issue(
                "placeholder",
                f"missing={missing} extra={extra}",
            )
        )

    source_tags = extract_tags(source)
    target_tags = extract_tags(target)
    if source_tags != target_tags:
        issues.append(
            Issue("html", f"source={source_tags} target={target_tags}")
        )

    if source.count("\n") != target.count("\n"):
        issues.append(
            Issue("newline", f"source={source.count(chr(10))} target={target.count(chr(10))}")
        )

    if target == source and looks_like_prose(source):
        # An English echo of a whole sentence is an error, of a single label only a warning.
        severity = "error" if is_sentence(source) else "warning"
        issues.append(Issue("untranslated", "target is identical to source", severity=severity))

    if (
        strict
        and looks_like_prose(source)
        and not _CJK_RE.search(target)
        and target != source
    ):
        issues.append(Issue("no_chinese", "no CJK characters in the translation"))

    return issues


def is_acceptable(source: str, target: str) -> bool:
    """True when the translation has no *error* level issue."""
    return not any(issue.severity == "error" for issue in validate(source, target))
