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
