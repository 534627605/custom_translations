# 检查与修正报告（custom_translations v1.1）

日期：本次会话　基线 commit：`dad7a7d`　修正分支：`cline/6q4b4eqh`

## 1. 结论摘要

这份 App 的核心思路（用独立的 `translations/zh.csv` 覆盖官方翻译）是正确的，**不需要推倒重来**；
但「扫描缺失词条 / 同步 / 导出」这一半功能建立在**一个已经失效的路径假设**上，对最新版本的
erpnext / hrms 完全失效；同时存在 1 个**会删除 16886 条人工词条**的数据破坏性命令、
1 个让 AI 补缺在 boot 路径永久空转的配置 bug、1 套**已经污染了线上数据**的术语替换逻辑。

本次共修正 **14 个缺陷**（其中 6 个 HIGH）、修正词条库 **66 条**误译、新增 **65 个单元测试**，
并补齐了 4 个新模块（多布局发现 / 零依赖 PO / 译文校验 / 智能翻译引擎）。

## 2. 根因：翻译文件布局假设失效（用户反馈的「无法适配最新版本」）

旧代码在 2 处硬编码 `frappe.get_app_path(app)/"locale"/"zh.po"`：

- `utils.py` `_get_app_po_path()`（扫描与同步用）
- `commands.py` `export_from_frappe()`（导出用）

实测各 App 官方仓库（`gh api` 取证，完整证据见 `docs/app-translation-layouts.md`）：

| App | v14 / v15 | develop / v16 | 官方中文缺口 |
|-----|-----------|---------------|-------------|
| frappe | `frappe/translations/zh.csv` | `frappe/locale/zh.po` + `main.pot` | 1835 / 7798 |
| erpnext | `erpnext/translations/zh.csv`（**无 locale 目录**） | `erpnext/locale/zh.po` + `main.pot` | 2749 / 10831 |
| hrms | `hrms/translations/zh.csv` | `hrms/locale/zh.po` + `main.pot` | 151 / 2252 |
| helpdesk | `helpdesk/locale/zh.po` | `helpdesk/locale/zh.po` | 649 / 1379 |
| payments / webshop / telephony / wiki | **无任何中文翻译文件** | **无任何中文翻译文件** | 只能由本 App 词条库覆盖 |

后果（已复现）：在 v15 站点上 `custom-translations-scan` 对 erpnext/hrms 返回 0 条，
`sync` 打印 `no zh.po found, skipping`，`export` 导出 0 条 —— 而这两个 App 恰恰是词条量最大的。

**修正**：新增 `sources.py`，探测 `translations/`、`locale/`、`translations/locale/`
（模块目录与源码根目录都探测）× `zh.po/zh_CN.po/zh_Hans.po/zh.csv/main.pot`；
对完全没有 PO/POT 的 App 退化为**源码扫描**（解析 `.py/.js/.html/.vue` 中的 `_("...")`）。
扫描、覆盖率、导出、同步、`bench generate-pot-file` 之外的路径全部改走该模块。

## 3. 缺陷清单（已全部修复）

