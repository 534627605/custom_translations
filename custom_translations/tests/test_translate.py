"""Tests for the AI translation engine (transport is faked)."""

import json
import unittest

from custom_translations.translate import (
    ApiError,
    OpenAiCompatClient,
    _parse_translations,
    build_glossary_block,
    select_reference_translations,
    translate_entries,
)

CONFIG = {
    "api_key": "test-key",
    "api_endpoint": "http://example.invalid/v1/chat/completions",
    "model": "test-model",
    "provider": "nvidia",
    "batch_size": 10,
}

GLOSSARY = {"Journal Entry": "日记账分录", "Stock Entry": "库存移动单"}


class FakeClient(OpenAiCompatClient):
    """Returns canned replies and records the prompts it was given."""

    def __init__(self, replies, config=None):
        super().__init__(config or CONFIG)
        self.replies = list(replies)
        self.prompts = []

    def complete(self, system_prompt, user_prompt, json_mode=True):
        self.prompts.append(user_prompt)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def reply(*translations):
    return json.dumps({"translations": list(translations)})


class TestPromptBuilding(unittest.TestCase):
    def test_glossary_block_only_includes_terms_in_the_batch(self):
        block = build_glossary_block(["Journal Entry"], GLOSSARY)
        self.assertIn("Journal Entry => 日记账分录", block)
        self.assertNotIn("Stock Entry", block)
        self.assertEqual(build_glossary_block(["Warehouse"], GLOSSARY), "")

    def test_reference_selection_prefers_token_overlap(self):
        memory = {
            "Stock Entry Type": "库存移动类型",
            "Delete all documents": "删除所有单据",
        }
        picked = select_reference_translations(["Stock Entry"], memory)
        self.assertEqual(picked[0][0], "Stock Entry Type")


class TestParsing(unittest.TestCase):
    def test_accepts_common_shapes(self):
        self.assertEqual(_parse_translations('["a","b"]', 2), ["a", "b"])
        self.assertEqual(_parse_translations('{"translations":["a"]}', 1), ["a"])
        self.assertEqual(_parse_translations('{"data":["a"]}', 1), ["a"])
        self.assertEqual(_parse_translations('here you go: ["a"]', 1), ["a"])
        self.assertEqual(_parse_translations('{"anything":["a"]}', 1), ["a"])

    def test_rejects_wrong_length(self):
        with self.assertRaises(ApiError):
            _parse_translations('["a"]', 2)


class TestTranslateEntries(unittest.TestCase):
    def test_happy_path(self):
        client = FakeClient([reply("日记账分录", "库存移动单")])
        result = translate_entries(
            ["Journal Entry", "Stock Entry"], CONFIG, glossary=GLOSSARY, client=client
        )
        self.assertEqual(
            result.translations,
            {"Journal Entry": "日记账分录", "Stock Entry": "库存移动单"},
        )
        self.assertEqual(result.rejected, {})
        self.assertIn("Mandatory terminology", client.prompts[0])

    def test_batching(self):
        config = {**CONFIG, "batch_size": 2}
        client = FakeClient([reply("一", "二"), reply("三")])
        result = translate_entries(["a", "b", "c"], config, client=client)
        self.assertEqual(len(client.prompts), 2)
        self.assertEqual(result.translations, {"a": "一", "b": "二", "c": "三"})

    def test_placeholder_loss_triggers_a_repair_request(self):
        client = FakeClient(
            [
                reply("无法取消。"),  # drops {0}
                reply("无法取消 {0}。"),
            ]
        )
        result = translate_entries(["Cannot cancel {0}."], CONFIG, client=client)
        self.assertEqual(result.translations, {"Cannot cancel {0}.": "无法取消 {0}。"})
        self.assertEqual(result.repaired, 1)
        self.assertIn("rejected by an automated checker", client.prompts[1])

    def test_entry_is_dropped_when_repair_also_fails(self):
        client = FakeClient([reply("无法取消。"), reply("还是不行")])
        result = translate_entries(["Cannot cancel {0}."], CONFIG, client=client)
        self.assertEqual(result.translations, {})
        self.assertIn("Cannot cancel {0}.", result.rejected)

    def test_terminology_rules_are_applied_to_model_output(self):
        client = FakeClient([reply("报表货币")])
        result = translate_entries(["Reporting Currency"], CONFIG, client=client)
        self.assertEqual(result.translations["Reporting Currency"], "报告货币")

    def test_api_errors_are_reported_not_raised(self):
        client = FakeClient([ApiError("boom"), ApiError("boom"), ApiError("boom")])
        result = translate_entries(
            ["Journal Entry"], CONFIG, client=client, sleeper=lambda _s: None
        )
        self.assertEqual(result.translations, {})
        self.assertIn("Journal Entry", result.rejected)

    def test_retries_transient_failures(self):
        client = FakeClient([ApiError("503"), reply("日记账分录")])
        result = translate_entries(
            ["Journal Entry"], CONFIG, client=client, sleeper=lambda _s: None
        )
        self.assertEqual(result.translations, {"Journal Entry": "日记账分录"})

    def test_duplicates_are_translated_once(self):
        client = FakeClient([reply("仓库")])
        result = translate_entries(["Warehouse", "Warehouse"], CONFIG, client=client)
        self.assertEqual(len(client.prompts), 1)
        self.assertEqual(result.translations, {"Warehouse": "仓库"})

    def test_empty_input_is_a_noop(self):
        result = translate_entries([], CONFIG, client=FakeClient([]))
        self.assertEqual(result.translations, {})
