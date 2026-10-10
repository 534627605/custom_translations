# Custom Translations

Frappe / ERPNext 生态的**简体中文翻译增强应用** —— 安装即用、不改官方文件、可扫描缺失词条、可 AI 补缺、可人工纠偏。

适配的 App：`frappe`、`erpnext`、`hrms`、`payments`、`wiki`、`helpdesk`、`webshop`、`telephony`。

## 为什么需要这个 App

Frappe / ERPNext 官方中文翻译存在以下问题：

- 大量词条未翻译（界面出现英文）。官方文件本身就存在缺口，例如 frappe 中文 PO 有 **1835/7798** 条未翻译、erpnext 有 **2749/10831** 条未翻译、helpdesk 有 **649/1379** 条未翻译。
- 部分翻译为台湾用语（「储存」「设定」「预设」「使用者」「汇入」），与大陆规范不一致。
- 专业术语不准确（如 `Journal Entry` 被译为「日记账凭证」而非「日记账分录」）。
- **各 App 的翻译文件位置不统一**，v14/v15 与 v16/develop 之间还会变化，导致「扫描缺失词条」类工具直接失效（见下节）。
- 版本升级后翻译容易被覆盖或失效。

本 App 用一份独立、可维护、可校验的简体中文词条库解决以上问题，并同时提供自动补缺与人工纠偏能力。

## 各 App 的翻译文件布局（本 App 会自动识别）

这是本 App 与其它同类工具最大的区别：**不假设任何固定路径**。

| App | v14 | v15（15.122.0，仍在发版） | v16（16.51.0，已定版） | v17 开发线（17.0.0-dev） | 官方中文缺口 |
|-----|-----|---------------------------|------------------------|---------------------------|-------------|
| frappe | `translations/zh.csv` | `locale/zh.po` **＋** `translations/zh.csv`（双轨） | `locale/zh.po` + `locale/main.pot` | 同 v16 | 1835 / 7798 |
| erpnext | `translations/zh.csv` | `translations/zh.csv`（**无 locale 目录**） | `locale/zh.po` + `main.pot` | 同 v16 | 2749 / 10831 |
| hrms | `translations/zh.csv` | `translations/zh.csv`（**无 locale 目录**） | `locale/zh.po` + `main.pot` | 同 v16 | 151 / 2252 |
| helpdesk | — | — | `locale/zh.po` | 同 v16 | 649 / 1379 |
| payments / webshop / telephony / wiki | 无 | 无 | 无 | **无** | 由本 App 的词条库覆盖 |

> 三条版本线（v15 / v16 / v17）**同时存在且都在发版**，而同一 App 在不同线上用的翻译文件格式并不相同，
> 这正是本 App 必须做多布局探测的原因。v17 仍支持加载 `<app>/translations/<lang>.csv`
> （`frappe.translate.get_translations_from_apps` 未变），所以本 App 的 CSV 覆盖策略在 v17 上依然有效。

扫描时会依次探测 `<app>/translations/`、`<app>/locale/`、`<app>/translations/locale/`（App 模块目录与源码根目录都探测），并识别 `zh.po` / `zh_CN.po` / `zh_Hans.po` / `zh.csv` / `main.pot` 等文件名。
对于完全没有 PO/POT 的 App（payments / webshop / telephony / wiki），会退化为**源码扫描**：
解析 App 自身的 `.py/.js/.html/.vue` 里的翻译调用 —— 关键词与 frappe v17 官方提取器保持一致
（`_` / `__` / `_lt` / `N_` / `gettext` / `ngettext` / `pgettext` / `npgettext` 等，含三引号与 JS 反引号模板串），
并按 v17 的做法额外解析 DocType / Workspace / Report 的 JSON（Select 选项会排除
`naming_series`、`number_format`、`icon` 等不可翻译项）。

## 核心能力

