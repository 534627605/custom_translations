"""Unit tests for the upstream-PO import pipeline (sync_po).

The tests build real PO files and real CSV files in a temp directory and run
the real parser/merger end to end - no mocks, no network, no git clones.
"""

import tempfile
import unittest
from pathlib import Path

from custom_translations import csvio
from custom_translations.sync_po import (
    REQUIRED_KEYWORDS,
    _filter_terms,
    _parse_po,
    default_po_paths,
    sync_po,
)

PO_TEMPLATE = '''msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\nmsgid "{msgid}"\nmsgstr "{msgstr}"\n'''


def _write_po(directory: Path, rows, name="zh.po") -> Path:
    """Write a minimal PO file. ``rows`` items: (msgid, msgstr) or raw (line,) tuples."""
    parts = []
    for row in rows:
        if len(row) == 2:
            parts.append(PO_TEMPLATE.format(msgid=row[0], msgstr=row[1]))
        else:
            parts.append(row[0])
    path = directory / name
    path.write_text("\n".join(parts), encoding="utf-8")
    return path


class TestSyncPo(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    # --------------------------------------------------------------- #
    # parsing
    # --------------------------------------------------------------- #
    def test_parse_po(self):
        po_path = _write_po(
            self.dir,
            [("Journal Entry", "日记账分录"), ("Payment Entry", "付款单")],
        )
        result = _parse_po(po_path)
        self.assertEqual(result["Journal Entry"], "日记账分录")
        self.assertEqual(result["Payment Entry"], "付款单")

    def test_parse_po_skips_untranslated_fuzzy_and_context(self):
        raw = (
            'msgid "Empty"\nmsgstr ""\n\n'
            '#, fuzzy\nmsgid "Fuzzy"\nmsgstr "模糊"\n\n'
            'msgctxt " DocType"\nmsgid "Payment"\nmsgstr "付款"\n'
        )
        po_path = self.dir / "zh.po"
        po_path.write_text(raw, encoding="utf-8")
        result = _parse_po(po_path)
        self.assertNotIn("Empty", result)
        self.assertNotIn("Fuzzy", result)
        # msgctxt keys follow the Frappe CSV convention msgid:context
        self.assertEqual(result["Payment: DocType"], "付款")

    def test_parse_missing_file_returns_empty(self):
        self.assertEqual(_parse_po(self.dir / "nope.po"), {})

    # --------------------------------------------------------------- #
    # keyword filtering
    # --------------------------------------------------------------- #
    def test_filter_terms(self):
        entries = {
            "Journal Entry": "日记账分录",
            "Payment Entry": "付款单",
            "Simple Entry": "简单条目",
        }
        result = _filter_terms(entries)
        self.assertGreater(len(result), 0)
        self.assertIn("Payment Entry", result)
        self.assertNotIn("Simple Entry", result)

    # --------------------------------------------------------------- #
    # end-to-end merge
    # --------------------------------------------------------------- #
    def _write_csv(self, rows) -> Path:
        path = self.dir / "zh.csv"
        csvio.write_csv_entries(
            path, [csvio.CsvEntry(msgid=m, msgstr=t, context=c) for m, t, c in rows]
        )
        return path

    def test_sync_po_overwrites_with_force(self):
        csv_path = self._write_csv([("Journal Entry", "旧翻译", None)])
        po_path = _write_po(self.dir, [("Journal Entry", "日记账分录")])
        added = sync_po(csv_path, force=True, po_paths=[po_path])
        self.assertEqual(added, 1)
        data = csvio.read_csv_translations(csv_path)
        self.assertEqual(data["Journal Entry"], "日记账分录")

    def test_sync_po_adds_new(self):
        csv_path = self._write_csv([("Old Entry", "旧条目", None)])
        po_path = _write_po(self.dir, [("New Entry", "新条目")])
        added = sync_po(csv_path, po_paths=[po_path])
        self.assertEqual(added, 1)
        data = csvio.read_csv_translations(csv_path)
        self.assertEqual(data["New Entry"], "新条目")
        self.assertEqual(data["Old Entry"], "旧条目")

    def test_sync_po_keeps_existing_without_force(self):
        csv_path = self._write_csv([("Journal Entry", "旧日记账", None)])
        po_path = _write_po(self.dir, [("Journal Entry", "新日记账")])
        added = sync_po(csv_path, po_paths=[po_path])
        self.assertEqual(added, 0)
        data = csvio.read_csv_translations(csv_path)
        self.assertEqual(data["Journal Entry"], "旧日记账")

    def test_sync_po_preserves_three_column_context_rows(self):
        csv_path = self._write_csv([("Yes", "是的", "Button")])
        po_path = _write_po(self.dir, [("No", "否")])
        added = sync_po(csv_path, po_paths=[po_path])
        self.assertEqual(added, 1)
        entries = csvio.read_csv_entries(csv_path)
        self.assertEqual(entries[0].context, "Button")
        self.assertEqual(entries[0].msgstr, "是的")

    def test_sync_po_keyword_scope(self):
        csv_path = self._write_csv([])
        po_path = _write_po(
            self.dir, [("Payment Entry", "付款单"), ("Plain Sentence", "普通句子")]
        )
        added = sync_po(csv_path, po_paths=[po_path], keywords=REQUIRED_KEYWORDS)
        self.assertEqual(added, 1)
        data = csvio.read_csv_translations(csv_path)
        self.assertIn("Payment Entry", data)
        self.assertNotIn("Plain Sentence", data)

    def test_default_po_paths_finds_local_apps(self):
        paths = default_po_paths()
        # the bench checkout ships frappe + erpnext at the very least
        self.assertTrue(any(p.name == "zh.po" for p in paths), paths)


if __name__ == "__main__":
    unittest.main()
