"""
Custom Translations utilities.

Core strategies:
1. translations/zh.csv in this app provides persistent translations that survive
   framework upgrades (Frappe auto-loads CSV from every installed app).
2. `sync_to_po_files()` writes translations back into frappe/erpnext/hrms .po files
   so they get compiled into .mo binaries.
3. `detect_missing_translations_bootinfo()` runs on every desk boot, scans all
   installed apps' .po files for empty msgstr entries, and logs them to the
   `Missing Translation Log` doctype for follow-up.
4. `auto_fill_from_csv()` fills empty msgstr entries in any app's .po file from
   this app's zh.csv (used by the sync command).
5. Optional API translation hook: set `custom_translations_settings.api_endpoint`
   in site_config.json to enable automatic translation of newly detected entries.
"""

import csv
import os
from pathlib import Path

import frappe
from frappe.utils import cstr, now_datetime

APP_NAME = "custom_translations"
SUPPORTED_LANG = "zh"


# ---------- Translation source loading ----------

def get_csv_path() -> Path:
    """Path to this app's translations/zh.csv"""
    return Path(frappe.get_app_path(APP_NAME)) / "translations" / f"{SUPPORTED_LANG}.csv"


def load_app_translations() -> dict:
    """Load translations from this app's zh.csv file."""
    csv_path = get_csv_path()
    translations = {}
    if not csv_path.exists():
        return translations

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2 and row[0]:
                # CSV stores literal "\n" as "\\n"; convert back
                key = row[0].replace("\\n", "\n")
                value = row[1].replace("\\n", "\n")
                translations[key] = value
    return translations


# ---------- Boot hook: detect missing translations ----------

def detect_missing_translations_bootinfo(bootinfo):
    """
    Called on desk boot via extend_bootinfo hook.
    Scans all installed apps for empty msgstr entries in zh.po and logs new ones
    to Missing Translation Log doctype.
    """
    try:
        if frappe.session.user == "Guest":
            return

        lang = frappe.local.lang or frappe.db.get_default("language") or "zh"
        if not lang.startswith("zh"):
            return

        missing = _scan_missing_translations()
        if not missing:
            return

        _log_missing_translations(missing)

        # Optional auto-translate via API
        api_cfg = frappe.conf.get("custom_translations_settings") or {}
        if api_cfg.get("auto_translate"):
            _auto_translate_via_api(missing, api_cfg)
    except Exception:
        frappe.logger(APP_NAME).error("Failed to detect missing translations", exc_info=True)


def _scan_missing_translations():
    """Scan all installed apps' zh.po files for empty msgstr entries."""
    try:
        from babel.messages.pofile import read_po
    except ImportError:
        return []

    missing = []
    apps = frappe.get_installed_apps()
    csv_translations = load_app_translations()

    for app in apps:
        if app == APP_NAME:
            continue
        po_path = _get_app_po_path(app)
        if not po_path or not po_path.exists():
            continue

        try:
            with open(po_path, "rb") as f:
                catalog = read_po(f)
            for msg in catalog:
                if not msg.id:
                    continue
                msgid = msg.id[0] if isinstance(msg.id, tuple) else msg.id
                if not msg.string or not str(msg.string).strip():
                    # Skip if we already have translation in our CSV
                    if msgid in csv_translations:
                        continue
                    missing.append({"app": app, "msgid": msgid})
        except Exception:
            frappe.logger(APP_NAME).error(
                f"Failed to scan {app} po file", exc_info=True
            )

    return missing


def _get_app_po_path(app: str) -> Path:
    """Return path to app's zh.po file."""
    try:
        app_path = frappe.get_app_path(app)
    except Exception:
        return None
    return Path(app_path) / "locale" / "zh.po"


