# Where Frappe-family apps actually keep their Chinese translations

Evidence gathered by querying GitHub (`gh api`) and `raw.githubusercontent.com` on the
branches below. All commands were actually run; raw outputs are trimmed but unedited.
Everything is reproducible from the commands shown. Where a fact could not be confirmed
from a live command it is marked **UNVERIFIED**.

Repo under investigation: `534627605/custom_translations` (working tree `/workspace`,
commit `dad7a7d`). Its code hardcodes the path `frappe.get_app_path(app)/"locale"/"zh.po"`
in two places:

- `custom_translations/utils.py:128` — `_get_app_po_path()` → `Path(app_path) / "locale" / "zh.po"`
- `custom_translations/commands.py:102` — `po_path = Path(app_path) / "locale" / "zh.po"`

## Summary table

| app | default branch | latest branch checked | module dir | translation dir(s) present | Chinese files present | format | Chinese coverage (translated/total) | coverage command |
|-----|----------------|-----------------------|-----------|----------------------------|-----------------------|--------|-------------------------------------|------------------|
| frappe/frappe | develop | **develop** (= release v16.51.0) | `frappe/` | `frappe/locale` | `zh.po`, `zh_TW.po`, `main.pot` | po | **5963 / 7798** | `python3 /tmp/ev/count_po.py frappe_develop_zh.po` |
| frappe/frappe | develop | version-15 | `frappe/` | `frappe/translations` | `zh.csv`, `zh-TW.csv` | csv | **4797 / 4797** rows | python csv reader (see evidence) |
| frappe/erpnext | develop | **develop** (v16 branch) | `erpnext/` | `erpnext/locale` | `zh.po`, `zh_TW.po`, `main.pot` | po | **8082 / 10831** | `python3 /tmp/ev/count_po.py erpnext_develop_zh.po` |
| frappe/erpnext | develop | version-15 (release v15.122.0) | `erpnext/` | `erpnext/translations` | `zh.csv`, `zh-TW.csv`, `zh_tw.csv` | csv | **11885 / 11885** rows | python csv reader |
| frappe/hrms | develop | **develop** | `hrms/` | `hrms/locale` | `zh.po`, `zh_TW.po`, `main.pot` | po | **2101 / 2252** | `python3 /tmp/ev/count_po.py hrms_develop_zh.po` |
| frappe/hrms | develop | version-15 (release v15.64.3) | `hrms/` | `hrms/translations` | `zh.csv`, `zh-TW.csv` | csv | **1131 / 1131** rows | python csv reader |
| frappe/payments | develop | **develop** (also v15/v14/v16) | `payments/` | **none** | **none** | n/a | n/a | tree grep (see evidence) |
| frappe/wiki | develop | **develop** (also v14) | `wiki/` | **none** (`frontend/src/translation.js` only) | **none** | n/a (runtime API) | n/a | tree grep (see evidence) |
| frappe/helpdesk | develop | **develop** (release v1.30.2) | `helpdesk/` | `helpdesk/locale` | `zh.po`, `main.pot` | po | **730 / 1379** | `python3 /tmp/ev/count_po.py helpdesk_develop_zh.po` |
| frappe/webshop | develop | **develop** (also v15/v16) | `webshop/` | **none** | **none** | n/a | n/a | tree grep (see evidence) |
| frappe/telephony | develop | **develop** (only branch) | `telephony/` | **none** | **none** | n/a | n/a | tree grep (see evidence) |

Headline: **the big three (frappe, erpnext, hrms) use `translations/<lang>.csv` on the
version-14/15 lines and switched to `locale/<lang>.po` on develop / version-16.**
payments, webshop and telephony ship **no** translation files at all on any branch, and
wiki has no locale directory.

---

## Evidence — frappe/frappe

### Branch discovery

```
$ gh api repos/frappe/frappe --jq '.default_branch'
develop
$ for b in develop version-15 version-14 version-16; do gh api repos/frappe/frappe/branches/$b --jq .name; done
develop
version-15
version-14
version-16
```
All four branches exist. Latest release (for context):
```
$ gh api repos/frappe/frappe/releases/latest --jq '.tag_name'
v16.51.0
```

### Module dir + translation dirs

```
$ gh api repos/frappe/frappe/contents --jq '.[] | select(.type=="dir") | .name'
.github .greptile esbuild frappe playwright realtime ui
```
The Python package is `frappe/` (same as repo name).

