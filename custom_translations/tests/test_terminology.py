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