def _log_missing_translations(missing):
    """Log missing translations to Missing Translation Log doctype (deduped)."""
    existing = set(
        frappe.get_all(
            "Missing Translation Log",
            filters={"status": "Open"},
            pluck="source_text",
        )
    )

    for item in missing:
        msgid = item["msgid"]
        if len(msgid) > 2000:
            continue  # skip overly long entries
        if msgid in existing:
            continue
        try:
            doc = frappe.get_doc(
                {
                    "doctype": "Missing Translation Log",
                    "source_text": msgid,
                    "app": item["app"],
                    "language": SUPPORTED_LANG,
                    "status": "Open",
                    "detected_on": now_datetime(),
                }
            )
            doc.insert(ignore_permissions=True)
            existing.add(msgid)
        except Exception as e:
            # Schema not migrated yet - log and skip
            frappe.logger(APP_NAME).error(
                f"Failed to log missing translation '{msgid[:50]}': {e}"
            )


# ---------- Optional API auto-translation ----------

def _auto_translate_via_api(missing, api_cfg=None):
    """
    Auto-translate new entries via configured provider.
    Supported providers: "deepseek", "nvidia", "openai" (all OpenAI-compatible).

    Configuration is loaded automatically from:
    1. Environment variables (CUSTOM_TRANSLATIONS_API_KEY, etc.)
    2. config.json in app directory (user-managed, gitignored)
    3. site_config.json (legacy support)

    See config.example.json for configuration template.
    See README.md for detailed setup instructions.
    """
    from custom_translations.config import load_config, get_setup_instructions

    if api_cfg is None:
        api_cfg = load_config()

    # Validate configuration
    if not api_cfg.get("is_configured"):
        instructions = get_setup_instructions()
        frappe.logger(APP_NAME).warning(
            "Auto-translation skipped: API not configured.\n" + instructions
        )
        return

    provider = (api_cfg.get("provider") or "nvidia").lower()
    max_length = int(api_cfg.get("max_length") or 500)

    # Filter entries by length (skip overly long code/HTML docs)
    # IMPORTANT: Skip entries that already have translations in CSV to avoid overwriting
    existing_translations = load_app_translations()
    new_entries = [
        m["msgid"] for m in missing
        if 0 < len(m["msgid"]) <= max_length
        and m["msgid"] not in existing_translations
    ]
    if not new_entries:
        frappe.logger(APP_NAME).info("No new entries to translate (all already have translations)")
        return

    try:
        if provider in ("deepseek", "nvidia"):
            # Both use OpenAI-compatible chat completions API
            translations = _translate_via_openai_compat(new_entries, api_cfg)
        else:
            frappe.logger(APP_NAME).warning(f"Unknown provider: {provider}")
            return

        if translations and len(translations) == len(new_entries):
            mapping = dict(zip(new_entries, translations))
            # Filter out empty/None results
            mapping = {k: v for k, v in mapping.items() if v and v.strip()}
            if mapping:
                # overwrite=False ensures existing translations are NEVER overwritten
                _append_to_csv(mapping, overwrite=False)
                _mark_logs_translated(mapping)
                frappe.logger(APP_NAME).info(
                    f"Auto-translated {len(mapping)} new entries via {provider} "
                    f"(preserved {len(existing_translations)} existing translations)"
                )
    except Exception:
        frappe.logger(APP_NAME).error(f"API auto-translation via {provider} failed", exc_info=True)