| ID | 严重度 | 位置 | 问题 | 修正 | 验证 |
|----|--------|------|------|------|------|
| B1 | **HIGH** | `utils.py` `_get_app_po_path` | 硬编码 `locale/zh.po`，erpnext/hrms 恒为 0 结果 | 改用 `sources.discover_app()` | `test_finds_missing_in_both_layouts` |
| B2 | **HIGH** | `commands.py` `export_from_frappe` | 以 `"w"` 打开人工词条库，只写入 frappe 的 6112 条 → **删除 16886 条词条、术语表与人工纠偏** | 默认写入 `translations/zh.imported.csv`；`--merge` 才写回且默认不覆盖 | 命令默认路径断言 |
| B3 | **HIGH** | `utils.py` `_auto_translate_via_api` | boot 路径传入裸 `site_config`，缺少 `is_configured` → 永久早退；且忽略环境变量/`config.json` | 统一 `load_config()`，部分字典改为覆盖合并 | `test_never_calls_the_api_synchronously` |
| B4 | **HIGH** | `utils.py` `apply_manual_corrections` | 同时传 `filters` 与 `or_filters`，Frappe 二者 AND → `status != Reviewed` 的 Manual 记录被静默丢弃 | 只用 `or_filters` | `test_manual_source_records_are_applied_even_when_not_reviewed` |
| B5 | **HIGH** | `utils.py` `fix_batch_terminology` | 对全部译文做无守卫 `str.replace`，把动词含义也改掉 → 线上数据已含 `Reporting Currency → 报表货币`、`can be reported → 报表漏洞` 等误译 | 38 条**英文原文守卫**规则 + 19 条精确修正；并修正词条库 66 条 | `test_terminology.py`（12 例）+ 数据 diff |
| B6 | **HIGH** | `missing_translation_log.json` | `source_text` 为 Text + `unique:1`，Frappe 对 Text 列不强制唯一 → 重复日志堆积 | 代码层对所有状态去重（不再只对 Open） | `test_logs_and_dedupes_across_statuses` |
| B7 | MED | `commands.py` `scan_missing` | 调用不存在的 `frappe.model.sync_file_to_doc`，异常被吞 → schema 未迁移时不生效 | 移除该无效调用 | 代码审查 |
| B8 | MED | `utils.py` boot hook | 每次 desk 启动解析所有 App 的 PO（上万词条）+ 读 16k CSV，且可能同步发 HTTP | 结果缓存（默认 6h）+ `scan_on_boot` 开关 + 只 `enqueue` 后台任务 + 每日 scheduler 兜底 | `test_scans_once_thanks_to_the_cache` |
| B9 | MED | `hooks.py` | `bench_commands` 不是 Frappe/bench 钩子（命令靠导入 `<app>.commands` 发现），属死配置 | 删除并加注释说明真实机制 | 框架源码 `bench_helper.get_app_commands` |
| B10 | MED | `utils.py` `_append_to_csv` | 只写 2 列 → 会丢弃 Frappe 的第 3 列 `context`；每次 Translation 保存都整文件重写 | 改用 `csvio`（保留 context、无变更不落盘、保留原 EOL） | `test_roundtrip_escapes_newlines_and_keeps_context` |
| B11 | MED | `utils.py` 扫描 | 依赖 `babel`，未安装时 `_scan_missing_translations()` 静默返回 `[]`（功能整体失效） | 新增零依赖 `po.py`（解析 + **就地**填充 msgstr，保留注释/引用/格式） | `test_po.py`（4 例） |
| B12 | LOW | `setup.py` | 命令提示是普通字符串，用户看到字面量 `bench --site {site} ...` | 改为正确输出，并补全新命令列表 | 代码审查 |
| B13 | LOW | `utils.py` boot hook | `frappe.local.lang or ...` 兜底是死代码；`frappe.local` 属性不存在时会抛错 | 用 `getattr(..., None)` 防御 | 代码审查 |
| B14 | LOW | `commands.py` `export` | 应用列表硬编码 `frappe, erpnext, hrms, payments, webshop`，漏 wiki/helpdesk/telephony | 改为遍历已安装 App | 代码审查 |

## 4. 词条库数据修正（66 条）

`python -m custom_translations.cli fix-csv` 的结果（CRLF 保持，仅 136 行变更，无整文件 diff）：

- 误译修复（旧全局替换的产物）：`报表货币 → 报告货币`（5 条）、`关于漏洞报表 → 关于漏洞报告`、
  `可以报表漏洞 → 可报告漏洞`、`报表错误 → 报告缺陷`、`准备报表 → 预生成报表`（对齐上游官方译法）等。
- 台湾用语 → 大陆规范：`预设 → 默认`、`讯息 → 消息`、`登入 → 登录`、`停用 → 禁用`、
  `专案 → 项目`、`使用者 → 用户`、`资料/档案 → 数据/文件`、`搜寻 → 搜索`、`载入 → 加载`、
  `开启 → 打开`、`资讯 → 信息`、`连结 → 链接` 等，共 60 条。

规则幂等性已测试：二次运行为 0 变更。


## 5. 「更精准、更智能」的翻译能力升级

针对「可能还要更精准智能化的翻译」，重写了 AI 管线（`translate.py`）：

| 维度 | 旧实现 | 现在 |
|------|--------|------|
| 术语表 | 只在 system prompt 里「建议」 | **按批次强制注入**本批次真正出现的术语映射 |
| 上下文 | 无 | 用**目标 App 自身最新官方译文**做翻译记忆，按 token 重合度选 few-shot 参考，风格与官方一致 |
| 输出校验 | 无 | 占位符 `{0}` / `%s` / `{{ }}`、HTML 标签、换行、英文回显、首尾空白逐条校验 |
| 失败处理 | 整批丢弃 | 单条隔离 → 带失败原因**修复重译** → 仍失败才丢弃并记录原因 |
| 术语后处理 | 全局 `str.replace`（会误伤） | 38 条英文原文守卫规则 |
| 可测性 | 无测试 | 13 个引擎测试（批次/重试/解析变体/校验/修复） |

实测（fake client）：`Journal Entry` 走术语表、`Cannot cancel {0}.` 被校验器拦下并自动修复为
`无法取消 {0}。`、`Reporting Currency` 被规则纠正为 `报告货币`。

## 6. 验证方式与证据

