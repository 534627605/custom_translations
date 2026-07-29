# Custom Translations

Frappe/ERPNext 简体中文翻译增强应用 - 安装即用，不影响官方更新。

## 特性

- **安装即用**：内置 16000+ 条高质量 ERP 专业翻译，无需任何配置
- **不修改官方文件**：翻译通过 app 的 `translations/zh.csv` 注入，Frappe 自动加载，官方更新不受影响
- **版本升级不丢失**：翻译独立存储，框架升级后翻译依然有效
- **自动翻译补缺**：可选启用 AI API（NVIDIA/DeepSeek/OpenAI）自动翻译新增词条
- **人工纠偏**：支持在 Missing Translation Log 中审核、修改翻译，人工修改优先级最高
- **ERP 专业术语**：针对会计、库存、销售、采购、HR、制造、CRM 领域优化翻译质量

## 安装

```bash
# 1. 获取应用
bench get-app https://github.com/your-org/custom_translations.git

# 2. 安装到站点
bench --site your-site install-app custom_translations

# 3. 清除缓存（让翻译生效）
bench --site your-site clear-cache
```

安装后翻译立即生效，无需额外配置。

## 可选：启用自动翻译

当 Frappe/ERPNext 发布新版本时，可能引入新的未翻译词条。启用自动翻译可自动补缺：

### 方式一：环境变量（推荐，最安全）

```bash
# 在 ~/.bashrc 或 systemd service 中设置
export CUSTOM_TRANSLATIONS_API_KEY="nvapi-your-key-here"
export CUSTOM_TRANSLATIONS_PROVIDER="nvidia"
export CUSTOM_TRANSLATIONS_AUTO_TRANSLATE=1
```

### 方式二：配置文件

```bash
# 复制示例配置
cp apps/custom_translations/config.example.json apps/custom_translations/config.json

# 编辑 config.json，填入你的 API key
vi apps/custom_translations/config.json
```

### 方式三：site_config.json

```json
"custom_translations_settings": {
    "provider": "nvidia",
    "api_key": "your-api-key-here",
    "auto_translate": true
}
```

### API 提供商

| 提供商 | provider | 模型 | 费用 | 获取 Key |
|--------|----------|------|------|----------|
| NVIDIA NIM | `nvidia` | deepseek-ai/deepseek-v4-flash | 免费额度 | https://build.nvidia.com/ |
| DeepSeek | `deepseek` | deepseek-chat | 付费 | https://platform.deepseek.com/ |
| OpenAI | `openai` | gpt-4o-mini | 付费 | https://platform.openai.com/ |

**API Key 安全**：
- 环境变量方式不会写入磁盘，最安全
- `config.json` 已在 `.gitignore` 中，不会被提交
- 不要将 API Key 提交到版本控制

## 使用命令

```bash
# 查看翻译统计和配置状态
bench --site your-site custom-translations-stats

# 查看当前配置（API key 会脱敏显示）
bench --site your-site custom-translations-config

# 扫描缺失的翻译
bench --site your-site custom-translations-scan

# 自动翻译缺失词条（需先配置 API）
bench --site your-site custom-translations-auto-translate --limit 100

# 应用人工纠偏（在 Missing Translation Log 中审核后运行）
bench --site your-site custom-translations-apply-corrections

# 可选：同步翻译到官方 .po 文件（会修改官方文件，非必要）
bench --site your-site custom-translations-sync
```

## 人工纠偏流程

1. 运行 `custom-translations-scan` 扫描缺失翻译
2. 运行 `custom-translations-auto-translate` 自动翻译
3. 在 Frappe 后台打开 **Missing Translation Log** 列表
4. 审核 `translated_text` 字段，修改不满意的翻译
5. 将状态改为 **Reviewed**（已审核）
6. 运行 `custom-translations-apply-corrections` 将人工修改保存到 CSV（会覆盖自动翻译）

**翻译优先级**（高 → 低）：
1. 人工纠偏（Reviewed 状态）→ 覆盖写入 CSV
2. 数据库 Translation doctype 记录 → 运行时最高优先级
3. 本 app 的 `translations/zh.csv` → 自动加载
4. 官方 `.mo` 文件 → 最后加载

**不覆盖原则**：自动翻译不会覆盖 CSV 中已有的翻译，确保人工修改和之前的有效翻译不被覆盖。

## 架构说明

```
custom_translations/
├── custom_translations/
│   ├── translations/zh.csv     # 16000+ 条翻译（核心，Frappe 自动加载）
│   ├── config.py               # 配置管理（环境变量/文件/site_config）
│   ├── utils.py                # 核心逻辑：扫描、翻译、纠偏
│   ├── commands.py             # bench 命令
│   ├── setup.py                # 安装后引导
│   ├── hooks.py                # Frappe 钩子注册
│   └── custom_translations/doctype/missing_translation_log/
│       └── missing_translation_log.json  # 缺失翻译日志 doctype
├── config.example.json         # 配置文件模板
├── .gitignore                  # 保护 config.json 不被提交
└── README.md
```

**为什么不影响官方更新？**
- 翻译存储在本 app 的 `translations/zh.csv`
- Frappe 框架启动时自动遍历所有已安装 app 的 `translations/{lang}.csv` 并合并
- 后加载的 app 翻译优先级更高，本 app 的翻译会覆盖官方翻译
- 完全不修改 `apps/frappe/`、`apps/erpnext/` 等官方目录的任何文件

## 技术要求

- Frappe Framework >= 14
- Python >= 3.8
- 可选：`zhconv`（繁简转换）、`babel`（PO 文件解析）

## 许可证

MIT License