```
$ gh api repos/frappe/frappe/contents/frappe/locale?ref=develop --jq '.[].name'
... vi.po zh.po zh_TW.po
$ gh api repos/frappe/frappe/contents/frappe/translations?ref=develop --jq '.[].name'
{"message":"Not Found",...,"status":"404"}
```
- **develop**: `frappe/locale/` exists (PO files), `frappe/translations/` does **not**.
- **version-16**: same as develop — `frappe/locale` has `zh.po zh_TW.po`; `frappe/translations` → 404.
- **version-15**: `frappe/locale` → **404**; `frappe/translations` exists with `... zh-TW.csv zh.csv`.
- **version-14**: `frappe/locale` → **404**; `frappe/translations` exists with `... zh-TW.csv zh.csv zh_tw.csv`.

Recursive tree confirms no `translations/` dir anywhere on develop:
```
$ gh api repos/frappe/frappe/git/trees/develop?recursive=1 --jq '.tree[].path' | grep -iE '/translations/|\.csv$'
babel_extractors.csv
frappe/core/doctype/data_import/fixtures/sample_import_file.csv
frappe/geo/languages.csv
... (no app-level translations CSV)
```

### Chinese files (all candidate names)

- `zh.po` — YES (develop, version-16)
- `zh_TW.po` — YES (develop, version-16)
- `zh_CN.po` / `zh_Hans.po` — NO
- `main.pot` — YES (develop, version-16)
- `zh.csv` — YES (version-15, version-14)
- `zh-TW.csv` — YES (version-15, version-14); `zh_tw.csv` also on version-14

### Coverage (develop, `frappe/locale/zh.po`)

```
$ curl -s -o frappe_develop_zh.po https://raw.githubusercontent.com/frappe/frappe/develop/frappe/locale/zh.po
$ wc -l frappe_develop_zh.po
42386 frappe_develop_zh.po
$ python3 /tmp/ev/count_po.py frappe_develop_zh.po
/tmp/ev/frappe_develop_zh.po: total_msgid=7798 empty_msgstr=1835 translated=5963
```
Cross-check with grep (1 extra = the file header `msgid ""`):
```
$ grep -c '^msgid "' frappe_develop_zh.po
7799
$ grep -c '^msgstr ""' frappe_develop_zh.po
1836
```
PO header (shows it is Simplified Chinese, `Language: zh_CN`, generated by Crowdin):
```
msgid ""
msgstr ""
"Project-Id-Version: frappe\n"
...
"X-Crowdin-Language: zh-CN\n"
"Language: zh_CN\n"
```

### Coverage (version-15, `frappe/translations/zh.csv`)

```
$ curl -s -o frappe_v15_zh.csv https://raw.githubusercontent.com/frappe/frappe/version-15/frappe/translations/zh.csv
$ wc -l frappe_v15_zh.csv
4797 frappe_v15_zh.csv
$ python3 - <<'PY'   # csv.reader over the file
frappe_v15_zh.csv: rows=4797 translated(non-empty col2)=4797 empty_col2=0
PY
$ head -5 frappe_v15_zh.csv
A4,A4,
API Endpoint,应用程序界面端点,
API Key,应用程序界面密钥,
Access Token,访问令牌,
Account,科目,
```
The CSV contains **only translated pairs** (every row has a non-empty column 2), so
"coverage" is simply the row count.


---

## Evidence — frappe/erpnext

```
$ gh api repos/frappe/erpnext --jq '.default_branch'
develop
$ for b in develop version-15 version-14 version-16; do gh api repos/frappe/erpnext/branches/$b --jq .name; done
develop version-15 version-14 version-16
$ gh api repos/frappe/erpnext/releases/latest --jq '.tag_name'
v15.122.0
```

Module dir is `erpnext/`:
```
$ gh api repos/frappe/erpnext/contents --jq '.[] | select(.type=="dir") | .name'
.github .greptile banking erpnext semgrep
$ gh api repos/frappe/erpnext/contents/erpnext/locale?ref=develop --jq '.[].name'
... vi.po zh.po zh_TW.po
$ gh api repos/frappe/erpnext/contents/erpnext/translations?ref=develop --jq '.[].name'
{"message":"Not Found",...,"status":"404"}
$ gh api repos/frappe/erpnext/contents/erpnext/translations?ref=version-15 --jq '.[].name'
... zh-TW.csv zh.csv zh_tw.csv
$ gh api repos/frappe/erpnext/contents/erpnext/locale?ref=version-15 --jq '.[].name'
{"message":"Not Found",...,"status":"404"}
```
- develop / version-16 → `erpnext/locale` (`zh.po`, `zh_TW.po`, `main.pot`); no `translations/`.
- version-15 / version-14 → `erpnext/translations` (`zh.csv`, `zh-TW.csv`, `zh_tw.csv`); no `locale/`.

### Coverage (develop, `erpnext/locale/zh.po`)