- **安装即用**：内置 **16886** 条简体中文词条，无需任何配置即可生效。
- **不修改官方文件**：翻译通过本 App 的 `translations/zh.csv` 注入，Frappe 自动加载并合并；官方目录零改动。
- **版本升级不丢失**：词条独立存储，`bench update` 后依然有效。
- **多布局覆盖扫描**：正确识别上表所有布局，输出每个 App 的「可翻译字符串 / 官方已译 / 本 App 覆盖 / 仍缺失」。
- **专业 ERP 术语表**：416 条人工校对术语，覆盖会计、库存、销售、采购、HR、制造、CRM、系统设置，符合企业会计准则。
- **上下文感知的术语修正**：38 条规则全部由**英文原文做守卫**，只在该词确实是该含义时才替换，不会像旧的全局字符串替换那样误伤（例如把 `Reporting Currency` 错改成「报表货币」、把 `... can be reported` 错改成「报表漏洞」）。
- **AI 自动补缺（更精准）**：术语表强制注入 + 用目标 App **自身最新官方译文**作为翻译记忆（few-shot）→ 风格与官方一致；输出经校验器检查占位符 / HTML / 换行，不通过会自动发起「修复重译」。
- **人工纠偏**：`Missing Translation Log` doctype 审核修改，人工修改优先级最高。
- **离线可维护**：`python -m custom_translations.cli` 不需要 bench 即可审计 / 修正词条库（可进 CI）。

## 安装

```bash
# 1. 获取应用
bench get-app https://github.com/534627605/custom_translations.git

# 2. 安装到站点
bench --site your-site install-app custom_translations

# 3. 清缓存（让翻译生效）
bench --site your-site clear-cache
```

安装后翻译立即生效，无需额外配置。刷新浏览器即可看到中文界面。

> 提示：Frappe 按 `apps.txt` 顺序合并各 App 的 `translations/<lang>.csv`，**后加载的覆盖先加载的**。
> 若希望本 App 的词条绝对优先，请在其它业务 App 之后再安装本 App（或之后重装一次）。

## 命令一览

所有命令通过 `bench --site your-site <command>` 调用。

| 命令 | 作用 | 需要 API Key |
|------|------|-------------|
| `custom-translations-stats` | 词条库与配置概览 | 否 |
| `custom-translations-config` | 查看生效配置（API Key 脱敏） | 否 |
| `custom-translations-coverage` | **新增**：逐 App 中文覆盖率与布局 | 否 |
| `custom-translations-scan` | 扫描缺失词条并写入日志 | 否 |
| `custom-translations-apply-glossary` | 应用 416 条专业术语表 | 否 |
| `custom-translations-fix-terminology` | 术语修正（`--dry-run` 可先预览） | 否 |
| `custom-translations-apply-corrections` | 应用人工纠偏到词条库 | 否 |
| `custom-translations-export` | 导出各 App 官方中文（**默认不动词条库**） | 否 |
| `custom-translations-auto-translate` | AI 自动翻译缺失词条（不覆盖已有） | 是 |
| `custom-translations-sync` | 可选：把译文写回官方 `.po` 并编译 `.mo` | 否 |

离线（无需 bench / 数据库）：

```bash
python -m custom_translations.cli audit-csv             # 审计词条库结构
python -m custom_translations.cli fix-csv --dry-run     # 预览术语修正
python -m custom_translations.cli fix-csv               # 应用术语修正
```

## 推荐使用流程

### 场景一：日常使用（无需 API）

```bash
bench --site your-site custom-translations-coverage          # 看缺口在哪
bench --site your-site custom-translations-apply-glossary    # 覆盖术语
bench --site your-site custom-translations-fix-terminology   # 修正台湾用语
bench --site your-site clear-cache
```

### 场景二：版本升级后补缺（需 API Key）