def _translate_via_openai_compat(entries, api_cfg):
    """
    Translate a list of English strings to Simplified Chinese using any
    OpenAI-compatible chat completions API (DeepSeek, NVIDIA NIM, OpenAI, etc.).
    Uses batched requests (batch_size entries per API call) for efficiency.
    Returns list of translated strings in same order as input.

    API key is loaded securely from environment/config - never hardcoded.
    """
    import json
    import re
    import requests

    provider = (api_cfg.get("provider") or "nvidia").lower()
    api_key = api_cfg.get("api_key")
    endpoint = api_cfg.get("api_endpoint")
    model = api_cfg.get("model")
    batch_size = int(api_cfg.get("batch_size") or 10)

    if not api_key:
        frappe.logger(APP_NAME).error(f"{provider} API key missing in config")
        return []

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    import time

    system_prompt = (
        "You are a professional software localization translator specializing in "
        "ERP and enterprise management systems (Frappe/ERPNext framework). "
        "Translate the user-provided English strings into Simplified Chinese (简体中文).\n\n"
        "Domain context - these strings come from an ERP system covering:\n"
        "- Accounting/Finance: 会计科目(Journal Entry=日记账分录, Ledger=分类账, "
        "Reconciliation=对账, Petty Cash=备用金, Provision=计提, Write-off=核销)\n"
        "- Inventory: 库存(Serial No=序列号, Batch=批次, Stock Ledger=库存分类账, "
        "Valuation=估值, Bin=仓位)\n"
        "- Sales/Purchase: 销售/采购(Quotation=报价单, Sales Order=销售订单, "
        "Purchase Receipt=采购收货单, Delivery Note=送货单)\n"
        "- HR: 人资(Payroll=工资单, Leave Application=请假申请, "
        "Attendance=考勤, Appraisal=绩效考核)\n"
        "- Manufacturing: 制造(Work Order=工单, BOM=物料清单, "
        "Job Card=作业卡, Operation=工序)\n"
        "- CRM: 客户关系管理(Lead=线索, Opportunity=商机, Prospect=潜在客户)\n"
        "\n"
        "Translation rules:\n"
        "1. Keep placeholders like {0}, {1}, {{name}}, %s, %(name)s unchanged.\n"
        "2. Keep HTML tags like <b>, <br>, <code>, <a href='...'> unchanged - only translate text content.\n"
        "3. Keep technical terms unchanged: DocType, Frappe, ERPNext, OAuth, LDAP, IMAP, SMTP, "
        "API, JSON, CSV, URL, PDF, HTML, CSS, SSH, SQL, WSDL, REST.\n"
        "4. Return ONLY a JSON object with key \"translations\" containing an array of "
        "translated strings, in the SAME ORDER as input. No explanation.\n"
        "5. Preserve newlines (\\n) and special characters.\n"
        "6. If a string is pure code/URL/email/identifier, return it unchanged.\n"
        "7. Use formal business Chinese (e.g., 您 instead of 你, 请 instead of 帮我).\n"
        "8. Be concise - UI labels should be short and clear."
    )

    results = []
    for i in range(0, len(entries), batch_size):
        batch = entries[i:i + batch_size]
        # Build numbered prompt for reliable ordering
        numbered = "\n".join(f"{idx+1}. {s}" for idx, s in enumerate(batch))
        user_msg = (
            f"Translate these {len(batch)} strings to Simplified Chinese. "
            f'Return JSON {{"translations": ["...", "..."]}}:\n\n{numbered}'
        )

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.1,
            "max_tokens": 4096,
        }
        # Only DeepSeek supports response_format; NVIDIA NIM ignores it safely
        if provider == "deepseek":
            payload["response_format"] = {"type": "json_object"}

        try:
            # Retry logic for transient errors (503, timeout)
            max_retries = 3
            last_error = None
            data = None
            for attempt in range(max_retries):
                try:
                    resp = requests.post(endpoint, headers=headers, json=payload, timeout=120)
                    resp.raise_for_status()
                    data = resp.json()
                    break
                except Exception as retry_err:
                    last_error = retry_err
                    if attempt < max_retries - 1:
                        wait = (attempt + 1) * 5  # 5s, 10s backoff
                        frappe.logger(APP_NAME).warning(
                            f"{provider} batch {i//batch_size+1} attempt {attempt+1} failed: {retry_err}, retrying in {wait}s"
                        )
                        time.sleep(wait)
                    else:
                        raise

            content = data["choices"][0]["message"]["content"].strip()

            # Parse response - may return {"translations": [...]} or [...]
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    translated = (
                        parsed.get("translations")
                        or parsed.get("data")
                        or parsed.get("result")
                        or list(parsed.values())[0]
                    )
                else:
                    translated = parsed
            except json.JSONDecodeError:
                # Fallback: extract JSON array from text
                match = re.search(r'\[.*\]', content, re.DOTALL)
                if match:
                    translated = json.loads(match.group(0))
                else:
                    frappe.logger(APP_NAME).error(
                        f"Failed to parse {provider} response: {content[:200]}"
                    )
                    translated = [""] * len(batch)

            # Validate length matches
            if isinstance(translated, list) and len(translated) == len(batch):
                results.extend(translated)
            else:
                frappe.logger(APP_NAME).warning(
                    f"{provider} batch {i//batch_size+1} returned "
                    f"{len(translated) if isinstance(translated, list) else 'non-list'} results, "
                    f"expected {len(batch)}"
                )
                results.extend([""] * len(batch))
        except Exception as e:
            frappe.logger(APP_NAME).error(
                f"{provider} batch {i//batch_size+1} failed after {max_retries} retries: {e}"
            )
            results.extend([""] * len(batch))

    return results