```
$ curl -s -o erpnext_develop_zh.po https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/locale/zh.po
$ wc -l erpnext_develop_zh.po
66931 erpnext_develop_zh.po
$ python3 /tmp/ev/count_po.py erpnext_develop_zh.po
/tmp/ev/erpnext_develop_zh.po: total_msgid=10831 empty_msgstr=2749 translated=8082
```
grep cross-check: `^msgid "` = 10832, `^msgstr ""` = 2750 (both minus the header = matches).

### Coverage (version-15, `erpnext/translations/zh.csv`)

```
$ curl -s -o erpnext_v15_zh.csv https://raw.githubusercontent.com/frappe/erpnext/version-15/erpnext/translations/zh.csv
$ wc -l erpnext_v15_zh.csv
12219 erpnext_v15_zh.csv
$ python3 - <<'PY'
erpnext_v15_zh.csv: rows=11885 translated(non-empty col2)=11885 empty_col2=0
PY
```

---

## Evidence — frappe/hrms

```
$ gh api repos/frappe/hrms --jq '.default_branch'
develop
$ for b in develop version-15 version-14 version-16; do gh api repos/frappe/hrms/branches/$b --jq .name; done
develop version-15 version-14 version-16
$ gh api repos/frappe/hrms/releases/latest --jq '.tag_name'
v15.64.3
$ gh api repos/frappe/hrms/contents --jq '.[] | select(.type=="dir") | .name'
.github docker frontend hrms roster semgrep
```
Module dir is `hrms/`.

```
$ gh api repos/frappe/hrms/contents/hrms/locale?ref=develop --jq '.[].name'
... uz.po vi.po zh.po zh_TW.po
$ gh api repos/frappe/hrms/contents/hrms/translations?ref=develop --jq '.[].name'
{"message":"Not Found",...,"status":"404"}
$ gh api repos/frappe/hrms/contents/hrms/translations?ref=version-15 --jq '.[].name'
... zh-TW.csv zh.csv
$ gh api repos/frappe/hrms/contents/hrms/locale?ref=version-15 --jq '.[].name'
{"message":"Not Found",...,"status":"404"}
```
- develop / version-16 → `hrms/locale` (`zh.po`, `zh_TW.po`, `main.pot`).
- version-15 / version-14 → `hrms/translations` (`zh.csv`, `zh-TW.csv`).

### Coverage (develop, `hrms/locale/zh.po`)

```
$ curl -s -o hrms_develop_zh.po https://raw.githubusercontent.com/frappe/hrms/develop/hrms/locale/zh.po
$ wc -l hrms_develop_zh.po
12027 hrms_develop_zh.po
$ python3 /tmp/ev/count_po.py hrms_develop_zh.po
/tmp/ev/hrms_develop_zh.po: total_msgid=2252 empty_msgstr=151 translated=2101
```
grep cross-check: `^msgid "` = 2253, `^msgstr ""` = 152 (minus header = matches).

### Coverage (version-15, `hrms/translations/zh.csv`)

```
$ curl -s -o hrms_v15_zh.csv https://raw.githubusercontent.com/frappe/hrms/version-15/hrms/translations/zh.csv
$ wc -l hrms_v15_zh.csv
1187 hrms_v15_zh.csv
$ python3 - <<'PY'
hrms_v15_zh.csv: rows=1131 translated(non-empty col2)=1131 empty_col2=0
PY
```


---

## Evidence — frappe/payments

```
$ gh api repos/frappe/payments --jq '.default_branch'
develop
$ for b in develop version-15 version-14 version-16; do gh api repos/frappe/payments/branches/$b --jq .name; done
develop version-15 version-14 version-16
$ gh api repos/frappe/payments/contents --jq '.[] | "\(.type) \(.name)"'
file .eslintrc
dir .github
dir payments
file pyproject.toml
dir semgrep
```
Module dir is `payments/`. Neither candidate dir exists on any branch:
```
$ for b in develop version-15 version-14 version-16; do
    gh api "repos/frappe/payments/contents/payments/locale?ref=$b" --jq '.[].name'
    gh api "repos/frappe/payments/contents/payments/translations?ref=$b" --jq '.[].name'
  done
{"message":"Not Found",...,"status":"404"}   # x8 (both dirs, all 4 branches)
```
Repo-root-level dirs also absent:
```
$ gh api repos/frappe/payments/contents/locale?ref=develop --jq '.[].name'
{"message":"Not Found",...,"status":"404"}
$ gh api repos/frappe/payments/contents/translations?ref=develop --jq '.[].name'
{"message":"Not Found",...,"status":"404"}
```
Recursive tree (whole repo, `truncated=false`, 149 entries) has no locale / translation / .po / .pot / app-level .csv:
```
$ gh api repos/frappe/payments/git/trees/develop?recursive=1 --jq '.truncated, (.tree|length)'
false
149
$ gh api repos/frappe/payments/git/trees/develop?recursive=1 --jq '.tree[].path' | grep -iE 'zh|locale|translation|\.po$|\.pot$|\.csv$'
(no output)
```
**Conclusion: frappe/payments ships NO Chinese translation file (and no translation file of any kind) on develop, version-15, version-14 or version-16.**