```bash
# 1. 扫描新增的未翻译词条（erpnext/hrms 的 csv 布局也会被正确扫描）
bench --site your-site custom-translations-scan

# 2. 自动翻译（只处理缺失条目，绝不覆盖已有译文）
bench --site your-site custom-translations-auto-translate --limit 100

# 3. 术语修正 + 清缓存
bench --site your-site custom-translations-fix-terminology
bench --site your-site clear-cache
```

### 场景三：人工审核纠偏

```bash
# 1. 后台打开「Missing Translation Log」列表
# 2. 修改 translated_text，并把 status 改为「Reviewed」
#    （或把 translation_source 设为「Manual」）
# 3. 应用人工修改（覆盖自动翻译）
bench --site your-site custom-translations-apply-corrections
bench --site your-site clear-cache
```

## AI 自动翻译配置（三选一）

**方式一：环境变量（推荐，最安全）**

```bash
export CUSTOM_TRANSLATIONS_API_KEY="nvapi-your-key-here"
export CUSTOM_TRANSLATIONS_PROVIDER="nvidia"
export CUSTOM_TRANSLATIONS_AUTO_TRANSLATE=1
# 可选：关闭开机扫描 / 调整扫描缓存时长（秒）
export CUSTOM_TRANSLATIONS_SCAN_ON_BOOT=0
export CUSTOM_TRANSLATIONS_SCAN_INTERVAL=86400
```

**方式二：配置文件**

```bash
cp apps/custom_translations/config.example.json apps/custom_translations/config.json
# 编辑 config.json 填入 API Key（该文件已在 .gitignore 中，不会被提交）
```

**方式三：site_config.json**

```json
"custom_translations_settings": {
    "provider": "nvidia",
    "api_key": "your-api-key-here",
    "auto_translate": true
}
```

优先级：**环境变量 > `config.json` > `site_config.json` > 默认值**。

### 支持的 Provider

| Provider | 值 | 默认模型 | 费用 |
|----------|-----|---------|------|
| NVIDIA NIM | `nvidia` | `deepseek-ai/deepseek-v4-flash` | 免费额度 |
| DeepSeek | `deepseek` | `deepseek-chat` | 付费 |
| OpenAI | `openai` | `gpt-4o-mini` | 付费 |

任何 OpenAI 兼容的 `/chat/completions` 端点都可以使用，只需自定义 `api_endpoint` 与 `model`。

### 配置项

| 键 | 默认 | 说明 |
|----|------|------|
| `provider` | `nvidia` | 提供方 |
| `api_key` | 空 | API Key |
| `api_endpoint` | 按 provider | 端点 |
| `model` | 按 provider | 模型 |
| `batch_size` | 10 | 每次请求翻译多少条 |
| `max_length` | 500 | 超过该长度的条目跳过（代码/HTML 大块） |
| `auto_translate` | false | 是否允许自动补缺 |
| `scan_on_boot` | true | 是否在 desk 启动时扫描缺失词条（结果有缓存） |
| `scan_interval_seconds` | 21600 | 扫描结果缓存时长（6 小时） |

**API Key 安全**：环境变量方式不落盘；`config.json` 已在 `.gitignore`；切勿把 Key 提交到版本库。

## 智能翻译管线（为什么更精准）

```
缺失词条
  │
  ├─ 1. 术语表强制注入   只注入本批次真正出现的术语，并要求「必须照此翻译」
  ├─ 2. 翻译记忆 few-shot 取目标 App 自身最新官方译文中 token 重合度最高的若干条作为参考
  ├─ 3. 模型翻译         OpenAI 兼容端点，批处理 + 3 次指数退避重试
  ├─ 4. 质量校验         占位符 {0}/%s/{{ }}、HTML 标签、换行、英文回显、空白
  ├─ 5. 修复重译         校验不通过的单条重发（带上失败原因），仍失败则丢弃并记入 rejected
  ├─ 6. 术语规则后处理   上下文守卫规则覆盖模型用词漂移（报告/报表、保存/存储…）
  └─ 7. 落库             overwrite=False，绝不覆盖任何已有译文
```

