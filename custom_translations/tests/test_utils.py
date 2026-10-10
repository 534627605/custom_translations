"""Behavioural tests for the app's core logic, using the frappe stub."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from custom_translations.tests import frappe_stub

APP_CSV = '"Journal Entry","日记账分录"\n"Trial Balance","试算平衡表"\n'
ERPNEXT_CSV = '"Journal Entry","日记账分录"\n'
ERPNEXT_SOURCE = 'msg = _("Trial Balance")\nother = _("New String")\n'
FRAPPE_PO = (
    'msgid "Stock Entry"\nmsgstr "库存移动单"\n\n'
    'msgid "Untranslated"\nmsgstr ""\n\n'
    'msgid "New String"\nmsgstr ""\n'
)


def build_site(root: Path) -> None:
    """Create a mini bench tree: this app + erpnext (csv) + frappe (po)."""
    app = root / "custom_translations" / "custom_translations"
    (app / "translations").mkdir(parents=True)
    (app / "translations" / "zh.csv").write_text(APP_CSV, encoding="utf-8")

    erp = root / "erpnext" / "erpnext"
    (erp / "translations").mkdir(parents=True)
    (erp / "translations" / "zh.csv").write_text(ERPNEXT_CSV, encoding="utf-8")
    (erp / "accounts.py").write_text(ERPNEXT_SOURCE, encoding="utf-8")

    fr = root / "frappe" / "frappe"
    (fr / "locale").mkdir(parents=True)
    (fr / "locale" / "zh.po").write_text(FRAPPE_PO, encoding="utf-8")


class UtilsTestCase(unittest.TestCase):
    """Base class: builds the fake bench and installs the stub."""

    PATCHED = ("_scan_missing_translations", "load_config", "_auto_translate_via_api")

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        build_site(self.root)
        self.state = frappe_stub.install(
            self.root, ["frappe", "erpnext", "custom_translations"]
        )
        # utils imports frappe at module import time
        import custom_translations.utils as utils

        self.utils = utils
        self.csv = utils.get_csv_path()
        # Monkeypatching module attributes leaks across tests (the module object
        # is shared), so remember the originals and restore them.
        self._originals = {name: getattr(utils, name) for name in self.PATCHED}

    def tearDown(self):
        for name, value in self._originals.items():
            setattr(self.utils, name, value)
        self._tmp.cleanup()


class TestCsvLayer(UtilsTestCase):
    def test_load(self):
        self.assertEqual(
            self.utils.load_app_translations(),
            {"Journal Entry": "日记账分录", "Trial Balance": "试算平衡表"},
        )

    def test_append_does_not_overwrite_by_default(self):
        changed = self.utils._append_to_csv({"Journal Entry": "WRONG"}, overwrite=False)
        self.assertEqual(changed, 0)
        self.assertEqual(
            self.utils.load_app_translations()["Journal Entry"], "日记账分录"
        )

    def test_append_with_overwrite_replaces(self):
        changed = self.utils._append_to_csv({"Journal Entry": "日记账分录（新）"}, overwrite=True)
        self.assertEqual(changed, 1)
        self.assertEqual(
            self.utils.load_app_translations()["Journal Entry"], "日记账分录（新）"
        )

    def test_append_adds_new_entries(self):
        self.assertEqual(self.utils._append_to_csv({"Stock Entry": "库存移动单"}), 1)
        self.assertIn("Stock Entry", self.utils.load_app_translations())

    def test_no_write_when_nothing_changes(self):
        before = self.csv.read_bytes()
        self.utils._append_to_csv({"Journal Entry": "日记账分录"}, overwrite=True)
        self.assertEqual(before, self.csv.read_bytes())


class TestScanning(UtilsTestCase):
    def test_finds_missing_in_both_layouts(self):
        missing = self.utils._scan_missing_translations()
        pairs = {(item["app"], item["msgid"]) for item in missing}
        # erpnext ships a CSV and source files
        self.assertIn(("erpnext", "New String"), pairs)
        self.assertIn(("frappe", "Untranslated"), pairs)
        self.assertIn(("frappe", "New String"), pairs)
        # already translated anywhere -> not missing
        self.assertNotIn(("frappe", "Stock Entry"), pairs)
        self.assertNotIn(("erpnext", "Journal Entry"), pairs)

    def test_coverage_report_shape(self):
        report = {row["app"]: row for row in self.utils.get_coverage_report()}
        self.assertEqual(report["erpnext"]["format"], "csv")
        self.assertEqual(report["erpnext"]["inventory_origin"], "source")
        self.assertEqual(report["frappe"]["format"], "po")
        self.assertEqual(report["frappe"]["inventory"], 3)
        self.assertEqual(report["frappe"]["missing_count"], 2)

    def test_app_list_excludes_self(self):
        self.assertEqual(self.utils.get_installed_apps(), ["frappe", "erpnext"])


class TestMissingLog(UtilsTestCase):
    def test_logs_and_dedupes_across_statuses(self):
        missing = [{"app": "frappe", "msgid": "Untranslated"}]
        self.assertEqual(self.utils._log_missing_translations(missing), 1)
        # the same string is not logged twice while it is Open
        self.assertEqual(self.utils._log_missing_translations(missing), 0)

        # ... and not again after it was reviewed (the old code only deduped Open rows)
        self.state.table("Missing Translation Log")[0]["status"] = "Reviewed"
        self.assertEqual(self.utils._log_missing_translations(missing), 0)

    def test_skips_overlong_strings(self):
        long_text = "x" * 2001
        self.assertEqual(
            self.utils._log_missing_translations([{"app": "frappe", "msgid": long_text}]), 0
        )

    def test_cap_is_respected(self):
        missing = [{"app": "frappe", "msgid": f"string {i}"} for i in range(10)]
        self.assertEqual(self.utils._log_missing_translations(missing, limit=3), 3)
        self.assertEqual(len(self.state.table("Missing Translation Log")), 3)

    def test_mark_translated(self):
        self.utils._log_missing_translations([{"app": "frappe", "msgid": "Untranslated"}])
        self.utils._mark_logs_translated({"Untranslated": "未翻译"})
        record = self.state.table("Missing Translation Log")[0]
        self.assertEqual(record["status"], "Translated")
        self.assertEqual(record["translated_text"], "未翻译")


class TestBootHook(UtilsTestCase):
    def setUp(self):
        super().setUp()
        self.scans = []
        original = self.utils._scan_missing_translations

        def counting_scan(apps=None):
            self.scans.append(apps)
            return original(apps)

        self.utils._scan_missing_translations = counting_scan

    def test_scans_once_thanks_to_the_cache(self):
        self.utils.detect_missing_translations_bootinfo()
        self.utils.detect_missing_translations_bootinfo()
        self.assertEqual(len(self.scans), 1, "the second boot must use the cache")
        self.assertTrue(self.state.table("Missing Translation Log"))

    def test_guest_and_other_languages_are_skipped(self):
        self.state.installed = list(self.state.installed)
        self.utils.frappe.session["user"] = "Guest"
        self.utils.detect_missing_translations_bootinfo()
        self.utils.frappe.session["user"] = "Administrator"
        self.utils.frappe.local["lang"] = "en"
        self.utils.detect_missing_translations_bootinfo()
        self.assertEqual(self.scans, [])

    def test_scan_on_boot_false_disables_scanning(self):
        self.utils.load_config = lambda: {"scan_on_boot": False}
        self.utils.detect_missing_translations_bootinfo()
        self.assertEqual(self.scans, [])

    def test_never_calls_the_api_synchronously(self):
        self.utils.load_config = lambda: {
            "scan_on_boot": True,
            "auto_translate": True,
            "is_configured": True,
            "scan_interval_seconds": 60,
        }

        def boom(*args, **kwargs):
            raise AssertionError("the boot hook must not call the API synchronously")

        self.utils._auto_translate_via_api = boom
        self.utils.detect_missing_translations_bootinfo()
        self.assertEqual(len(self.state.enqueued), 1)
        self.assertEqual(
            self.state.enqueued[0]["method"],
            "custom_translations.utils._auto_translate_via_api",
        )

    def test_auto_translate_not_enqueued_when_disabled(self):
        self.utils.detect_missing_translations_bootinfo()
        self.assertEqual(self.state.enqueued, [])

    def test_errors_never_propagate(self):
        def boom(*args, **kwargs):
            raise RuntimeError("database on fire")

        self.utils._scan_missing_translations = boom
        self.utils.detect_missing_translations_bootinfo()  # must not raise


class TestManualCorrections(UtilsTestCase):
    def test_manual_source_records_are_applied_even_when_not_reviewed(self):
        self.state.insert(
            {
                "doctype": "Missing Translation Log",
                "source_text": "New String",
                "translated_text": "新字符串",
                "status": "Translated",
                "translation_source": "Manual",
            }
        )
        self.state.insert(
            {
                "doctype": "Missing Translation Log",
                "source_text": "Untranslated",
                "translated_text": "未翻译",
                "status": "Reviewed",
                "translation_source": "Auto",
            }
        )
        count = self.utils.apply_manual_corrections()
        self.assertEqual(count, 2)
        translations = self.utils.load_app_translations()
        self.assertEqual(translations["New String"], "新字符串")
        self.assertEqual(translations["Untranslated"], "未翻译")

    def test_manual_corrections_override_auto_values(self):
        self.utils._append_to_csv({"Untranslated": "机器翻译"}, overwrite=False)
        self.state.insert(
            {
                "doctype": "Missing Translation Log",
                "source_text": "Untranslated",
                "translated_text": "人工翻译",
                "status": "Reviewed",
            }
        )
        self.utils.apply_manual_corrections()
        self.assertEqual(self.utils.load_app_translations()["Untranslated"], "人工翻译")

    def test_on_translation_update_writes_to_csv(self):
        doc = frappe_stub.FakeDoc(
            {"language": "zh", "source_text": "New String", "translated_text": "新字符串"}
        )
        self.utils.on_translation_update(doc)
        self.assertEqual(self.utils.load_app_translations()["New String"], "新字符串")

    def test_on_translation_update_ignores_other_languages(self):
        doc = frappe_stub.FakeDoc(
            {"language": "de", "source_text": "New String", "translated_text": "x"}
        )
        self.utils.on_translation_update(doc)
        self.assertNotIn("New String", self.utils.load_app_translations())


class TestTerminologyRepair(UtilsTestCase):
    def test_fix_batch_terminology_uses_guarded_rules(self):
        self.utils._append_to_csv(
            {
                "Reporting Currency": "报表货币",
                "Report": "报告",
                "User": "使用者",
            },
            overwrite=True,
        )
        count = self.utils.fix_batch_terminology()
        self.assertEqual(count, 3)
        translations = self.utils.load_app_translations()
        self.assertEqual(translations["Reporting Currency"], "报告货币")
        self.assertEqual(translations["Report"], "报表")
        self.assertEqual(translations["User"], "用户")

    def test_dry_run_changes_nothing(self):
        self.utils._append_to_csv({"User": "使用者"}, overwrite=True)
        self.utils.fix_batch_terminology(dry_run=True)
        self.assertEqual(self.utils.load_app_translations()["User"], "使用者")