1. **真实数据回归**（本机，无 frappe）：
   - 用官方 `frappe/locale/zh.po`（6293 条）验证 PO 解析：6112 已译 / 180 未译，与官方一致；
     `fill_po_file` 就地写入只改动目标行，其余字节不变（含注释与引用）。
   - 用官方 `erpnext/translations/zh.csv`（12219 行）验证 CSV 解析与布局发现：
     旧代码在此返回 0，新代码正确识别为 `csv` 布局并读到 11848 条译文。
   - 对 16886 条词条跑术语审计：命中 66 条，逐条人工核对无假阳性，二次运行 0 变更。
2. **单元测试**：`python -m unittest discover -s custom_translations/tests -t .` → **65 passed**。
   其中核心逻辑用自建 `frappe` 桩（`tests/frappe_stub.py`）驱动，覆盖扫描、覆盖率、日志去重、
   boot 缓存与 enqueue、人工纠偏、术语修正。
3. **框架语义核对**：所有涉及 Frappe 行为的判断均对照 `frappe/frappe@version-15` 源码
   （`translate.py`、`gettext/translate.py`、`sessions.py`、`db_query.py`、`bench_helper.py`、
   `model/sync.py`、`database/database.py`）。

4. **真实上游端到端验证**：把官方 `develop` 分支的 `locale/zh.po` + `locale/main.pot`
   （frappe / erpnext / hrms / helpdesk）与本 App 的 16886 条词条库放进同一个仿真 bench，
   运行 `get_coverage_report()`（结果如下，扫描耗时 0.3 秒）：

   | app | 布局 | 可翻译字符串 | 官方已译 | 本 App 覆盖 | 仍缺失 |
   |-----|------|-------------|---------|------------|--------|
   | frappe | po+pot | 7992 | 5905 | 5887 | **1960** |
   | erpnext | po+pot | 11167 | 8079 | 8152 | **2984** |
   | hrms | po+pot | 2294 | 2101 | 2012 | **271** |
   | helpdesk | po+pot | 1622 | 730 | 366 | **880** |
   | payments | 无文件 | 0 | 0 | 0 | 0 |
   | **合计** | | **23075** | | | **6095** |

   说明：旧代码在同样环境下对 erpnext / hrms 只会返回 0（找不到 `locale/zh.po` 时的旧假设在
   develop 分支恰好成立、在 v15 分支完全不成立），也就是说这次修复让扫描在两条版本线上都可用。
   表中「仍缺失」即为后续 `custom-translations-scan` + `auto-translate` 的真实工作量。

## 7. 对独立审计结论的复核（含 1 处纠正）


| 审计结论 | 我的复核 |
|----------|---------|
| 76 个带空格 key 是「死键」，建议 trim | **否证**。逐字比对上游后：43 个在 ERPNext 官方 `zh.csv` 中**原样存在**（如 `" Address","地址"`），是真实 msgid；trim 会破坏匹配。已在 README 明确「切勿批量 trim」。 |
| `_append_to_csv` 用 CRLF 会破坏兼容 | **部分否证**。原文件本来就是 CRLF，Frappe 读取正常；真正的问题是「改写时把 CRLF 变成 LF 会造成 16k 行 diff」。现改为**保留原文件 EOL**。 |
| `export` 会破坏词条库 | **确认（HIGH）**，已按建议改为默认不动词条库。 |
| `bench_commands` 是死配置 | **确认**，已删除。 |
| 其余（B1/B3/B4/B6/B7/B8） | 全部确认并修复。 |

## 8. 未做 / 建议后续

- **未新增词条**：补齐 erpnext（2749 条）/ frappe（1835 条）等缺口需要真实站点 + API Key，
  本次只交付了「能正确找到缺口并高质量翻译」的能力。上线后建议：
  `custom-translations-coverage` → `custom-translations-scan` → `custom-translations-auto-translate`。
- **`translations/zh.imported.csv` 未纳入 `.gitignore`**：若执行导出会产生一个 16k 行的旁路文件，
  是否需要入库由维护者决定。
- 术语规则仍有主观空间（如 `Cancel → 取消` 同时用于「取消」与 docstatus 的「已取消」），
  后续可按 App 维度细分规则。
- 建议在 CI 中加一行：`python -m unittest discover -s custom_translations/tests -t .`
  与 `python -m custom_translations.cli audit-csv`，防止词条库被误改。

## 9. 本次改动文件

新增：`sources.py`、`po.py`、`csvio.py`、`validate.py`、`terminology.py`、`translate.py`、`cli.py`、
`tests/`（5 个文件）、`docs/app-translation-layouts.md`、`docs/code-audit.md`、`docs/verification.md`、
`pyproject.toml`。
重写：`utils.py`、`commands.py`、`hooks.py`、`setup.py`、`README.md`。
数据：`translations/zh.csv`（66 条修正）。
配置：`config.py`（新增 `scan_on_boot` / `scan_interval_seconds`）、`config.example.json`。