对比旧实现：

| 维度 | 旧实现 | 现在 |
|------|--------|------|
| 术语表 | 只写在 system prompt 里「建议」 | 按批次强制注入映射 |
| 上下文 | 无 | 目标 App 官方译文作翻译记忆 |
| 输出校验 | 无（`报表货币` 这类错误直接入库） | 占位符/HTML/换行校验 + 修复重译 |
| 失败处理 | 整批丢弃 | 单条隔离、可修复、逐条报告原因 |
| 术语修正 | 全局 `str.replace`（会误伤） | 38 条规则，全部由英文原文守卫 |

## 翻译优先级

加载顺序（高 → 低）：

1. **数据库 `Translation` doctype** —— 运行时最高优先级。
2. **本 App 的 `translations/zh.csv`** —— Frappe 自动加载，覆盖官方。
3. **各 App 官方翻译** —— 注意官方 `.mo`（编译产物）会覆盖同一 App 的 `.csv`；本 App 的词条因为后加载，仍然最终生效。

写入优先级（`zh.csv` 内部）：

1. **人工纠偏**（Reviewed / Manual）—— `overwrite=True`，覆盖一切。
2. **专业术语表** —— `overwrite=True`。
3. **术语修正规则** —— 只修正既有译文的用词。
4. **AI 自动翻译** —— `overwrite=False`，只填空缺，绝不覆盖。

**核心原则：自动翻译永不覆盖已有译文，人工修改优先级最高。**

## 术语修正规则（举例）

规则全部带**英文原文守卫**，因此不会误伤：

| 规则 | 生效条件（英文原文） | 效果 |
|------|---------------------|------|
| 储存 → 保存 | `save/saved/saving` | 正确 |
| 保存 → 存储 | `store/stores/storage` | 正确（旧实现会把两者混为一谈） |
| 报告 → 报表 | `Report`（名词，且后面不接宾语） | 正确 |
| 报表 → 报告 | `reporting` / `can be reported` / `report bug` | 正确（旧实现会误改成「报表」） |
| 设定 → 设置 | `Setting(s)` / `Setup` | 正确 |
| 使用者 → 用户 | `User(s)` | 正确 |
| 预设 → 默认 | `Default(s)` | 正确 |
| 资料 → 数据 | `Data` | 正确 |
| 档案 → 文件 | `File(s)` | 正确 |
| 登入/登出 → 登录/退出登录 | `login` / `logout` | 正确 |
| 汇入/汇出 → 导入/导出 | `import` / `export` | 正确 |
| 搜寻 → 搜索 | `search` | 正确 |
| 载入 → 加载 | `load` | 正确 |
| 开启 → 打开 | `open` | 正确 |
| 停用 → 禁用 | `disable` | 正确 |
| 资讯 → 信息 | `information/info` | 正确 |
| 张贴 → 过账 | `post` | 正确 |
| 硬碟/记忆体/萤幕/网路/即时 | `disk/memory/screen/network/real-time` | 正确 |

另有 19 条「精确修正」用于规则无法覆盖的长句（含上游官方译法对齐，如 `Prepared Report → 预生成报表`）。

## 项目结构