---

## Evidence — frappe/wiki

```
$ gh api repos/frappe/wiki --jq '.default_branch'
develop
$ gh api repos/frappe/wiki/branches/version-15 --jq .name
{"message":"Branch not found",...,"status":"404"}
$ gh api repos/frappe/wiki/branches/version-14 --jq .name
version-14
```
Only `develop` and `version-14` (plus `master`) exist; there is no `version-15`.

```
$ gh api repos/frappe/wiki/contents --jq '.[] | select(.type=="dir") | .name'
.github docs e2e frontend scripts skills specs wiki worktrees
$ gh api repos/frappe/wiki/contents/wiki/locale?ref=develop --jq '.[].name'
{"message":"Not Found",...,"status":"404"}
$ gh api repos/frappe/wiki/contents/wiki/translations?ref=develop --jq '.[].name'
{"message":"Not Found",...,"status":"404"}
```
Recursive tree finds **no** `.po`/`.pot`/`locale/` at all; the only translation-related paths are:
```
$ gh api repos/frappe/wiki/git/trees/develop?recursive=1 --jq '.tree[].path' | grep -iE 'zh|locale|translation|\.po$|\.pot$'
frontend/src/translation.js
specs/crowdin_translation_sync.md
```
`frontend/src/translation.js` fetches messages at runtime from the server API, not a file:
```
function fetchTranslations() {
	createResource({ url: 'wiki.api.get_translations', auto: true,
		transform: (data) => { window.translatedMessages = data; } });
}
```
The repo's own spec (`specs/crowdin_translation_sync.md`, dated 2026-07-07) states the current state explicitly:
> **No** `crowdin.yml`, **no** `wiki/locale/`, **no** `*.pot`. … Wiki has **none** of this today.

**Conclusion: frappe/wiki has no in-repo Chinese (or any) translation file; translations come from the server-side Translation store via `wiki.api.get_translations`; Crowdin sync is "Planned. Not yet started."**


---

## Evidence — frappe/helpdesk

```
$ gh api repos/frappe/helpdesk --jq '.default_branch'
develop
$ gh api repos/frappe/helpdesk/branches/version-15 --jq .name
{"message":"Branch not found",...,"status":"404"}
$ gh api repos/frappe/helpdesk/branches/version-14 --jq .name
version-14
$ gh api repos/frappe/helpdesk/releases/latest --jq '.tag_name'
v1.30.2
```
Only `develop` and `version-14` exist (no `version-15`).

```
$ gh api repos/frappe/helpdesk/contents --jq '.[] | select(.type=="dir") | .name'
.github desk docker e2e helpdesk realtime
$ gh api repos/frappe/helpdesk/contents/helpdesk/locale?ref=develop --jq '.[].name'
... uz.po vi.po zh.po
$ gh api repos/frappe/helpdesk/contents/helpdesk/translations?ref=develop --jq '.[].name'
{"message":"Not Found",...,"status":"404"}
$ gh api repos/frappe/helpdesk/contents/helpdesk/locale?ref=version-14 --jq '.[].name'
{"message":"Not Found",...,"status":"404"}
$ gh api repos/frappe/helpdesk/contents/helpdesk/translations?ref=version-14 --jq '.[].name'
{"message":"Not Found",...,"status":"404"}
```
- develop → `helpdesk/locale` with `zh.po` and `main.pot` (note: **no `zh_TW.po`** here).
- version-14 → **neither** dir; recursive tree on version-14 returns nothing for translation paths.

### Coverage (develop, `helpdesk/locale/zh.po`)

```
$ curl -s -o helpdesk_develop_zh.po https://raw.githubusercontent.com/frappe/helpdesk/develop/helpdesk/locale/zh.po
$ wc -l helpdesk_develop_zh.po
6769 helpdesk_develop_zh.po
$ python3 /tmp/ev/count_po.py helpdesk_develop_zh.po
/tmp/ev/helpdesk_develop_zh.po: total_msgid=1379 empty_msgstr=649 translated=730
```
grep cross-check: `^msgid "` = 1380, `^msgstr ""` = 650 (minus header = matches).

---

## Evidence — frappe/webshop