# Backward-compatible alias
_translate_via_deepseek = _translate_via_openai_compat


def _mark_logs_translated(translations: dict):
    """Mark corresponding Missing Translation Log records as Translated (Auto)."""
    try:
        for source_text, translated_text in translations.items():
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
    except Exception:
        pass


# ---------- CSV management ----------

def _append_to_csv(new_translations: dict, overwrite: bool = False):
    """Append new translations to this app's zh.csv (deduped by key).

    Args:
        new_translations: dict of {source_text: translated_text}
        overwrite: If False (default), existing translations are NOT overwritten,
                   so manual corrections and prior translations are preserved.
                   If True, new values override existing ones (used by manual
                   Translation doctype edits).
    """
    csv_path = get_csv_path()
    existing = load_app_translations()

    if overwrite:
        existing.update(new_translations)
    else:
        # Only add entries that don't already exist - preserve existing translations
        for k, v in new_translations.items():
            if k not in existing or not existing[k]:
                existing[k] = v

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        for key, value in sorted(existing.items()):
            # Store newlines as literal \n for CSV compatibility
            k = key.replace("\n", "\\n")
            v = value.replace("\n", "\\n")
            writer.writerow([k, v])


# ---------- Translation doctype change hook ----------

def on_translation_update(doc, method):
    """When a Translation record is updated in DB, also persist to this app's CSV
    so it survives cache clears and migrations. Manual edits always overwrite."""
    if doc.language != SUPPORTED_LANG:
        return
    if not doc.source_text or not doc.translated_text:
        return
    _append_to_csv({doc.source_text: doc.translated_text}, overwrite=True)


def apply_manual_corrections():
    """Apply manual corrections from Missing Translation Log to CSV.

    Extracts translations from records marked as 'Reviewed' (manually verified)
    or 'Translated' with translation_source='Manual', and writes them to CSV
    with overwrite=True so they override auto-translations.

    Called by bench command: custom-translations-apply-corrections
    """
    # Get all records with manual translations (Reviewed status or Manual source)
    manual_records = frappe.get_all(
        "Missing Translation Log",
        filters=[
            {"status": "Reviewed"},
        ],
        or_filters=[
            {"status": "Reviewed"},
            {"translation_source": "Manual"},
        ],
        fields=["source_text", "translated_text"],
    )

    if not manual_records:
        return 0

    corrections = {}
    for r in manual_records:
        if r.translated_text and r.source_text:
            corrections[r.source_text] = r.translated_text

    if corrections:
        _append_to_csv(corrections, overwrite=True)
        frappe.logger(APP_NAME).info(
            f"Applied {len(corrections)} manual corrections to CSV"
        )

    return len(corrections)


# ---------- Sync command: write translations back to .po files ----------