```
custom_translations/
├── custom_translations/
│   ├── translations/zh.csv              # 16886 条词条（核心，Frappe 自动加载）
│   ├── sources.py                       # 多布局翻译文件发现 + 源码字符串提取
│   ├── po.py                            # 零依赖 PO 解析 / 就地填充（保留注释与格式）
│   ├── csvio.py                         # Frappe 兼容翻译 CSV 读写（保留第 3 列 context）
│   ├── validate.py                      # 译文质量校验（占位符/HTML/换行/英文回显）
│   ├── terminology.py                   # 上下文守卫的术语规则 + 精确修正
│   ├── translate.py                     # AI 引擎：术语强制 + 翻译记忆 + 校验修复
│   ├── utils.py                         # 编排：扫描、覆盖率、日志、纠偏、boot/scheduler
│   ├── commands.py                      # 10 个 bench 命令
│   ├── cli.py                           # 离线维护 CLI（无需 bench）
│   ├── config.py                        # 配置（环境变量/config.json/site_config）
│   ├── professional_glossary.py         # 416 条专业术语表
│   ├── setup.py                         # 安装后引导提示
│   ├── hooks.py                         # Frappe 钩子（bootinfo / doc_events / 每日任务）
│   └── custom_translations/doctype/
│       └── missing_translation_log/     # 缺失翻译日志 doctype
│   └── tests/                           # 65 个单元测试（标准库 unittest）
├── docs/                                # 布局取证与代码审计报告
├── config.example.json
├── pyproject.toml
└── setup.py
```

## 技术原理

**为什么不影响官方更新？**

- 词条保存在本 App 的 `translations/zh.csv`。
- Frappe 启动时遍历所有已安装 App 的 `translations/<lang>.csv` 并合并（`frappe.translate.get_translations_from_apps`），本 App 的词条覆盖官方。
- 完全不修改 `apps/frappe/`、`apps/erpnext/` 等官方目录的任何文件。

**为什么翻译不丢失？**

- `zh.csv` 是本 App 自有文件，随 App 存在；官方升级只更新官方文件。
- `bench update` 后本 App 词条原样保留。

**扫描为什么不再拖慢启动？**

- 旧实现每次 desk 启动都要解析所有 App 的 `.po`（上万个词条）+ 读 16886 行 CSV，并且可能同步发起 HTTP 请求。
- 现在：扫描结果缓存（默认 6 小时，可用 `scan_interval_seconds` 调整），且**绝不在 boot 中同步调用 API** —— 需要自动翻译时改为 `frappe.enqueue` 后台任务。
- 另外提供每日 scheduler 任务作为兜底（适合关闭开机扫描的站点）。

## 开发与测试

```bash
# 全部单元测试（标准库 unittest，无需 bench / 数据库 / 网络）
python -m unittest discover -s custom_translations/tests -t .

# 词条库审计
python -m custom_translations.cli audit-csv
```

测试覆盖：PO 解析与就地写入、CSV 往返与 EOL 保持、多布局发现、源码字符串提取、译文校验、术语规则（含误伤回归用例）、AI 引擎（批次/重试/校验/修复）、以及用 `frappe` 桩驱动的核心逻辑（扫描、日志去重、覆盖率、boot 缓存、人工纠偏）。

## 已知限制与注意事项

- `payments`、`webshop`、`telephony`、`wiki` 官方**没有任何中文翻译文件**，其界面中文只能来自本 App 的词条库；若界面仍显示英文，需要新增词条（可用 `custom-translations-scan` + `auto-translate` 补）。
- 官方 `.mo` 编译产物在加载顺序上**晚于**同一 App 的 `.csv`；`custom-translations-sync` 只影响官方 `.po`，是可选优化，不执行也完全不影响翻译生效。
- `Missing Translation Log.source_text` 是 Text 字段，Frappe 对 Text 列**不会真正强制 `unique`**；因此去重是在代码层完成的（对所有状态去重，而非仅 Open）。
- 词条库中存在 87 个带首尾空格的 key。这些**不是脏数据**：其中 43 个在 ERPNext 官方 `zh.csv` 中逐字存在（属真实 msgid），因此切勿批量 trim。
- 本 App 的 `zh.csv` 与官方译文存在风格差异：12866 个重叠 key 中，5571 个与官方完全一致、7295 个不同，多数差异只是中文与拉丁字母/数字之间的空格排版。如需完全跟随官方，可先 `custom-translations-export` 导出后比对。
- `custom-translations-export` 默认**不修改**词条库（输出到 `translations/zh.imported.csv`）；只有显式加 `--merge` 才会写入，且默认不覆盖已有译文。

## 许可证

MIT License

