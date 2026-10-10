"""Unit tests for the dependency-free helpers (no frappe needed)."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from custom_translations import csvio, po
from custom_translations.sources import (
    discover_app,
    extract_msgids,
    extract_msgids_from_dir,
    read_official_translations,
    source_inventory,
)
from custom_translations.terminology import audit_translations, fix_translation, fix_translations
from custom_translations.validate import is_acceptable, looks_like_prose, validate

PO_SAMPLE = '''# translation template
msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

#: frappe/translate.py:1
msgid "Journal Entry"
msgstr "日记账分录"

msgid "Add attachment"
msgstr ""

#, fuzzy
msgid "Multi\\nline"
msgstr "多\\n行"

msgctxt "Doctype"
msgid "Open"
msgstr "打开"
'''


class TestPoParser(unittest.TestCase):
    def test_parses_header_entries_and_context(self):
        entries = po.parse_po_text(PO_SAMPLE)
        self.assertEqual(len(entries), 5)
        self.assertTrue(entries[0].is_header)
        by_key = {entry.key: entry for entry in entries}
        self.assertEqual(by_key["Journal Entry"].msgstr, "日记账分录")
        self.assertEqual(by_key["Doctype:Open"].msgstr, "打开")
        self.assertEqual(by_key["Multi\nline"].msgstr, "多\n行")
        self.assertTrue(by_key["Multi\nline"].fuzzy)

    def test_untranslated_detection(self):
        entries = po.parse_po_text(PO_SAMPLE)
        untranslated = [entry.msgid for entry in po.iter_untranslated(entries)]
        self.assertEqual(untranslated, ["Add attachment"])

    def test_fill_po_file_is_in_place_and_preserves_comments(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "zh.po"
            path.write_text(PO_SAMPLE, encoding="utf-8")
            filled = po.fill_po_file(path, {"Add attachment": "添加附件", "Nope": "x"})
            self.assertEqual(filled, 1)
            result = path.read_text(encoding="utf-8")
            self.assertIn('#: frappe/translate.py:1', result)
            self.assertIn('msgstr "添加附件"', result)
            self.assertEqual(result.count("msgid"), PO_SAMPLE.count("msgid"))
            self.assertEqual(len(po.parse_po_text(result)), 5)

    def test_fill_po_file_noop_keeps_bytes(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "zh.po"
            path.write_text(PO_SAMPLE, encoding="utf-8")
            self.assertEqual(po.fill_po_file(path, {}), 0)
            self.assertEqual(path.read_text(encoding="utf-8"), PO_SAMPLE)


class TestCsvIo(unittest.TestCase):
    def test_roundtrip_escapes_newlines_and_keeps_context(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "zh.csv"
            csvio.write_csv_entries(
                path,
                [
                    csvio.CsvEntry("line1\nline2", "第一行\n第二行"),
                    csvio.CsvEntry("Open", "打开", context="Doctype"),
                ],
            )
            raw = path.read_text(encoding="utf-8")
            self.assertIn(r"line1\nline2", raw)
            entries = csvio.read_csv_entries(path)
            self.assertEqual(entries[0].msgstr, "第一行\n第二行")
            self.assertEqual(entries[1].context, "Doctype")
            self.assertEqual(entries[1].key, "Open:Doctype")

    def test_preserves_existing_line_terminator(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "zh.csv"
            path.write_bytes('"a","b"\r\n'.encode("utf-8"))
            csvio.write_csv_entries(path, [csvio.CsvEntry("a", "c")])
            self.assertIn(b"\r\n", path.read_bytes())
            self.assertEqual(csvio.detect_lineterminator(path), "\r\n")


class TestSourceDiscovery(unittest.TestCase):
    def _build(self, tmp):
        root = Path(tmp)
        # erpnext style: translations/*.csv, no locale dir
        erp = root / "erpnext" / "erpnext"
        (erp / "translations").mkdir(parents=True)
        (erp / "translations" / "zh.csv").write_text(
            '"Journal Entry","日记账分录"\n', encoding="utf-8"
        )
        (erp / "accounts.py").write_text(
            'from frappe import _\nmsg = _("Trial Balance")\nother = _("New String")\n',
            encoding="utf-8",
        )
        # frappe style: locale/*.po + main.pot
        fr = root / "frappe" / "frappe"
        (fr / "locale").mkdir(parents=True)
        (fr / "locale" / "zh.po").write_text(
            'msgid "Stock Entry"\nmsgstr "库存移动单"\n\nmsgid "Untranslated"\nmsgstr ""\n',
            encoding="utf-8",
        )
        return root

    def test_discovers_both_layouts(self):
        with TemporaryDirectory() as tmp:
            root = self._build(tmp)
            erp = discover_app("erpnext", root / "erpnext" / "erpnext")
            self.assertEqual(erp.format, "csv")
            self.assertEqual(len(erp.csv_files), 1)
            self.assertFalse(erp.po_files)

            fr = discover_app("frappe", root / "frappe" / "frappe")
            self.assertEqual(fr.format, "po")
            self.assertEqual(len(fr.po_files), 1)

    def test_inventory_falls_back_to_source_scan(self):
        with TemporaryDirectory() as tmp:
            root = self._build(tmp)
            erp_dir = root / "erpnext" / "erpnext"
            inventory = source_inventory("erpnext", erp_dir)
            self.assertEqual(inventory.origin, "source")
            self.assertEqual(inventory.msgids, {"Trial Balance", "New String"})
            self.assertEqual(
                read_official_translations("erpnext", erp_dir), {"Journal Entry": "日记账分录"}
            )

    def test_inventory_prefers_po(self):
        with TemporaryDirectory() as tmp:
            root = self._build(tmp)
            inventory = source_inventory("frappe", root / "frappe" / "frappe")
            self.assertEqual(inventory.origin, "po")
            self.assertEqual(inventory.msgids, {"Stock Entry", "Untranslated"})

    def test_extract_msgids_ignores_non_translation_calls(self):
        text = (
            'x = _("A")\ny = __("B")\nz = some_("C")\nw = _.each(items)\n'
            'j = {{ _("D") }}\nk = _("con" "cat")\n'
        )
        self.assertEqual(extract_msgids(text), {"A", "B", "D", "concat"})

    def test_extract_msgids_from_dir_skips_node_modules(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "node_modules").mkdir()
            (root / "node_modules" / "a.js").write_text('__("ignored")', encoding="utf-8")
            (root / "a.js").write_text('__("kept")', encoding="utf-8")
            self.assertEqual(extract_msgids_from_dir(root), {"kept"})


class TestValidation(unittest.TestCase):
    def test_placeholder_loss_is_an_error(self):
        self.assertFalse(is_acceptable("Cannot cancel {0}.", "无法取消。"))
        self.assertTrue(is_acceptable("Cannot cancel {0}.", "无法取消 {0}。"))

    def test_html_loss_is_an_error(self):
        self.assertFalse(is_acceptable("<b>Hello</b>", "你好"))

    def test_english_echo_of_sentence_is_an_error_but_label_is_warning(self):
        self.assertFalse(is_acceptable("Save the document.", "Save the document."))
        self.assertTrue(is_acceptable("Folio", "Folio"))

    def test_prose_detection(self):
        self.assertTrue(looks_like_prose("Please select a Customer"))
        self.assertFalse(looks_like_prose("BOM"))
        self.assertFalse(looks_like_prose("https://example.com"))

    def test_jinja_and_percent_placeholders(self):
        self.assertTrue(is_acceptable("Hello %(name)s", "你好 %(name)s"))
        self.assertFalse(is_acceptable("Hello %(name)s", "你好"))
        issues = validate("{{ _('x') }} {0}", "x")
        self.assertTrue(any(issue.code == "placeholder" for issue in issues))
