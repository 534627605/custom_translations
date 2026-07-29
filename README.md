# Custom Translations

Frappe / ERPNext 简体中文翻译增强应用 —— 安装即用、不影响官方更新、支持 AI 自动补缺与人工纠偏。

## 为什么需要这个 App

Frappe / ERPNext 官方中文翻译存在以下问题：

- 大量词条未翻译（界面出现英文）
- 部分翻译为台湾用语（如「储存」「设定」「报告」），与大陆规范不一致
- 专业术语不准确（如「Journal Entry」译为「日记账凭证」而非「日记账分录」）
- 版本升级后翻译容易失效或被覆盖

本 App 通过独立加载一份高质量的简体中文翻译来解决以上问题，同时提供自动补缺和人工纠偏能力。

## 特性

- **安装即用**：内置 16000+ 条 ERP 专业翻译，无需任何配置即可生效
- **不修改官方文件**：翻译通过 App 的 `translations/zh.csv` 注入，Frappe 自动加载，官方更新不受影响
- **版本升级不丢失**：翻译独立存储，框架升级后翻译依然有效
- **专业 ERP 术语**：416 条精心维护的术语表，覆盖会计、库存、销售、采购、HR、制造、CRM、系统设置等领域，符合企业会计准则
- **批量术语修正**：一键将台湾用语批量转换为大陆规范（储存→保存、报告→报表、大师→主数据、设定→设置）
- **AI 自动补缺**：可选启用 AI API（NVIDIA / DeepSeek / OpenAI）自动翻译新增词条，不覆盖已有翻译
- **人工纠偏**：通过 `Missing Translation Log` doctype 审核、修改翻译，人工修改优先级最高

## 安装

```bash
# 1. 获取应用
bench get-app https://github.com/your-org/custom_translations.git

# 2. 安装到站点
bench --site your-site install-app custom_translations

# 3. 清除缓存（让翻译生效）
bench --site your-site clear-cache
```

安装后翻译立即生效，无需额外配置。刷新浏览器即可看到中文界面。

## 命令一览

| 命令 | 作用 | 是否需要 API |
|------|------|-------------|
| `custom-translations-stats` | 查看翻译统计和配置状态 | 否 |
| `custom-translations-config` | 查看当前配置（API key 脱敏显示） | 否 |
| `custom-translations-apply-glossary` | 应用 416 条专业 ERP 术语表（覆盖错误翻译） | 否 |
| `custom-translations-fix-terminology` | 批量修正台湾用语为大陆规范 | 否 |
| `custom-translations-scan` | 扫描各 App PO 文件中的空 msgstr 条目 | 否 |
| `custom-translations-auto-translate` | 自动翻译缺失词条（不覆盖已有翻译） | 是 |
| `custom-translations-apply-corrections` | 应用人工纠偏到 CSV | 否 |
| `custom-translations-sync` | 可选：同步翻译到官方 .po 文件 | 否 |

所有命令均通过 `bench --site your-site <command>` 调用。

## 推荐使用流程

### 场景一：日常使用（无需 API）

```bash
# 安装后即可用。如需修复常见翻译问题：
bench --site your-site custom-translations-apply-glossary
bench --site your-site custom-translations-fix-terminology
bench --site your-site clear-cache
```

### 场景二：版本升级后补缺（需配置 API）

```bash
# 1. 扫描新增的未翻译词条
bench --site your-site custom-translations-scan

# 2. 自动翻译（仅处理 CSV 中不存在的条目，不覆盖已有翻译）
bench --site your-site custom-translations-auto-translate --limit 100

# 3. 修正台湾用语
bench --site your-site custom-translations-fix-terminology

# 4. 清缓存生效
bench --site your-site clear-cache
```

### 场景三：人工审核纠偏

```bash
# 1. 在 Frappe 后台打开「Missing Translation Log」列表
#    （已翻译条目排在顶部，便于审核）

# 2. 修改 translated_text 字段，将状态改为「Reviewed」

# 3. 应用人工修改到 CSV（覆盖自动翻译）
bench --site your-site custom-translations-apply-corrections

# 4. 清缓存生效
bench --site your-site clear-cache
```

## 可选：启用 AI 自动翻译

当 Frappe / ERPNext 发布新版本引入未翻译词条时，可启用 AI 自动补缺。

### 配置方式（三选一）

**方式一：环境变量（推荐，最安全）**

```bash
export CUSTOM_TRANSLATIONS_API_KEY="nvapi-your-key-here"
export CUSTOM_TRANSLATIONS_PROVIDER="nvidia"
export CUSTOM_TRANSLATIONS_AUTO_TRANSLATE=1
```

**方式二：配置文件**

```bash
cp apps/custom_translations/config.example.json apps/custom_translations/config.json
# 编辑 config.json 填入 API key（此文件已在 .gitignore 中，不会被提交）
```

**方式三：site_config.json**

