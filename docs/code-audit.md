# Independent Defect Audit — `custom_translations`

Auditor: independent senior Python/Frappe reviewer (task `task_0002`).
Scope: `custom_translations/utils.py`, `commands.py`, `config.py`, `hooks.py`, `setup.py`,
`professional_glossary.py`, `custom_translations/doctype/missing_translation_log/missing_translation_log.json`.
Frappe semantics were verified against `frappe/frappe@version-15` source (fetched from
`raw.githubusercontent.com`) and GitHub code search; ERPNext/HRMS shipped-file layout was verified
against the `frappe/erpnext@version-15` and `frappe/hrms@version-15` git trees.

No source files were modified. Only this document was written.

## Ranked summary (worst first)

| id | file:line | severity | finding | concrete failure scenario | evidence / confidence |
|----|-----------|----------|---------|---------------------------|-----------------------|
| A1 | utils.py:122-128 (also commands.py:94-104) | **HIGH** | `_get_app_po_path()` hard-codes `<app>/locale/zh.po`; ERPNext v15 and HRMS v15 ship `translations/zh.csv` and have **no** `locale/` dir | `custom-translations-scan` and the boot detector silently skip ERPNext and HRMS — the apps that actually contain the untranslated ERP strings — so the whole "detect missing translations" feature is a near-no-op | ERPNext tree: `erpnext/translations/zh.csv`, `zh-TW.csv`, `zh_tw.csv`, no `locale/`; HRMS tree: `hrms/translations/zh.csv`; frappe has `frappe/locale/zh.po` (PO_DIR="locale" in `frappe/gettext/translate.py`). **CONFIRMED, high confidence** |
| A2 | commands.py:80-128 | **HIGH** | `export_from_frappe` opens the app's curated `translations/zh.csv` with mode `"w"` and writes only what it extracted from `<app>/locale/zh.po` | Running `bench --site X custom-translations-export` replaces the 16,886-entry curated CSV with frappe's ~6,112 entries, **silently destroying** all ERPNext/HRMS strings, the 416-entry glossary and any manual corrections. Command is not documented in README | commands.py:119-128 (`open(csv_path,"w")`, no merge); `frappe/locale/zh.po` = 6,293 msgid / 6,112 non-empty msgstr; erpnext/hrms contribute 0 because they have no `.po`. **CONFIRMED, high confidence** |
| A3 | utils.py:169-193 + 76-79 | **HIGH** | `_auto_translate_via_api()` is called from the boot hook with the raw `site_config` dict, so `api_cfg.get("is_configured")` is always falsy → early return; it also bypasses `load_config()` (env vars / `config.json` ignored) | Setting `custom_translations_settings.auto_translate=true` in `site_config.json` never translates anything; `auto_translate` in `config.json`/env is not even read on the boot path | utils.py:77-79 passes `frappe.conf.get(...)`; utils.py:184-188 `if api_cfg is None: load_config()` then `if not api_cfg.get("is_configured"): return`. **CONFIRMED (known #2), high confidence** |
| A4 | utils.py:457-477 | **HIGH** | `apply_manual_corrections()` passes both `filters=[{status:Reviewed}]` and `or_filters=[{status:Reviewed},{translation_source:Manual}]`; Frappe ANDs `filters` with the grouped `or_filters` | Only records with `status="Reviewed"` are exported. A record with `translation_source="Manual"` but `status="Translated"` is ignored, contradicting the docstring/README ("Reviewed status or Manual source") | `frappe/model/db_query.py:553` `args.conditions = " and ".join(self.conditions + self.permission_conditions + grouped_or_clause)`; `build_conditions` (957-965). **CONFIRMED (known #3), high confidence** |
| A5 | utils.py:581-628 | **HIGH** | `fix_batch_terminology()` blind substring `str.replace` over every value; the shipped CSV shows corrupted verb senses from `报告→报表` | e.g. `"…vulnerability reporting…" → "关于漏洞报表的指南…"`, `"Allow Reporting of Issues…" → "…允许向开发人员报表问题"`, `"…vulnerabilities can be reported…" → "可以报表漏洞的网站…"`, `"Ignore Is Opening check for reporting" → "报表中忽略是开账凭证"` (all should be 报告) | CSV has **0** `报告` and **235** `报表`; utils.py:615-616 `new_value.replace(wrong,correct)`. **CONFIRMED (known #7), high confidence** |
| A6 | missing_translation_log.json:15 | **HIGH** | `source_text` is `fieldtype:"Text"` with `unique:1`; Frappe silently **skips** `unique` for text/longtext columns, so uniqueness is not enforced | Duplicate `Missing Translation Log` rows accumulate: `_log_missing_translations` de-dupes only against `status="Open"`, so once a row is set to `Ignored`/`Translated`/`Reviewed` a later scan re-inserts it (and concurrent boots race) | `frappe/database/schema.py:212` and `:241-244` (`... column_type not in ("text","longtext")`); `frappe/database/mariadb/database.py:189` `"Text": ("text","")`. **CONFIRMED, high confidence** |
| A7 | commands.py:144 | **MEDIUM** | `frappe.model.sync_file_to_doc("Missing Translation Log", ...)` does not exist; `AttributeError` swallowed by `except Exception: pass` | The "ensure doctype schema is migrated" step never runs, so on a fresh site `custom-translations-scan` can fail to log anything (inserts fail on the missing table and are only written to the error log) | `frappe/model/__init__.py` defines only `delete_fields`, `get_permitted_fields`, `is_default_field`; sync lives in `frappe/model/sync.py` (`sync_for`/`sync_all`). **CONFIRMED (known #4), high confidence** |
| A8 | utils.py:56-81 | **MEDIUM** | `detect_missing_translations_bootinfo` runs on **every** desk boot and does heavy synchronous work (parse every app's `.po`, load the 16,886-entry CSV) plus DB writes | Each desk page load pays the full scan; `_log_missing_translations` also performs inserts during a read/boot request. (The "HTTP during boot" sub-claim is currently unreachable — see A3) | `frappe/sessions.py:170-171` runs `extend_bootinfo` hooks on every `get_bootinfo()` even when `bootinfo` was served from cache. **CONFIRMED (known #5, scan part); HTTP part REFUTED** |
| A9 | hooks.py:30-32 | **MEDIUM** | `bench_commands = ["custom_translations.commands"]` is not a Frappe/bench hook; commands are discovered by importing `<app>.commands` and reading its `commands` list | The line is a silent no-op (harmless here because commands.py:319-329 defines `commands`, so the CLI still works). Misleads maintainers into thinking it registers anything | `frappe/utils/bench_helper.py::get_app_commands` → `importlib.import_module(f"{app}.commands")`; code search `bench_commands repo:frappe/frappe` returns nothing. **CONFIRMED no-op (known #1), high confidence** |
| A10 | utils.py:414-442 + 447-454 | **MEDIUM** | `_append_to_csv` writes only 2 columns, dropping Frappe's 3rd "context" column, and rewrites the entire file on every `Translation` save with no lock | Any context-bearing row is silently lost/misread (Frappe keys context translations as `msgid:context`). `on_translation_update` re-writes all 16,886 rows per save → O(n) write amplification and lost updates under concurrent edits | `frappe/translate.py:680-707` `write_csv_file` writes `[message, translated_string, context]`; `:198-213` keys `item[0]+":"+item[2]`. Current CSV has 0 three-col rows → latent. **CONFIRMED (3rd-column part, known #8); CRLF part REFUTED** |
| A11 | translations/zh.csv (via utils.py:43-51) | **MEDIUM** | 76 CSV keys have leading/trailing spaces (e.g. `' Rate'→'费率'`, `' Item'→'物料'`); Frappe strips the lookup key but does not strip CSV keys | Those 76 curated translations are **dead** and are shadowed by differently-worded un-spaced duplicates (`'Rate'→'单价'`, `'Phantom Item'→'虚拟项目'` …) | `frappe/__init__.py:119-120` `msg = as_unicode(msg).strip()`; `frappe/translate.py:198-213` uses `item[0]` unstripped; utils.py:46-50 no strip. **CONFIRMED, high confidence** |
| A12 | hooks.py:8-12 + README | **LOW** | The claim "this app loads AFTER frappe/erpnext so our translations take priority" is not guaranteed | If any app is installed *after* `custom_translations`, that app's `.mo`/`.csv` overrides this app's `zh.csv`, silently reverting curated translations | `frappe/translate.py:174-189` iterates `frappe.get_installed_apps()` and `update()`s per app (later wins); `frappe/__init__.py:1559-1577` returns install order. **CONFIRMED as a fragile assumption (medium confidence)** |
| A13 | setup.py:34-39 | **LOW** | `after_install` prints literal `{site}` because the strings are not f-strings | Users see `bench --site {site} custom-translations-stats` after install | setup.py:34-39 (no `f` prefix). **CONFIRMED, high confidence** |
| A14 | utils.py:66 | **LOW** | `frappe.local.lang or frappe.db.get_default("language")` fallback is dead; `frappe.local.lang` is always set (≥ "en") after `connect()` | The intended "use site default language if unset" path never triggers | `frappe/__init__.py:240` `local.lang = local.conf.lang or "en"`. **CONFIRMED, medium confidence** |

## Verification method per finding

### A1 — ERPNext/HRMS `.po` path does not exist (CONFIRMED)
Method: listed the shipped file trees.
- `gh api repos/frappe/erpnext/git/trees/version-15?recursive=1 | grep -iE 'locale|\.po$|zh'` → only `erpnext/translations/zh.csv`, `zh-TW.csv`, `zh_tw.csv`; `repos/frappe/erpnext/contents/erpnext/locale` → HTTP 404.
- HRMS tree → only `hrms/translations/zh.csv`; `hrms/locale` → HTTP 404.
- `frappe/locale/zh.po` exists and `frappe/gettext/translate.py` defines `PO_DIR = "locale"`, `get_po_dir(app) = get_app_path(app)/locale`.
- `utils.py:128` `return Path(app_path) / "locale" / "zh.po"`; `_scan_missing_translations` (utils.py:98-100) and `export_from_frappe` (commands.py:102-104) both `continue`/`skip` when the file is absent.
Conclusion: the detector only ever scans `frappe` (plus any app that happens to ship `.po`); ERPNext/HRMS are always skipped. This CONFIRMS known finding #6, but the correct framing is that the path is right for `.po`-shipping apps and simply does not exist for ERPNext/HRMS (which use `translations/*.csv`).

### A2 — `export_from_frappe` destructively overwrites the curated CSV (CONFIRMED)
Method: read commands.py:80-128. `csv_path` points at this app's `translations/zh.csv`, opened with mode `"w"` (line 121) and written with only `all_translations` (lines 122-126); there is no read/merge of the existing file. The extraction loop only reads `<app>/locale/zh.po` (line 102). Because ERPNext/HRMS have no `.po`, the result is a frappe-only file (`frappe/locale/zh.po` = 6,293 msgid / 6,112 non-empty msgstr) replacing 16,886 curated rows. The command is absent from the README command table. Severity HIGH because it is silent, irreversible data loss of the app's primary asset.

### A3 — boot auto-translate always early-returns (CONFIRMED, known #2)
Method: trace the argument. `detect_missing_translations_bootinfo` (utils.py:56-81) builds `api_cfg = frappe.conf.get("custom_translations_settings") or {}` (line 77) and, only if `api_cfg.get("auto_translate")`, calls `_auto_translate_via_api(missing, api_cfg)` (line 79). In `_auto_translate_via_api` (utils.py:169-193), `load_config()` is only called when `api_cfg is None` (line 184-185); the raw site_config dict is not None, and it never contains the computed `is_configured` key, so line 188 always returns. Net effect: the boot path ignores env vars and `config.json` entirely and never translates.

### A4 — `filters` AND `or_filters` (CONFIRMED, known #3)
Method: read frappe query builder. `frappe.get_all` → `get_list` → `frappe/model/db_query.py`. `build_conditions` (lines 957-965) puts `filters` in `self.conditions` and `or_filters` in `self.grouped_or_conditions`; line 541-553 assembles `args.conditions = " and ".join(self.conditions + self.permission_conditions + grouped_or_clause)`. So `status=Reviewed AND (status=Reviewed OR translation_source=Manual)` collapses to `status=Reviewed`. The `translation_source=Manual` branch of `or_filters` can never broaden the result, contradicting utils.py:460-462 and the README "Reviewed status or Manual source".

### A5 — blind substring batch replacement corrupted verb senses (CONFIRMED, known #7)
Method: reproduced the transform and inspected the shipped CSV.
- `BATCH_TERM_REPLACEMENTS` (utils.py:581-592) contains `("报告","报表", ...)`; `fix_batch_terminology` (utils.py:613-619) does `new_value.replace(wrong, correct)` for every value.
- The shipped `translations/zh.csv` contains **0** occurrences of `报告` and **235** of `报表`, i.e. the replacement has already been applied. Concrete wrong rows found by filtering keys containing `report(ing|ed)`:
  - `Guidelines and policies on vulnerability reporting. Defaults to https://frappe.io/security` → `关于漏洞报表的指南和政策…` (should be 报告)
  - `Show Full Error and Allow Reporting of Issues to the Developer` → `显示完整错误并允许向开发人员报表问题`
  - `Website, email or phone where vulnerabilities can be reported…` → `可以报表漏洞的网站…`
  - `Ignore Is Opening check for reporting` → `报表中忽略是开账凭证`
- The same class of bug applies to `储存→保存` (verb/noun "stores/storage") and `大师→主数据`; no live counter-example remains for those in the current file, so their status is a latent risk rather than a reproduced corruption.

### A6 — `unique` on a `Text` field is silently ignored (CONFIRMED)
Method: verified Frappe schema generation for `unique` on text columns.
- `frappe/database/mariadb/database.py:189` `"Text": ("text", "")`, so `get_definition("Text")` returns `"text"`.
- `frappe/database/schema.py:212` appends ` unique` only when `column_def not in ("text", "longtext")`; `:241-244` likewise only adds a unique index when `column_type not in ("text", "longtext")`.
- `frappe/model/base_document.py:609-673` only reacts to a *database* unique violation (there is no application-level pre-check), so with no index no error is ever raised.
Combined with `_log_missing_translations` (utils.py:133-139) de-duping only `status="Open"`, a row re-detected after being set to `Ignored`/`Translated`/`Reviewed` is inserted again, and concurrent boots can insert duplicates for the same `source_text`.

### A7 — `frappe.model.sync_file_to_doc` does not exist (CONFIRMED, known #4)
Method: fetched `frappe/model/__init__.py`; its only functions are `delete_fields`, `get_permitted_fields`, `is_default_field`. The sync helpers are `frappe.model.sync.sync_for` / `sync_all` (frappe/model/sync.py). Code search `sync_file_to_doc repo:frappe/frappe` returns nothing. commands.py:143-146 wraps the call in `try/except Exception: pass`, so the AttributeError is swallowed and the intended schema-ensure is a no-op.

### A8 — boot hook heavy work on every desk boot (CONFIRMED for scan; HTTP sub-claim REFUTED)
Method: `frappe/sessions.py:129-190`. `get()` loads `bootinfo` from cache if present (lines 138-143), but lines 170-171 always run `for hook in frappe.get_hooks("extend_bootinfo"): frappe.get_attr(hook)(bootinfo=bootinfo)`. So the hook (registered at hooks.py:15-17) executes on every boot request, regardless of the bootinfo cache. It then runs `_scan_missing_translations` (opens and parses every installed app's `.po`; `frappe/locale/zh.po` alone has 6,293 entries) and `load_app_translations` (16,886 rows) and `_log_missing_translations` (a `get_all` plus inserts). The "synchronous HTTP during boot" part of known #5 is **REFUTED as currently reachable**: `_auto_translate_via_api` always returns before any request due to A3. It becomes a real hang risk only if A3 is fixed, since `requests.post(..., timeout=120)` is retried 3× per batch inline in the boot request.

### A9 — `bench_commands` hook is a no-op (CONFIRMED no-op, known #1)
Method: `frappe/utils/bench_helper.py::get_app_commands` does `importlib.import_module(f"{app}.commands")` and reads `getattr(module, "commands", [])`; `frappe/commands/__init__.py` builds the frappe group from its own command lists. GitHub code search `bench_commands repo:frappe/frappe` returns no hits, i.e. no consumer of a `bench_commands` hook exists. The commands still work because commands.py:319-329 defines `commands = [...]`, but hooks.py:30-32 has no effect.

### A10 — 2-column rewrite / context drop / write amplification (3rd-column part CONFIRMED, CRLF part REFUTED, known #8)
Method:
- Frappe's canonical CSV is 3 columns: `write_csv_file` (frappe/translate.py:680-707) writes `w.writerow([message, translated_string, context])`, and `get_translation_dict_from_file` (frappe/translate.py:198-213) keys a context row as `item[0] + ":" + item[2]`.
- `_append_to_csv` (utils.py:436-442) writes `writer.writerow([k, v])` only, and `load_app_translations` (utils.py:43-51) reads only `row[0]`/`row[1]`. Any 3rd column would be dropped on write and ignored on read. Current `zh.csv` has 16,886 rows all with exactly 2 fields → **no present data loss, latent defect**.
- The "default CRLF" concern is **REFUTED**: the file already uses CRLF (`16886` CRLF vs `0` bare LF) and `csv.writer`'s default `lineterminator="\r\n"` matches; Frappe reads with `open(path, newline="")` + `csv.reader` (frappe/translate.py:668-677), which handles CRLF fine.
- Additional confirmed hazard: `on_translation_update` (utils.py:447-454) calls `_append_to_csv(..., overwrite=True)` on every `Translation` save; `_append_to_csv` calls `load_app_translations()` and rewrites all 16,886 rows with no file lock, so two concurrent saves can lose each other's update (read-modify-write race).

### A11 — 76 dead spaced-key translations (CONFIRMED)
Method: parsed the CSV and compared to Frappe's lookup path.
- `csv.reader` found `16886` rows, all 2 columns; `76` keys have leading/trailing whitespace, e.g. `' Rate'→'费率'`, `' Item'→'物料'`, `' Phantom Item'→'虚拟物料'`.
- Frappe's `_()` strips the lookup string (`frappe/__init__.py:119-120` `msg = as_unicode(msg).strip()`) and `get_translation_dict_from_file` uses the raw `item[0]` as key (frappe/translate.py:204-213), so `" Address"` can never match `_("Address")`.
- Many spaced keys are shadowed by a correctly-spaced key with a different value (e.g. `'Rate'→'单价'`, `'Phantom Item'→'虚拟项目'`), so the spaced entries are not merely redundant — they are silently discarded. `utils.load_app_translations` has the same no-strip behaviour.

### A12 — install-order priority assumption (CONFIRMED as fragile, medium confidence)
Method: `frappe/translate.py:174-189` `get_translations_from_apps` iterates `frappe.get_installed_apps(_ensure_on_bench=True)` and, per app, does `translations.update(csv)` then `translations.update(mo)`; later iterations win. `frappe/__init__.py:1559-1577` returns the persisted `installed_apps` list (install order). The hooks.py:8-12 comment and README "later apps override earlier … this app loads AFTER frappe/erpnext" hold only if `custom_translations` is installed last; installing ERPNext/HRMS after it would let their `.mo` override this app's CSV.

### A13 — literal `{site}` in after_install output (CONFIRMED)
Method: setup.py:34-39 are plain `str` literals (no `f` prefix), so the placeholder is printed verbatim. Cosmetic only.

### A14 — dead language fallback (CONFIRMED, medium confidence)
Method: `frappe/__init__.py:240` `local.lang = local.conf.lang or "en"` runs during `connect()`, so `frappe.local.lang` is always truthy when the boot hook executes; the `or frappe.db.get_default("language") or "zh"` branches in utils.py:66 are unreachable. Practical impact is limited (the hook keys off the request language), but the intended site-default fallback never applies.

## Status of the 8 pre-supplied findings

| known # | claim | verdict | notes |
|---------|-------|---------|-------|
| 1 | `bench_commands` may be a no-op | **CONFIRMED (no-op)** | A9; commands are discovered by importing `<app>.commands`. Harmless because `commands` is defined. |
| 2 | boot passes a raw site_config dict lacking `is_configured` | **CONFIRMED** | A3; also bypasses env/`config.json`. |
| 3 | `apply_manual_corrections` ANDs `filters` and `or_filters` | **CONFIRMED** | A4; `db_query.py:553`. |
| 4 | `frappe.model.sync_file_to_doc` may not exist | **CONFIRMED (does not exist)** | A7; swallowed AttributeError. |
| 5 | boot scans every app on every boot, can do synchronous HTTP | **PARTIALLY CONFIRMED** | A8: scanning/DB-writes on every boot CONFIRMED; synchronous HTTP is currently unreachable because of #2 (latent risk only). |
| 6 | `_get_app_po_path` assumes `locale/zh.po`; ERPNext/HRMS ship `translations/*.csv` | **CONFIRMED** | A1; ERPNext/HRMS have no `locale/` at all, so they are always skipped. |
| 7 | blind substring batch replacement produced wrong verb-sense translations | **CONFIRMED** | A5; four concrete `报告→报表` corruptions in the shipped CSV. |
| 8 | `_append_to_csv` rewrites whole CSV (CRLF) and drops the 3rd column | **PARTIALLY CONFIRMED** | A10: 3rd-column drop CONFIRMED (latent, 0 rows today) + write-amplification race; the CRLF claim is REFUTED (file is already CRLF and Frappe handles it). |

## Refuted / non-defects (checked, not real defects)

- **`bench --site all clear-cache` in `sync_to_po_files`** — valid: `clear_cache` loops `for site in context.sites` (frappe/commands/utils.py:107-121) and `get_sites("all")` expands to all sites.
- **`bench compile-po-to-mo --app <app>`** — valid command with an `--app` option (frappe/commands/gettext.py:19-29).
- **`doc_events` handler signature** — `on_translation_update(doc, method)` matches Frappe: the hook runner calls `f(self, method, *args, **kwargs)` (frappe/model/document.py:1338-1376).
- **`extend_bootinfo` keyword call** — Frappe calls `hook(bootinfo=bootinfo)` (frappe/sessions.py:171); `def detect_missing_translations_bootinfo(bootinfo)` accepts it.
- **`language="zh"` Link on the log doctype** — `zh` is a real Language code (`frappe/geo/languages.json`: `{"code": "zh", "name": "简体中文"}`; Language `autoname = field:language_code`).
- **`professional_glossary.py`** — 416 entries, no missing-Chinese values, no placeholder mismatches, no keys needing trimming, and every glossary key/value already matches the current CSV (so applying it is idempotent and cannot corrupt anything). No defect found.
- **`config.py` priority order** — site_config → config.json → env → defaults is applied in that order, so env/config.json correctly win; `is_configured` is recomputed last. No defect found. (Minor: `config.example.json` ships a placeholder `api_key` with `auto_translate:true`, so a copy-paste yields `is_configured=True` and failing HTTP calls — noted, low.)
- **Syntax** — all six Python modules and the doctype controller compile (`python3 -m py_compile ...` → OK).

## Method summary

1. Read every in-scope file in full and computed the shipped CSV's shape with Python (`16886` rows, all 2 columns, `16886` CRLF / `0` LF, 76 spaced keys, 0 `报告` / 235 `报表`).
2. Fetched `frappe/frappe@version-15` sources for `translate.py`, `__init__.py`, `boot.py`, `sessions.py`, `model/sync.py`, `model/__init__.py`, `model/db_query.py`, `model/document.py`, `model/base_document.py`, `commands/__init__.py`, `commands/gettext.py`, `commands/utils.py`, `utils/bench_helper.py`, `database/schema.py`, `database/mariadb/database.py`, `gettext/translate.py`, `geo/languages.json`.
3. Verified ERPNext/HRMS/FRAPPE shipped translation layout via the GitHub contents/trees APIs and `gh api search/code`.
4. Each finding cites the concrete frappe source line that proves the semantics and a concrete failure scenario; confidence is stated per finding.