```
$ gh api repos/frappe/webshop --jq '.default_branch'
develop
$ for b in develop version-15 version-16 version-14; do echo -n "$b: "; gh api repos/frappe/webshop/branches/$b --jq .name 2>&1; done
develop: develop
version-15: version-15
version-16: version-16
version-14: {"message":"Branch not found",...,"status":"404"}
$ gh api repos/frappe/webshop/contents --jq '.[] | select(.type=="dir") | .name'
.github webshop
```
Branches: develop, version-15, version-16 (no version-14). Module dir is `webshop/`.

```
$ for b in develop version-15 version-16; do
    gh api "repos/frappe/webshop/contents/webshop/locale?ref=$b" --jq '.[].name'
    gh api "repos/frappe/webshop/contents/webshop/translations?ref=$b" --jq '.[].name'
  done
{"message":"Not Found",...,"status":"404"}   # x6 (both dirs, all 3 branches)
```
Repo-root dirs also absent; recursive tree (236 entries, `truncated=false`) has no translation paths:
```
$ gh api repos/frappe/webshop/git/trees/develop?recursive=1 --jq '.tree[].path' | grep -iE 'i18n|lang|\.po$|\.pot$|\.csv$|zh'
(no output)
```
**Conclusion: frappe/webshop ships NO Chinese (or any) translation file on develop, version-15 or version-16.**

---

## Evidence — frappe/telephony

```
$ gh api repos/frappe/telephony --jq '.default_branch'
develop
$ for b in develop version-15 version-14 version-16; do echo -n "$b: "; gh api repos/frappe/telephony/branches/$b --jq .name 2>&1; done
develop: develop
version-15: {"message":"Branch not found",...,"status":"404"}
version-14: {"message":"Branch not found",...,"status":"404"}
version-16: {"message":"Branch not found",...,"status":"404"}
$ gh api repos/frappe/telephony/contents --jq '.[] | select(.type=="dir") | .name'
.github telephony
```
Only `develop` exists. Module dir is `telephony/`.

```
$ gh api repos/frappe/telephony/contents/telephony/locale?ref=develop --jq '.[].name'
{"message":"Not Found",...,"status":"404"}
$ gh api repos/frappe/telephony/contents/telephony/translations?ref=develop --jq '.[].name'
{"message":"Not Found",...,"status":"404"}
```
Repo-root dirs also absent; recursive tree (91 entries, `truncated=false`) has no translation paths:
```
$ gh api repos/frappe/telephony/git/trees/develop?recursive=1 --jq '.tree[].path' | grep -iE 'i18n|lang|\.po$|\.pot$|\.csv$|zh'
(no output)
```
**Conclusion: frappe/telephony ships NO Chinese (or any) translation file on develop.**


---

## Framework-side convention (Frappe source)

Source read: `frappe/gettext/translate.py` and `frappe/translate.py`, on both
`version-15` and `develop`.

### v15 — `frappe/gettext/translate.py` (PO / MO compilation)

```
13: PO_DIR = "locale"  # po and pot files go into [app]/locale
17: POT_FILE = "main.pot"  # the app's pot file is always main.pot
41: def get_po_dir(app: str) -> Path:
42: 	return Path(frappe.get_app_path(app)) / PO_DIR
45: def get_locale_dir() -> Path:
46: 	return Path(get_bench_path()) / "sites" / "assets" / "locale"
57: def get_po_path(app: str, locale: str | None = None) -> Path:
58: 	return get_po_dir(app) / f"{locale}.po"
61: def get_mo_path(app: str, locale: str | None = None) -> Path:
62: 	return get_locale_dir() / locale / "LC_MESSAGES" / f"{app}.mo"
```
→ PO source is `<app>/locale/<locale>.po`; the compiled binary lands in
`sites/assets/locale/<locale>/LC_MESSAGES/<app>.mo`.

### v15 — `frappe/translate.py` (runtime CSV loading)

```
174: def get_translations_from_apps(lang, apps=None):
...
182: 		translations.update(get_translations_from_csv(lang, app) or {})
183: 		translations.update(get_translations_from_mo(lang, app) or {})
...
192: def get_translations_from_csv(lang, app):
193: 	return get_translation_dict_from_file(
194: 		os.path.join(frappe.get_app_path(app, "translations"), lang + ".csv"), lang, app
195: 	)
```

**Answer for v15:**
- Frappe v15 loads CSVs from **`<app>/translations/<lang>.csv`** (e.g.
  `frappe/translations/zh.csv`). This is the primary runtime source.
- Frappe v15 compiles `.po` from **`<app>/locale/<lang>.po`** (PO_DIR = `"locale"`,
  `get_po_dir()` = `Path(frappe.get_app_path(app)) / "locale"`), and reads the compiled
  `.mo` from `sites/assets/locale/<lang>/LC_MESSAGES/<app>.mo`.
- Load order in `get_translations_from_apps`: CSV first, then MO **overrides** CSV.