def sync_to_po_files():
    """
    Bench command: `bench --site {site} custom-translations-sync`

    OPTIONAL: Writes this app's CSV translations into frappe/erpnext/hrms
    zh.po files (filling empty msgstr entries only), then recompiles .mo
    and clears cache.

    NOTE: This modifies official framework .po files. It is OPTIONAL -
    translations work out-of-the-box via this app's zh.csv (Frappe auto-loads
    CSV from every installed app). Use this only if you want translations
    compiled into .mo binaries for slight performance improvement.

    After running this, official updates may show merge conflicts in .po files.
    To avoid this, skip this command and rely on the app's CSV instead.
    """
    from babel.messages.pofile import read_po, write_po

    print("WARNING: This will modify official frappe/erpnext/hrms .po files.")
    print("This is OPTIONAL - translations already work via this app's zh.csv.")
    print("Proceeding in 3 seconds... (Ctrl+C to cancel)\n")
    import time
    time.sleep(3)

    csv_translations = load_app_translations()
    if not csv_translations:
        print("No translations found in custom_translations/translations/zh.csv")
        return

    print(f"Loaded {len(csv_translations)} translations from CSV")

    apps = ["frappe", "erpnext", "hrms", "payments", "webshop"]
    total_filled = 0

    for app in apps:
        po_path = _get_app_po_path(app)
        if not po_path or not po_path.exists():
            print(f"  [{app}] no zh.po found, skipping")
            continue

        try:
            with open(po_path, "rb") as f:
                catalog = read_po(f)

            filled = 0
            for msg in catalog:
                if not msg.id:
                    continue
                msgid = msg.id[0] if isinstance(msg.id, tuple) else msg.id
                if (not msg.string or not str(msg.string).strip()) and msgid in csv_translations:
                    msg.string = csv_translations[msgid]
                    filled += 1

            if filled > 0:
                with open(po_path, "wb") as f:
                    write_po(f, catalog)
                print(f"  [{app}] filled {filled} entries")
                total_filled += filled
            else:
                print(f"  [{app}] nothing to fill")
        except Exception as e:
            print(f"  [{app}] error: {e}")

    if total_filled > 0:
        print(f"\nTotal filled: {total_filled}")
        print("Recompiling .mo files...")
        os.system("bench compile-po-to-mo --app frappe")
        os.system("bench compile-po-to-mo --app erpnext")
        os.system("bench compile-po-to-mo --app hrms")
        print("Clearing cache...")
        os.system("bench --site all clear-cache")
        print("Done.")
    else:
        print("\nNothing to sync - all translations already in place.")


# ---------- Batch terminology fix ----------
# Word-level replacements to fix systematic translation errors across the
# entire CSV. These correct widespread mistranslations that affect many
# sentence-level entries (e.g. "储存" should be "保存", "报告" should be "报表").
#
# Format: (wrong_substring, correct_substring, description)
# Order matters: longer/more-specific replacements run first.
BATCH_TERM_REPLACEMENTS = [
    # Save - 储存 → 保存 (台湾用语 → 大陆规范)
    ("储存", "保存", "Save: 储存→保存"),
    # Report - 报告 → 报表 (in ERP context, Report = 报表 not 报告)
    ("报告", "报表", "Report: 报告→报表"),
    # Masters - 大师 → 主数据 (Master Data, not "大师")
    ("大师", "主数据", "Masters: 大师→主数据"),
    # Settings - 设定 → 设置 (台湾用语 → 大陆规范)
    ("设定", "设置", "Settings: 设定→设置"),
    # Note: "家" 单字替换太危险（影响"家庭"、"家具"等正确翻译），
    # 所以 "Home → 家" 的修正通过 professional_glossary 覆盖处理。
]


def fix_batch_terminology():
    """
    Fix systematic translation errors across the entire zh.csv.

    Scans all translations and applies word-level replacements to correct
    widespread mistranslations:
    - 储存 → 保存 (Save)
    - 报告 → 报表 (Report)
    - 大师 → 主数据 (Masters)
    - 设定 → 设置 (Settings)

    Returns: number of entries modified
    """
    csv_path = get_csv_path()
    existing = load_app_translations()

    modified = {}
    count = 0
    for key, value in existing.items():
        new_value = value
        for wrong, correct, _desc in BATCH_TERM_REPLACEMENTS:
            new_value = new_value.replace(wrong, correct)
        if new_value != value:
            modified[key] = new_value
            count += 1

    if count > 0:
        # Merge modified entries back (overwrite=True to replace wrong values)
        _append_to_csv(modified, overwrite=True)
        frappe.logger(APP_NAME).info(
            f"Fixed {count} entries with batch terminology replacements"
        )

    return count

