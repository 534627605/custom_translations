"""
AI translation engine (v2).

Compared to the original implementation this engine:

1. **Enforces the curated glossary.** Only the terms that actually occur in the
   current batch are injected, and they are injected as *mandatory* mappings
   rather than as a wall of domain prose.
2. **Uses the target app's own newest translations as a translation memory.**
   The few examples with the highest token overlap with the batch are injected
   as reference translations, so the model follows the style already used by
   ERPNext/HRMS/Helpdesk instead of inventing its own wording.
3. **Validates every string** with :mod:`custom_translations.validate` and runs
   a targeted repair pass for the entries that fail (placeholders/HTML dropped,
   English echoed back, ...). Only strings that pass are returned.
4. **Applies the terminology rules** (:mod:`custom_translations.terminology`)
   after the model, so mainland-China wording wins over model drift.

The transport layer stays provider agnostic: any OpenAI-compatible
``/chat/completions`` endpoint works (NVIDIA NIM, DeepSeek, OpenAI, ...).
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from custom_translations.terminology import fix_translation
from custom_translations.validate import is_acceptable, normalize, validate

__all__ = [
    "TranslationResult",
    "translate_entries",
    "build_glossary_block",
    "select_reference_translations",
    "SYSTEM_PROMPT",
]

SYSTEM_PROMPT = (
    "You are a professional software localisation translator specialising in "
    "ERP and enterprise management systems (Frappe / ERPNext). "
    "Translate the user-provided English strings into Simplified Chinese (简体中文).\n"
    "\n"
    "Domain vocabulary you must respect:\n"
    "- Accounting: Journal Entry=日记账分录, Ledger=分类账, Reconciliation=对账, "
    "Write-off=核销, Provision=计提, Petty Cash=备用金\n"
    "- Inventory: Stock Entry=库存移动单, Serial No=序列号, Batch=批次, "
    "Valuation Rate=计价成本, Bin=库位\n"
    "- Sales/Purchase: Quotation=报价单, Delivery Note=送货单, "
    "Purchase Receipt=采购收货单, Material Request=物料申请单\n"
    "- HR: Payroll Entry=工资单分录, Salary Slip=工资条, Leave Application=请假申请, "
    "Attendance=考勤, Appraisal=绩效考核\n"
    "- Manufacturing: Work Order=工单, BOM=物料清单, Operation=工序, Job Card=作业卡\n"
    "- CRM: Lead=线索, Opportunity=商机, Campaign=营销活动\n"
    "\n"
    "Translation rules:\n"
    "1. Keep placeholders byte-identical: {0}, {1}, {}, {name}, %s, %(name)s, {{ x }}.\n"
    "2. Keep HTML tags byte-identical and in the same order: <b>, <br>, <a href='...'>.\n"
    "3. Keep technical identifiers untranslated: DocType, Frappe, ERPNext, OAuth, LDAP, "
    "IMAP, SMTP, API, JSON, CSV, URL, PDF, HTML, CSS, SQL, REST, UUID.\n"
    "4. Use mainland-China ERP wording. Never use Taiwan wording: use 保存 not 储存, "
    "报表 not 报告 for the noun, 设置 not 设定, 用户 not 使用者, 默认 not 预设, "
    "数据 not 资料, 文件 not 档案, 登录 not 登入, 导入/导出 not 汇入/汇出.\n"
    "5. Keep the translation as short as the original - these are UI labels.\n"
    "6. If a string is pure code, a URL, an email or an identifier, return it unchanged.\n"
    "7. Preserve leading/trailing newlines and tabs exactly.\n"
    '8. Reply with JSON only: {"translations": ["...", "..."]} in the same order.'
)

_USER_TEMPLATE = (
    "Translate these {count} strings to Simplified Chinese.\n"
    "{glossary}{reference}"
    'Return JSON {{"translations": ["...", ...]}} with exactly {count} items:\n\n{items}'
)

_REPAIR_TEMPLATE = (
    "Your previous translation was rejected by an automated checker.\n"
    "Source: {source}\n"
    "Rejected translation: {previous}\n"
    "Problems: {problems}\n"
    "Translate the source again, fixing every problem. "
    'Reply with JSON only: {{"translations": ["..."]}}'
)


@dataclass
class TranslationResult:
    """Outcome of one translation run."""

    translations: Dict[str, str] = field(default_factory=dict)
    rejected: Dict[str, List[str]] = field(default_factory=dict)
    api_calls: int = 0
    repaired: int = 0

    @property
    def accepted(self) -> int:
        return len(self.translations)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)


def _tokens(text: str) -> set:
    return {token.lower() for token in re.findall(r"[A-Za-z_]{3,}", text)}


def build_glossary_block(
    entries: Sequence[str],
    glossary: Dict[str, str],
    limit: int = 40,
) -> str:
    """Return the glossary subset relevant to ``entries`` as prompt text."""
    haystack = " \n ".join(entries).lower()
    hits: List[Tuple[str, str]] = []
    for source, target in glossary.items():
        if source.lower() in haystack:
            hits.append((source, target))
        if len(hits) >= limit:
            break
    if not hits:
        return ""
    lines = "\n".join(f"- {source} => {target}" for source, target in hits)
    return (
        "\nMandatory terminology for terms occurring in this batch "
        "(use these translations exactly):\n" + lines + "\n"
    )


def select_reference_translations(
    entries: Sequence[str],
    memory: Dict[str, str],
    limit: int = 8,
) -> List[Tuple[str, str]]:
    """Pick the most relevant existing translations as few-shot examples.

    Relevance is token overlap between the batch and the candidate source
    string; ties are broken by the candidate's length (shorter = more generic).
    """
    if not memory:
        return []
    batch_tokens: set = set()
    for entry in entries:
        batch_tokens |= _tokens(entry)
    if not batch_tokens:
        return []

    scored: List[Tuple[int, int, str, str]] = []
    for source, target in memory.items():
        if not source or not target or source in entries:
            continue
        overlap = len(_tokens(source) & batch_tokens)
        if overlap:
            scored.append((overlap, -len(source), source, target))
    scored.sort(reverse=True)
    return [(source, target) for _overlap, _len, source, target in scored[:limit]]


def _reference_block(examples: Sequence[Tuple[str, str]]) -> str:
    if not examples:
        return ""
    lines = "\n".join(f"- {source} => {target}" for source, target in examples)
    return (
        "\nReference translations already used by this application "
        "(match their style and vocabulary):\n" + lines + "\n"
    )


# --------------------------------------------------------------------------- #
# Transport
# --------------------------------------------------------------------------- #

class ApiError(RuntimeError):
    """Raised when the provider cannot be reached or returns junk."""


class OpenAiCompatClient:
    """Minimal OpenAI-compatible chat-completions client."""

    def __init__(self, config: Dict, timeout: int = 120):
        self.api_key = config.get("api_key")
        self.endpoint = config.get("api_endpoint")
        self.model = config.get("model")
        self.provider = (config.get("provider") or "").lower()
        self.timeout = timeout

    def complete(self, system_prompt: str, user_prompt: str, *, json_mode: bool = True) -> str:
        import requests

        if not self.api_key:
            raise ApiError("API key missing in configuration")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 4096,
        }
        # Only some providers accept response_format; it is optional anyway.
        if json_mode and self.provider == "deepseek":
            payload["response_format"] = {"type": "json_object"}

        response = requests.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ApiError(f"unexpected response shape: {str(data)[:200]}") from exc


def _parse_translations(content: str, expected: int) -> List[str]:
    """Extract the translated list from a model reply."""
    parsed = None
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError:
                parsed = None

    if isinstance(parsed, dict):
        for key in ("translations", "data", "result", "items"):
            if isinstance(parsed.get(key), list):
                parsed = parsed[key]
                break
        else:
            values = list(parsed.values())
            parsed = values[0] if values and isinstance(values[0], list) else None

    if not isinstance(parsed, list) or len(parsed) != expected:
        raise ApiError(
            f"expected {expected} items, got "
            f"{len(parsed) if isinstance(parsed, list) else type(parsed).__name__}"
        )
    return ["" if item is None else str(item) for item in parsed]


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def _postprocess(source: str, target: str) -> str:
    """Deterministic clean-up applied to every model output."""
    fixed, _notes = fix_translation(source, target)
    return normalize(fixed)


def _call_with_retries(
    client: OpenAiCompatClient,
    system_prompt: str,
    user_prompt: str,
    *,
    attempts: int = 3,
    sleeper=time.sleep,
    on_retry=None,
) -> str:
    last_error: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            return client.complete(system_prompt, user_prompt)
        except Exception as exc:  # noqa: BLE001 - provider errors are opaque
            last_error = exc
            if attempt < attempts - 1:
                wait = (attempt + 1) * 5
                if on_retry:
                    on_retry(attempt + 1, exc, wait)
                sleeper(wait)
    raise ApiError(str(last_error))


def translate_entries(
    entries: Sequence[str],
    config: Dict,
    *,
    glossary: Optional[Dict[str, str]] = None,
    memory: Optional[Dict[str, str]] = None,
    client: Optional[OpenAiCompatClient] = None,
    logger=None,
    sleeper=time.sleep,
) -> TranslationResult:
    """Translate ``entries`` into Simplified Chinese.

    Returns a :class:`TranslationResult`; only validated strings are included in
    ``translations``, everything else is reported in ``rejected`` with reasons.
    """
    result = TranslationResult()
    unique: List[str] = []
    seen: set = set()
    for entry in entries:
        if entry and entry not in seen:
            seen.add(entry)
            unique.append(entry)
    if not unique:
        return result

    client = client or OpenAiCompatClient(config)
    glossary = glossary or {}
    memory = memory or {}
    batch_size = max(1, int(config.get("batch_size") or 10))

    pending: Dict[str, str] = {}

    for start in range(0, len(unique), batch_size):
        batch = unique[start : start + batch_size]
        items = "\n".join(f"{index + 1}. {text}" for index, text in enumerate(batch))
        user_prompt = _USER_TEMPLATE.format(
            count=len(batch),
            glossary=build_glossary_block(batch, glossary),
            reference=_reference_block(select_reference_translations(batch, memory)),
            items=items,
        )
        try:
            content = _call_with_retries(
                client,
                SYSTEM_PROMPT,
                user_prompt,
                sleeper=sleeper,
                on_retry=(
                    lambda attempt, exc, wait: logger.warning(
                        f"batch {start // batch_size + 1} attempt {attempt} failed: {exc}; "
                        f"retrying in {wait}s"
                    )
                    if logger
                    else None
                ),
            )
            result.api_calls += 1
            candidates = _parse_translations(content, len(batch))
        except Exception as exc:  # noqa: BLE001
            if logger:
                logger.error(f"batch {start // batch_size + 1} failed: {exc}")
            for source in batch:
                result.rejected.setdefault(source, []).append(f"api: {exc}")
            continue

        for source, candidate in zip(batch, candidates):
            processed = _postprocess(source, candidate)
            if not processed:
                result.rejected.setdefault(source, []).append("empty response")
                continue
            issues = validate(source, processed)
            errors = [issue for issue in issues if issue.severity == "error"]
            if errors:
                pending[source] = processed
                result.rejected.setdefault(source, []).extend(str(issue) for issue in errors)
            else:
                result.translations[source] = processed

    # ---- repair pass: one request per rejected entry, with feedback ----
    for source, previous in list(pending.items()):
        problems = ", ".join(result.rejected.get(source, []))
        prompt = _REPAIR_TEMPLATE.format(
            source=source, previous=previous, problems=problems
        )
        try:
            content = _call_with_retries(
                client, SYSTEM_PROMPT, prompt, attempts=2, sleeper=sleeper
            )
            result.api_calls += 1
            repaired = _postprocess(source, _parse_translations(content, 1)[0])
        except Exception as exc:  # noqa: BLE001
            result.rejected.setdefault(source, []).append(f"repair api: {exc}")
            continue
        issues = [issue for issue in validate(source, repaired) if issue.severity == "error"]
        if repaired and not issues:
            result.translations[source] = repaired
            result.rejected.pop(source, None)
            result.repaired += 1
        else:
            result.rejected.setdefault(source, []).extend(str(issue) for issue in issues)

    return result