### develop / v16 — same functions, same paths

```
$ curl -s .../frappe/develop/frappe/translate.py | grep -nE 'get_translations_from_csv|translations'
193: 		translations.update(get_translations_from_csv(lang, app) or {})
194: 		translations.update(get_translations_from_mo(lang, app) or {})
203: def get_translations_from_csv(lang, app):
204: 	return get_translation_dict_from_file(
205: 		os.path.join(frappe.get_app_path(app, "translations"), lang + ".csv"), lang, app
206: 	)
```
```
$ curl -s .../frappe/develop/frappe/gettext/translate.py | grep -nE 'PO_DIR|def get_po_dir|def get_mo_path'
17: PO_DIR = "locale"
41: def get_po_dir(app: str) -> Path:
42: 	return Path(frappe.get_app_path(app)) / PO_DIR
61: def get_mo_path(app, locale=None):
62: 	return get_locale_dir() / locale / "LC_MESSAGES" / f"{app}.mo"
```
`develop` also adds `get_translations_from_mo()` which reads
`get_mo_path(app, lang)` (`sites/assets/locale/<lang>/LC_MESSAGES/<app>.mo`) and keys
entries by `msgid` and `"msgid:context"`.

**Key takeaway:** the *code* still supports `<app>/translations/<lang>.csv` on develop,
but frappe/erpnext/hrms **no longer ship** a `translations/` directory there — they ship
`<app>/locale/*.po`, which the build compiles to `.mo`. So the effective source of truth
moved from `translations/zh.csv` (v14/v15) to `locale/zh.po` (v16/develop).

### Coverage-counting helper (exact command)

```python
# /tmp/ev/count_po.py
import re, sys
kw = re.compile(r'^(msgid|msgstr|msgid_plural|msgctxt|msgstr\[\d+\])\b(.*)$')
q  = re.compile(r'^"(.*)"$')
def counts(path):
    entries = []; cur = None; field = None
    for raw in open(path, encoding='utf-8'):
        s = raw.strip()
        if s == '':
            if cur: entries.append(cur); cur = None; field = None
            continue
        if s.startswith('#'): continue
        m = kw.match(s)
        if m:
            key = m.group(1); rest = m.group(2).strip()
            val = q.match(rest).group(1) if q.match(rest) else ''
            if key == 'msgid':
                if cur: entries.append(cur)
                cur = {'id': val, 'str': ''}; field = 'id'
            elif key.startswith('msgstr'):
                field = 'str'
                if cur is not None: cur['str'] += val
            else:
                field = None
        elif s.startswith('"') and cur is not None and field:
            mm = q.match(s)
            if mm: cur[field] += mm.group(1)
    if cur: entries.append(cur)
    total = sum(1 for e in entries if e['id'] != '')
    empty = sum(1 for e in entries if e['id'] != '' and e['str'] == '')
    return total, empty, total - empty
for p in sys.argv[1:]:
    t, e, n = counts(p)
    print(f"{p}: total_msgid={t} empty_msgstr={e} translated={n}")
```
Run: `python3 /tmp/ev/count_po.py <file>.po`. It excludes the header entry
(`msgid ""`) and validates against `grep -c '^msgid "'` minus 1.


---

## Implications for custom_translations

Every place where the current hardcoded `locale/zh.po` assumption breaks, with the evidence:

- **v14/v15 are broken outright — the file simply is not there.** On `version-14` and
  `version-15`, frappe/erpnext/hrms keep Chinese in `<app>/translations/zh.csv`; there is
  **no** `<app>/locale/` directory at all (`gh api .../frappe/locale?ref=version-15` → 404).
  Both `_get_app_po_path()` (`custom_translations/utils.py:128`,
  `Path(app_path) / "locale" / "zh.po"`) and `custom_translations/commands.py:102`
  therefore point at a non-existent path. Consequences: `_scan_missing_translations()`
  (`utils.py:98-100`) hits `if not po_path or not po_path.exists(): continue` and finds
  **nothing**; `sync_to_po_files()` (`utils.py:532-536`) prints
  `[<app>] no zh.po found, skipping` for every app. This silently disables the
  detect/sync feature on the current *released* line (frappe `v16.51.0` is the only v16
  release; erpnext `v15.122.0` and hrms `v15.64.3` are still v15).

- **The format is branch-dependent (CSV ↔ PO).** Newest branches use `.po`
  (`<app>/locale/zh.po`); v14/v15 use `.csv` (`<app>/translations/zh.csv`). A robust scan
  must handle both extensions/dirs and parse CSV with 2- or 3-column rows (the 3rd column
  is a context key, per `get_translation_dict_from_file` in `frappe/translate.py`) and
  `\n` un-escaping.

