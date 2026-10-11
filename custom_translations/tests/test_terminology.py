"""Regression tests for the context-aware terminology rules.

These are the exact strings that the previous blind ``str.replace``
implementation corrupted in the shipped zh.csv.
"""

import unittest

from custom_translations.terminology import (
    KNOWN_FIXES,
    TERM_RULES,
    audit_translations,
    fix_translation,
    fix_translations,
)


class TestGuardedReplacement(unittest.TestCase):
    def test_reporting_currency_is_not_a_report(self):
        fixed, notes = fix_translation("Reporting Currency", "报表货币")
        self.assertEqual(fixed, "报告货币")
        self.assertTrue(notes)

    def test_report_verb_keeps_the_verb_sense(self):
        source = "Website, email or phone where vulnerabilities can be reported."
        fixed, _ = fix_translation(source, "可以报表漏洞的网站、邮件或电话。")
        self.assertEqual(fixed, "可以报告漏洞的网站、邮件或电话。")

    def test_report_noun_is_converted(self):
        fixed, _ = fix_translation("Report", "报告")
        self.assertEqual(fixed, "报表")

    def test_report_noun_is_not_converted_when_it_is_a_verb_phrase(self):
        fixed, _ = fix_translation("Report bug", "报告缺陷")
        self.assertEqual(fixed, "报告缺陷")

    def test_store_is_not_save(self):
        source = "Stores the JSON of last known versions of various installed apps."
        fixed, _ = fix_translation(source, "保存最后安装版本之应用程序的JSON。")
        self.assertTrue(fixed.startswith("存储"), fixed)

    def test_save_rule_does_not_fire_for_store_sources(self):
        fixed, _ = fix_translation("This server stores tokens.", "此服务器保存令牌。")
        self.assertIn("存储", fixed)
        fixed2, _ = fix_translation("Save the document.", "储存单据。")
        self.assertEqual(fixed2, "保存单据。")

    def test_taiwan_vocabulary_is_normalised(self):
        cases = {
            "User": ("使用者", "用户"),
            "Default": ("预设", "默认"),
            "Login": ("登入", "登录"),
            "Message": ("讯息", "消息"),
            "Search": ("搜寻", "搜索"),
            "Setting": ("设定", "设置"),
            "Data": ("资料", "数据"),
            "Bank Account": ("银行户头", "银行账户"),
        }
        for source, (before, after) in cases.items():
            with self.subTest(source=source):
                fixed, _ = fix_translation(source, before)
                self.assertEqual(fixed, after)

    def test_known_fixes_take_priority(self):
        for source, expected in KNOWN_FIXES.items():
            with self.subTest(source=source):
                fixed, _ = fix_translation(source, "garbage")
                self.assertEqual(fixed, expected)

    def test_untouched_when_no_rule_applies(self):
        fixed, notes = fix_translation("Warehouse", "仓库")
        self.assertEqual(fixed, "仓库")
        self.assertEqual(notes, [])

    def test_rules_are_idempotent(self):
        mapping = {
            "Reporting Currency": "报表货币",
            "Report": "报告",
            "User": "使用者预设",
            "Default": "预设值",
            "Store": "保存数据",
        }
        once, _ = fix_translations(mapping)
        twice, changes = fix_translations(once)
        self.assertEqual(once, twice)
        self.assertEqual(changes, [])

    def test_every_rule_has_a_source_guard(self):
        for rule in TERM_RULES:
            with self.subTest(rule=rule.note):
                self.assertIsNotNone(
                    rule.source_pattern,
                    "unguarded rule would corrupt unrelated strings",
                )

    def test_audit_reports_changes_only(self):
        changes = audit_translations({"Warehouse": "仓库", "Report": "报告"})
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0][0], "Report")

    def test_report_noun_verb_distinction(self):
        """Test that report noun vs verb is correctly distinguished."""
        # Noun case: "Report" should become "报表"
        fixed, notes = fix_translation("Report", "报告")
        self.assertEqual(fixed, "报表")
        self.assertTrue(notes)  # At least one note should be present

        # Verb case: "Report bug" should stay "报告"
        fixed, notes = fix_translation("Report bug", "报告缺陷")
        self.assertEqual(fixed, "报告缺陷")
        # Translation was already correct, so no rule fired and no note is logged.
        self.assertEqual(notes, [])

    def test_reporting_currency_noun_verb(self):
        """Test that reporting currency noun vs verb is correctly distinguished."""
        # Noun case: "Reporting Currency" should become "报告货币"
        fixed, notes = fix_translation("Reporting Currency", "报表货币")
        self.assertEqual(fixed, "报告货币")
        # Note: KNOWN_FIXES takes priority, so the note is "known-fix: ..."
        self.assertTrue(notes)  # At least one note should be present

        # Verb case: lowercase "reporting currency" keeps the generic wording
        # (the correction rule is case-sensitive and only fires for the
        # title-case field label "Reporting Currency").
        fixed, notes = fix_translation("reporting currency", "报表货币")
        self.assertEqual(fixed, "报表货币")
        # Already correct -> no rule fired -> no note.
        self.assertEqual(notes, [])

    def test_generate_report_verb(self):
        """Test that 'generate report' verb phrase is correctly handled."""
        # Verb case: "generate report" should become "生成报表"
        fixed, notes = fix_translation("generate report", "生成报表")
        self.assertEqual(fixed, "生成报表")
        # Already correct -> no rule fired -> no note.
        self.assertEqual(notes, [])

        # Noun case: "The report" should become "报表"
        fixed, notes = fix_translation("The report", "报表")
        self.assertEqual(fixed, "报表")
        # Already correct -> no rule fired -> no note.
        self.assertEqual(notes, [])

    def test_zhang_variant_character_is_normalised_in_context(self):
        """帐→账 keeps the word, only the character changes.

        帐号→账号, 帐户→账户, 台帐→台账, 日记帐→日记账, 锁帐→锁账.
        """
        cases = {
            "Bank Account No": ("银行帐号", "银行账号"),
            "No email account found": ("未找到电子邮件帐户", "未找到电子邮件账户"),
            "Serial No Ledger": ("序列号台帐", "序列号台账"),
            "Exchange Gain/Loss amount has been booked through {0}": (
                "汇兑损益日记帐凭证", "汇兑损益日记账凭证",
            ),
            "Not allowed to update stock transactions older than {0}": (
                "最晚可动帐日期", "最晚可动账日期",
            ),
        }
        for source, (before, after) in cases.items():
            with self.subTest(source=source):
                fixed, notes = fix_translation(source, before)
                self.assertEqual(fixed, after)
                self.assertTrue(notes)

    def test_tent_is_not_an_account(self):
        """帐篷 (tent) is a different word - the 帐→账 rule must not fire."""
        fixed, notes = fix_translation("Tent", "帐篷")
        self.assertEqual(fixed, "帐篷")
        self.assertEqual(notes, [])

    def test_jilu_is_record_but_jiyao_stays(self):
        """纪录→记录 (record); 纪要 (minutes) is a correct word, untouched."""
        fixed, _ = fix_translation(
            "Select atleast 1 record for printing", "选择打印ATLEAST 1纪录"
        )
        self.assertEqual(fixed, "选择打印ATLEAST 1记录")
        fixed, notes = fix_translation("Quality Meeting Minutes", "质量会议纪要")
        self.assertEqual(fixed, "质量会议纪要")
        self.assertEqual(notes, [])

    def test_login_account_wording_is_context_sensitive(self):
        """A login account is 账号, an accounting Account stays 账户."""
        cases = {
            "Don't have an account?": ("还没有账户？", "还没有账号？"),
            "Create Account": ("创建账户", "创建账号"),
            "Bank Account No": ("银行账户", "银行账号"),
            "Your account has been locked and will resume after {0} seconds": (
                "您的账户已被锁定，并将在{0}秒后恢复", "您的账号已被锁定，并将在{0}秒后恢复",
            ),
        }
        for source, (before, after) in cases.items():
            with self.subTest(source=source):
                fixed, _ = fix_translation(source, before)
                self.assertEqual(fixed, after)
        # accounting / email contexts deliberately keep 账户
        for source, target in (
            ("Bank Account", "银行账户"),
            ("Account Data", "账户数据"),
            ("Update Account", "更新账户"),
        ):
            with self.subTest(source=source):
                fixed, notes = fix_translation(source, target)
                self.assertEqual(fixed, target)
                self.assertEqual(notes, [])