```json
"custom_translations_settings": {
    "provider": "nvidia",
    "api_key": "your-api-key-here",
    "auto_translate": true
}
```

### 支持的 API 提供商

| 提供商 | provider | 模型 | 费用 | 获取 Key |
|--------|----------|------|------|----------|
| NVIDIA NIM | `nvidia` | deepseek-ai/deepseek-v4-flash | 免费额度 | https://build.nvidia.com/ |
| DeepSeek | `deepseek` | deepseek-chat | 付费 | https://platform.deepseek.com/ |
| OpenAI | `openai` | gpt-4o-mini | 付费 | https://platform.openai.com/ |

**API Key 安全说明**：
- 环境变量方式不会写入磁盘，最安全
- `config.json` 已在 `.gitignore` 中，不会被提交
- 切勿将 API Key 提交到版本控制

## 翻译优先级

加载顺序（高 → 低）：

1. **数据库 Translation doctype** —— 运行时最高优先级
2. **本 App 的 `translations/zh.csv`** —— Frappe 自动加载，覆盖官方翻译
3. **官方 `.mo` 文件** —— 最后加载

写入优先级（`zh.csv` 内部）：

1. **人工纠偏**（Reviewed 状态）—— `overwrite=True`，覆盖自动翻译
2. **专业术语表**（`professional_glossary.py`）—— 覆盖错误翻译和本地化包
3. **批量术语修正**（`fix-terminology`）—— 修正句子级台湾用语
4. **自动翻译**（AI API）—— `overwrite=False`，仅填充缺失条目，不覆盖已有翻译

**核心原则**：自动翻译永不覆盖已有翻译，人工修改优先级最高。

## 专业术语表

`custom_translations/professional_glossary.py` 维护一份精心校对的 ERP 术语表，当前包含 416 条，覆盖以下领域：

| 领域 | 示例术语 | 示例翻译 |
|------|---------|---------|
| 会计 | Journal Entry, Stock Ledger Entry, Bank Reconciliation | 日记账分录、库存分类账分录、银行对账 |
| 库存 | Stock Entry, Serial No, Valuation Rate | 库存移动单、序列号、计价成本 |
| 销售采购 | Quotation, Delivery Note, Purchase Receipt | 报价单、送货单、采购收货单 |
| HR | Leave Application, Payroll Entry, Salary Slip | 请假申请、工资单分录、工资条 |
| 制造 | Work Order, BOM, Operation, Workstation | 工单、物料清单、工序、工作站 |
| CRM | Lead, Opportunity, Campaign | 线索、商机、营销活动 |
| 系统设置 | Custom Field, Workflow, Print Format | 自定义字段、工作流、打印格式 |
| UI 核心 | Home, Save, Report, Settings | 首页、保存、报表、设置 |

扩展方式：编辑 `professional_glossary.py` 中的 `PROFESSIONAL_GLOSSARY` 字典，然后运行：

```bash
bench --site your-site custom-translations-apply-glossary
bench --site your-site clear-cache
```

## 项目结构

```
custom_translations/
├── custom_translations/
│   ├── translations/zh.csv              # 16000+ 条翻译（核心，Frappe 自动加载）
│   ├── professional_glossary.py         # 416 条专业 ERP 术语表
│   ├── config.py                        # 配置管理（环境变量/文件/site_config）
│   ├── utils.py                         # 核心逻辑：扫描、翻译、纠偏、批量修正
│   ├── commands.py                      # bench 命令定义
│   ├── setup.py                         # 安装后引导提示
│   ├── hooks.py                         # Frappe 钩子注册
│   └── custom_translations/doctype/
│       └── missing_translation_log/
│           ├── missing_translation_log.json   # 缺失翻译日志 doctype
│           └── missing_translation_log.py
├── config.example.json                  # 配置文件模板
├── .gitignore                           # 保护 config.json 不被提交
├── setup.py                             # pip 安装入口
├── pyproject.toml                       # Python 包元数据
└── README.md
```

## 技术原理

**为什么不影响官方更新？**

- 翻译存储在本 App 的 `translations/zh.csv`
- Frappe 框架启动时自动遍历所有已安装 App 的 `translations/{lang}.csv` 并合并
- 后加载的 App 翻译优先级更高，本 App 的翻译会覆盖官方翻译
- 完全不修改 `apps/frappe/`、`apps/erpnext/` 等官方目录的任何文件

**为什么翻译不丢失？**

- `zh.csv` 是本 App 自有的翻译文件，随 App 一起存在
- 官方 App 升级只会更新官方的 `.po` / `.mo` 文件，不会触碰本 App
- 即使运行 `bench update`，本 App 的翻译也原样保留

## 技术要求

- Frappe Framework >= 14
- Python >= 3.8
- 可选：`zhconv`（繁简转换）、`babel`（PO 文件解析）

## 许可证

MIT License