- **payments, webshop and telephony have no translation files on any branch.** Verified by
  recursive tree grep (`grep -iE 'zh|locale|translation|\.po$|\.pot$|\.csv$'` → empty) on
  develop / version-15 / version-14 / version-16. A file-based scan can *never* find Chinese
  for them; their strings exist only as source msgids (POT/Crowdin) or must come from this
  app's own `translations/zh.csv`.

- **wiki has no `locale/zh.po`.** Its Vue frontend fetches translations at runtime from
  `wiki.api.get_translations` (`frontend/src/translation.js`), and its own spec
  (`specs/crowdin_translation_sync.md`) says `wiki/locale/` and `*.pot` do not exist yet and
  Crowdin sync is "Planned. Not yet started." There is no file to scan or sync.

- **Filename variants are ignored.** Upstream Chinese files are `zh.po` + `zh_TW.po` (PO)
  and `zh.csv` + `zh-TW.csv` + `zh_tw.csv` (CSV). The code only matches the literal
  `zh.po`. `zh_CN.po` / `zh_Hans.po` were **not** found in any probed repo (so the code does
  not need them), but the hyphen/underscore CSV variants are real and unhandled.

- **Language-code normalisation is missing.** `frappe.gettext.translate.get_translations_from_mo`
  does `lang = lang.replace("-", "_")`; the app hardcodes `"zh"` everywhere
  (`SUPPORTED_LANG = "zh"`). Upstream `zh.po` declares `Language: zh_CN` while `zh_TW.po`
  is Traditional — the scan must not conflate the two, and the app's Simplified target
  should stay on the `zh`/`zh_CN` file, never `zh_TW`.

- **Editing `.po` alone does not take effect.** Even on develop, Frappe reads the compiled
  `.mo` from `sites/assets/locale/<lang>/LC_MESSAGES/<app>.mo` (`get_mo_path()` in
  `frappe/gettext/translate.py`), and `get_translations_from_apps()` applies MO *after* CSV
  (`translate.py:182-183`), so MO overrides CSV. `sync_to_po_files()` only recompiles
  frappe/erpnext/hrms (`utils.py:564-566`) and never payments/webshop/wiki/helpdesk/telephony
  → any other app stays stale. Also note `get_mo_path` uses the app's `locale` code while
  the PO header says `zh_CN`; the exact on-disk asset directory name per install is
  **UNVERIFIED** from source alone.

- **`export_from_frappe` shares the same bug.** `commands.py:94` hardcodes
  `apps = ["frappe", "erpnext", "hrms", "payments", "webshop"]` and then
  `po_path = Path(app_path) / "locale" / "zh.po"` (`commands.py:102`). It therefore exports
  nothing on v15, nothing for payments/webshop on any branch, and never covers
  wiki/helpdesk/telephony.

- **The one part that still works: this app's own CSV.** `<app>/translations/<lang>.csv` is
  still read by `get_translations_from_csv()` on **both** v15 and develop
  (`frappe/translate.py:192-195` / `:203-206`), and this app ships
  `custom_translations/translations/zh.csv`, which matches that convention. So the
  "independent CSV override" strategy is sound; what is broken is specifically the
  **scanning/sync of other apps' files**, which assumes `locale/zh.po`.

- **Apps with a `main.pot` but no `zh.po` are still scannable in principle.** On develop,
  frappe/erpnext/hrms/helpdesk each ship `<app>/locale/main.pot` (the full msgid template).
  For a "find untranslated strings" feature, `main.pot` is a more reliable source than
  `zh.po` because it always exists wherever gettext is used — but it is absent on v14/v15
  (no `locale/` at all) and absent for payments/webshop/telephony/wiki.

### Concrete break points (code references)

| Location | Assumption | Reality |
|----------|-----------|---------|
| `utils.py:128` `_get_app_po_path()` | `<app>/locale/zh.po` | v15 → `<app>/translations/zh.csv`; payments/webshop/telephony/wiki → no file |
| `utils.py:98-100` scan loop | skips if `locale/zh.po` missing | silently skips all of v15 and 4 apps on develop |
| `utils.py:533-536` `sync_to_po_files()` | writes `<app>/locale/zh.po` | no such file on v15; other apps never covered |
| `utils.py:564-566` recompile | only frappe/erpnext/hrms | payments/webshop/wiki/helpdesk/telephony never recompiled |
| `commands.py:94` app list | `frappe, erpnext, hrms, payments, webshop` | missing wiki, helpdesk, telephony; payments/webshop have no file |
| `commands.py:102` `export_from_frappe` | `<app>/locale/zh.po` | same break as `utils.py:128` |
| `SUPPORTED_LANG = "zh"` (`utils.py:26`) | single Chinese locale | upstream also has `zh_TW.po` / `zh-TW.csv`; MO lookup normalises `-`→`_` |


