"""
Context aware terminology correction (mainland China standard).

The original implementation applied blind substring replacement over every
translation value::

    for wrong, correct, _desc in BATCH_TERM_REPLACEMENTS:
        new_value = new_value.replace(wrong, correct)

That is how the shipped ``zh.csv`` ended up containing
``Reporting Currency -> 报表货币`` (should be 报告货币) and
``... where vulnerabilities can be reported -> 可以报表漏洞的网站``.
"报告" is *Report* the noun in some sentences and *report* the verb in others;
a blind ``str.replace`` cannot tell them apart.

Here every rule is **guarded by the English source string**, so a rule only
fires when the source actually means what the rule assumes. Rules are also
idempotent: applying them twice changes nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

__all__ = [
    "TermRule",
    "TERM_RULES",
    "KNOWN_FIXES",
    "fix_translation",
    "fix_translations",
    "audit_translations",
]


@dataclass(frozen=True)
class TermRule:
    """Replace ``wrong`` with ``right`` when the English source matches."""

    wrong: str
    right: str
    note: str
    #: regex the *source* (English msgid) must match; None = always apply
    source_pattern: Optional[str] = None
    #: regex the *target* must match (defaults to containing ``wrong``)
    target_pattern: Optional[str] = None

    def applies(self, source: str, target: str) -> bool:
        if self.wrong not in target:
            return False
        if self.target_pattern and not re.search(self.target_pattern, target):
            return False
        if self.source_pattern is not None:
            if not re.search(self.source_pattern, source, re.IGNORECASE):
                return False
        return True


#: "report" used as a verb, e.g. "reporting", "can be reported", "report bug"
_VERB_REPORT = (
    r"\breport(?:ing|ed|s)?\b\s*(?:a|an|the|it|this|issue|bug|error|problem|these|them)\b"
    r"|can be reported|are reported|is reported|be reported"
)

#: "Report" used as a noun, i.e. not followed by an object pronoun
_NOUN_REPORT = (
    r"\breports?\b(?!\s*(?:a|an|the|it|this|issue|bug|error|problem|these|them)\b)"
)

# --------------------------------------------------------------------------- #
# Rules - every rule is guarded by the English source
# --------------------------------------------------------------------------- #

TERM_RULES: Tuple[TermRule, ...] = (
    # ---- Save / Store (mutually exclusive by source guard) ----
    TermRule("储存", "保存", "Save: 储存→保存", source_pattern=r"\bsav(?:e|ed|es|ing)\b"),
    TermRule(
        "保存",
        "存储",
        "Store: 保存→存储",
        source_pattern=r"\b(?:store|stores|stored|storing|storage)\b",
    ),
    # ---- Report the noun vs report the verb ----
    TermRule(
        "报告",
        "报表",
        "Report(noun): 报告→报表",
        source_pattern=_NOUN_REPORT,
        target_pattern=r"报告(?!货币|期)",
    ),
    TermRule("报表", "报告", "report(verb): 报表→报告", source_pattern=_VERB_REPORT),
    TermRule(
        "报表货币",
        "报告货币",
        "Reporting Currency: 报表货币→报告货币",
        source_pattern=r"reporting currency",
    ),
    # ---- Masters / Settings ----
    TermRule("大师", "主数据", "Masters: 大师→主数据", source_pattern=r"\bmasters?\b"),
    TermRule(
        "设定",
        "设置",
        "Settings: 设定→设置",
        source_pattern=r"\b(?:settings?|set up|setup)\b",
    ),
    # ---- Common Taiwan -> mainland vocabulary (all source guarded) ----
    TermRule("使用者", "用户", "User: 使用者→用户", source_pattern=r"\busers?\b"),
    TermRule("预设", "默认", "Default: 预设→默认", source_pattern=r"\bdefaults?\b"),
    TermRule("资料", "数据", "Data: 资料→数据", source_pattern=r"\bdata\b"),
    TermRule("档案", "文件", "File: 档案→文件", source_pattern=r"\bfiles?\b"),
    TermRule("专案", "项目", "Project: 专案→项目", source_pattern=r"\bprojects?\b"),
    TermRule("连结", "链接", "Link: 连结→链接", source_pattern=r"\blinks?\b"),
    TermRule("搜寻", "搜索", "Search: 搜寻→搜索", source_pattern=r"\bsearch(?:ing)?\b"),
    TermRule("载入", "加载", "Load: 载入→加载", source_pattern=r"\bload(?:ing|ed)?\b"),
    TermRule("开启", "打开", "Open: 开启→打开", source_pattern=r"\bopen(?:ing|ed)?\b"),
    TermRule("登入", "登录", "Login: 登入→登录", source_pattern=r"\b(?:log ?in|sign ?in|login)\b"),
    TermRule(
        "登出",
        "退出登录",
        "Logout: 登出→退出登录",
        source_pattern=r"\b(?:log ?out|sign ?out|logout)\b",
    ),
    TermRule("汇入", "导入", "Import: 汇入→导入", source_pattern=r"\bimport(?:ing|ed)?\b"),
    TermRule("汇出", "导出", "Export: 汇出→导出", source_pattern=r"\bexport(?:ing|ed)?\b"),
    TermRule("检视", "查看", "View: 检视→查看", source_pattern=r"\bview(?:ing|ed)?\b"),
    TermRule("讯息", "消息", "Message: 讯息→消息", source_pattern=r"\bmessages?\b"),
    TermRule("资讯", "信息", "Information: 资讯→信息", source_pattern=r"\b(?:information|info)\b"),
    TermRule("网路", "网络", "Network: 网路→网络", source_pattern=r"\bnetwork\b"),
    TermRule("计画", "计划", "Plan: 计画→计划", source_pattern=r"\bplans?\b"),
    TermRule("元件", "组件", "Component: 元件→组件", source_pattern=r"\bcomponents?\b"),
    TermRule("群组", "组", "Group: 群组→组", source_pattern=r"\bgroups?\b"),
    TermRule("身分", "身份", "Identity: 身分→身份", source_pattern=r"\bidentit(?:y|ies)\b"),
    TermRule("停用", "禁用", "Disable: 停用→禁用", source_pattern=r"\bdisable[ds]?\b"),
    TermRule("选取", "选择", "Select: 选取→选择", source_pattern=r"\bselect(?:ing|ed)?\b"),
    TermRule("硬碟", "硬盘", "Disk: 硬碟→硬盘", source_pattern=r"\b(?:disk|drive)\b"),
    TermRule("记忆体", "内存", "Memory: 记忆体→内存", source_pattern=r"\bmemory\b"),
    TermRule("萤幕", "屏幕", "Screen: 萤幕→屏幕", source_pattern=r"\bscreen\b"),
    TermRule("连线", "连接", "Connection: 连线→连接", source_pattern=r"\bconnections?\b"),
    TermRule("侦测", "检测", "Detect: 侦测→检测", source_pattern=r"\bdetect(?:ing|ed|ion)?\b"),
    TermRule("即时", "实时", "Real-time: 即时→实时", source_pattern=r"\breal[ -]?time\b"),
    TermRule("重新整理", "刷新", "Refresh: 重新整理→刷新", source_pattern=r"\brefresh(?:ing|ed)?\b"),
    TermRule("张贴", "过账", "Post: 张贴→过账", source_pattern=r"\bpost(?:ing|ed)?\b"),
)

#: Exact fixes for entries a generic rule cannot repair (audited by hand).
KNOWN_FIXES: Dict[str, str] = {
    "Ignore Is Opening check for reporting": "忽略开账检查（用于报告）",
    "Folio no.": "Folio no.",
    "Fieldtype": "字段类型",
    "AB+": "AB+",
    "Prepared Report": "预备报表",
    "Prepared report": "预备报表",
    "Reporting Currency": "报告货币",
    "Report bug": "报告缺陷",
    "Stores the JSON of last known versions of various installed apps. It is used to show release notes.": (
        "存储各已安装应用最新已知版本的 JSON，用于显示发行说明。"
    ),
    "You don't have permission to get a report on: {0}": "您无权获取 {0} 的报表",
    "Credit Amount in Reporting Currency": "贷方金额（报告货币）",
    "Debit Amount in Reporting Currency": "借方金额（报告货币）",
    "Reporting Currency Exchange Rate": "报告货币汇率",
    "Reporting Currency Exchange Not Found": "未找到报告货币汇率",
    "Show Full Error and Allow Reporting of Issues to the Developer": (
        "显示完整错误并允许向开发人员报告问题"
    ),
    "Guidelines and policies on vulnerability reporting. Defaults to `https://frappe.io/security`": (
        "关于漏洞报告的指南和政策。默认为 `https://frappe.io/security`"
    ),
    "Website, email or phone where vulnerabilities can be reported. Defaults to `https://security.frappe.io`": (
        "可报告漏洞的网站、邮件或电话。默认为 `https://security.frappe.io`"
    ),
}


def fix_translation(source: str, target: str) -> Tuple[str, List[str]]:
    """Apply every applicable rule to one translation.

    Returns the (possibly unchanged) translation and the notes of applied rules.
    """
    if source in KNOWN_FIXES:
        fixed = KNOWN_FIXES[source]
        if fixed != target:
            return fixed, [f"known-fix: {source!r}"]

    applied: List[str] = []
    result = target
    for rule in TERM_RULES:
        if rule.applies(source, result):
            updated = result.replace(rule.wrong, rule.right)
            if updated != result:
                result = updated
                applied.append(rule.note)
    return result, applied


def fix_translations(
    mapping: Dict[str, str]
) -> Tuple[Dict[str, str], List[Tuple[str, str, str, List[str]]]]:
    """Apply the rules to a whole mapping.

    Returns ``(fixed_mapping, changes)`` where changes is a list of
    ``(source, before, after, notes)``.
    """
    fixed: Dict[str, str] = {}
    changes: List[Tuple[str, str, str, List[str]]] = []
    for source, target in mapping.items():
        new_target, notes = fix_translation(source, target)
        fixed[source] = new_target
        if new_target != target:
            changes.append((source, target, new_target, notes))
    return fixed, changes


def audit_translations(mapping: Dict[str, str]) -> List[Tuple[str, str, str, List[str]]]:
    """Dry-run: report what :func:`fix_translations` would change."""
    _, changes = fix_translations(mapping)
    return changes
