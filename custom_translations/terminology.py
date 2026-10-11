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
    #: match ``source_pattern`` case-sensitively (default: ignore case).
    #: Use for title-case field labels such as "Reporting Currency" where the
    #: lowercase phrase must keep its generic translation.
    case_sensitive: bool = False

    def applies(self, source: str, target: str) -> bool:
        if self.wrong not in target:
            return False
        if self.target_pattern and not re.search(self.target_pattern, target):
            return False
        if self.source_pattern is not None:
            flags = 0 if self.case_sensitive else re.IGNORECASE
            if not re.search(self.source_pattern, source, flags):
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
        # Title-case field label only; a lowercase "reporting currency"
        # mention inside a sentence keeps its generic wording.
        source_pattern=r"Reporting Currency",
        case_sensitive=True,
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
    # ---- Obsolete variant character 帐 -> 账 (mainland standard) ----
    # The word itself is kept - 帐号→账号, 帐户→账户, 台帐→台账 - only the
    # character is normalised. 帐篷 (tent) is a *different* word, so the
    # guard is limited to financial/accounting sources and never fires for
    # a tent string.
    TermRule(
        "帐",
        "账",
        "Simplified chars: 帐→账 (帐号→账号, 帐户→账户, 台帐→台账)",
        source_pattern=r"\baccounts?\b|\bjournals?\b|\bledgers?\b|\bbook(?:ed|ing)\b|\bstock\b",
    ),
    # 纪录 is standard only in 打破纪录 (breaking a sports record); ERP text
    # means the record sense, which is always 记录. Words that merely contain
    # 纪 (纪要 minutes, 纪念 anniversary) are correct and never touched.
    TermRule("纪录", "记录", "Record: 纪录→记录", source_pattern=r"\brecords?\b"),
    # 户头 is Taiwan banking slang for an account; the mainland term is 账户.
    # Every upstream occurrence is a Bank Account / Company Account row.
    TermRule("户头", "账户", "Account: 户头→账户", source_pattern=r"\baccounts?\b"),
)

#: Exact fixes for entries a generic rule cannot repair (audited by hand).
KNOWN_FIXES: Dict[str, str] = {
    # Wording aligned with the upstream frappe zh.po where it exists, so this
    # app never diverges from the official translation without a reason.
    "Ignore Is Opening check for reporting": "忽略期初检查用于报表",
    "Folio no.": "Folio no.",
    "Fieldtype": "字段类型",
    "AB+": "AB+",
    "Prepared Report": "预生成报表",
    "Prepared report": "预生成报表",
    "Prepared Report Analytics": "预生成报表分析",
    "Prepared Report User": "预生成报表用户",
    "Reporting Currency": "报告货币",
    "Report bug": "报告缺陷",
    "Stores the JSON of last known versions of various installed apps. It is used to show release notes.": (
        "存储已安装应用最后已知版本的JSON数据，用于显示版本说明"
    ),
    "You don't have permission to get a report on: {0}": "您无权获取 {0} 的报表",
    "Credit Amount in Reporting Currency": "贷方金额（报告货币）",
    "Debit Amount in Reporting Currency": "借方金额（报告货币）",
    "Reporting Currency Exchange Rate": "报告货币汇率",
    "Reporting Currency Exchange Not Found": "未找到报告货币汇率",
    "Show Full Error and Allow Reporting of Issues to the Developer": (
        "显示完整错误并允许向开发者报告问题"
    ),
    "Guidelines and policies on vulnerability reporting. Defaults to `https://frappe.io/security`": (
        "关于漏洞报告的指南和政策。默认为 `https://frappe.io/security`"
    ),
    "Website, email or phone where vulnerabilities can be reported. Defaults to `https://security.frappe.io`": (
        "可报告漏洞的网站、邮件或电话。默认为 `https://security.frappe.io`"
    ),
    # 帐号 in a row whose English source has no "account" word, so the
    # generic character rule cannot fire - audited by hand instead.
    "Setting Events to {0}, since the Employee attached to the below Sales Persons does not have a User ID{1}": (
        "设置事件为{0}，因为关联到下列业务员的员工没有用户账号{1}"
    ),
    # ---- Word choice is context sensitive: a *login* account is 账号, an
    # *accounting* Account is 账户. Both sources contain "account", so no
    # generic rule can tell them apart - each row below was audited against
    # its real usage:
    #   Create Account  - frappe login page sign-up button (login.js)
    #   My Account      - frappe /me user profile page (website_settings.py)
    #   Bank Account No - bank account *number*, like "Bank A/C No."
    # Rows meaning an accounting Account (Bank Account, Payable Account,
    # Account Data, Email Account, ...) deliberately stay 账户 and are NOT
    # listed here.
    "Create Account": "创建账号",
    "Delete Account": "删除账号",
    "Confirm Deletion of Account": "确认删除账号",
    "Account Deletion Settings": "账号删除设置",
    "Automatically delete account within (hours)": "在（小时）内自动删除账号",
    "My Account": "我的账号",
    "Don't have an account?": "还没有账号？",
    "Have an account? Login": "有账号？登录",
    "Let's set up your account": "让我们设置您的账号",
    "Let's setup your account.": "让我们设置您的账号。",
    "Note: Your request for account deletion will be fulfilled within {0} hours.": (
        "注意：您的账号删除请求将在 {0} 小时内完成。"
    ),
    "Show account deletion link in My Account page": "在我的账号页面显示账号删除链接",
    "Your account has been deleted": "您的账号已被删除",
    "Your account has been locked and will resume after {0} seconds": (
        "您的账号已被锁定，并将在{0}秒后恢复"
    ),
    "wants to access the following details from your account": "想要访问您账号的以下详细信息",
    "A new account has been created for you at {0}": "已经在{0}为您创建一个新的账号",
    "A new account has been created for you at {0}.": "已为您创建新账号{0}.",
    "Bank Account No": "银行账号",
    "Custom Field {0} is created by the Administrator and can only be deleted through the Administrator account.": (
        "自定义字段 {0} 由管理员创建，只能通过管理员账号删除。"
    ),
    "As per your request, your account and data on {0} associated with email {1} has been permanently deleted": (
        "根据您的要求，您在 {0} 上与邮件 {1} 关联的账号和数据已被永久删除"
    ),
    '<div class="ql-editor read-mode"><p>Send a request to delete your account and personally identifiable information (PII) that is stored on our system. You will receive an email to verify your request. Once the request is verified we will take care of deleting your PII. If you just want to check what PII we have stored, you can <a href="/request-data" rel="noopener noreferrer">request your data</a>.</p></div>': (
        '<div class="ql-editor read-mode"><p>发送请求以删除您的账号以及我们系统上存储的个人身份信息（PII）。您将收到一封用于验证请求的电子邮件。验证通过后，我们将负责删除您的PII。如果您只想查看我们存储了哪些PII，可以<a href="/request-data" rel="noopener noreferrer">请求您的数据</a>。</p></div>'
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