---

## 附录：版本与迁移矩阵（主 Agent 复核，含对前文 1 处更正）

> 以下数据于本次会话重新用 `gh api` 逐项核对，覆盖前文表述。

### A. 各仓库当前版本

| 仓库 | 最新 release | 默认分支 | 说明 |
|------|-------------|---------|------|
| frappe/frappe | **v16.51.0**（2026-10-07） | `develop` | 有 version-14 / 15 / 16 三条线 |
| frappe/erpnext | **v15.122.0**（2026-10-07） | `develop` | `develop` 即 v16 开发线；正式线仍在 v15 |
| frappe/hrms | **v15.64.3**（2026-10-07） | `develop` | 同上 |
| frappe/helpdesk | **v1.30.2**（2026-10-10） | `develop` | 另有 `main` 线，zh.po 与 develop 一致 |
| frappe/wiki | **v3.4.0**（2026-10-08） | `develop` | 无 locale 目录 |
| frappe/payments | 无 release | `develop` | 无任何中文文件 |
| frappe/webshop | 无 release | `develop` | 无任何中文文件 |
| frappe/telephony | 无 release | `develop` | 无任何中文文件 |

### B. 中文翻译文件位置（逐分支实测，`gh api .../contents/<path>?ref=<branch>`）

| App | version-14 | version-15 | version-16 / develop |
|-----|-----------|-----------|---------------------|
| frappe | `translations/zh.csv` (236 KB) | **两者都有**：`locale/zh.po` (1.27 MB) + `translations/zh.csv` (238 KB) | 仅 `locale/zh.po` (1.33 MB) |
| erpnext | `translations/zh.csv` (489 KB) | `translations/zh.csv` (724 KB)，**无 locale 目录** | 仅 `locale/zh.po` (2.83 MB) |
| hrms | `translations/zh.csv` (88 KB) | `translations/zh.csv` (55 KB)，**无 locale 目录** | 仅 `locale/zh.po` (447 KB) |
| helpdesk | — | — | `locale/zh.po` (230 KB) |
| payments / webshop / telephony / wiki | 无 | 无 | **无** |

> **更正前文**：前文「frappe version-15 → `frappe/locale` 404」不成立。
> 实测 `frappe/locale/zh.po` 在 **version-15 上存在**（1,271,306 字节），v15 同时保留了旧的
> `translations/zh.csv`（双轨）。真正只有 CSV 的是 **erpnext / hrms 的 v14 与 v15**。

### C. 变更事项（翻译机制迁移）

| 事项 | 内容 |
|------|------|
| frappe 迁移 PR | **#22732「feat: translations via gettext」**，2024-01-10 合入 `develop` |
| frappe v15 移植 PR | **#25982「feat: gettext translations (v15 port)」**，2024-04-17 合入（base `version-15-hotfix`）→ 所以 v15 双轨 |
| erpnext 迁移 PR | **#39313「chore: migrate translations to gettext」**，2024-01-11 合入 `develop`，**未回移 version-15** |
| 格式 | `translations/<lang>.csv` → `locale/<lang>.po` + `locale/main.pot`，编译为 `sites/assets/locale/<lang>/LC_MESSAGES/<app>.mo` |
| 新模块/命令 | `frappe/gettext/`（`translate.py` + `extractors/`）；`bench generate-pot-file`、`bench compile-po-to-mo`、`bench new-po` |
| 加载顺序 | 同一 App 内先 CSV 后 MO，**MO 覆盖 CSV**（`frappe/translate.py: get_translations_from_apps`） |
| 文件名 | v16：`zh.po` + `zh_TW.po`；v15：`zh.csv` + `zh-TW.csv` / `zh_tw.csv` |
| 兼容性 | `<app>/translations/<lang>.csv` 仍然被支持（本 App 正是依赖它注入词条） |
| 近期相关修复 | #43416（2026-09-28）JS 嵌套 `__()` 未进 POT；#38063（2026-03-16）模板字符串抽取行号 |

### D. 对本 App 的影响（为什么必须双布局探测）

- **v15 站点**：frappe 双轨（旧代码「碰巧」能用），**erpnext / hrms 只有 CSV**（旧代码静默返回 0）
  —— 与用户反馈的「无法适配最新版本」完全吻合。
- **v16 / develop 站点**：三者都是 `locale/*.po`（旧代码可用）。
- 因此任何只认一种布局的实现都会在另一条版本线上失效；本 App 现已同时支持 CSV / PO / POT，
  并对 payments / webshop / telephony / wiki（永无翻译文件）退化为源码扫描。

