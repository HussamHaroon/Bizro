"""Parsing layer: fence stripping, balanced-brace scan, tolerant numbers,
unreadable-line dropping, and the repair-retry loop."""

from __future__ import annotations

import json

import pytest

from vision_agent.parsing import ExtractionParseError, extract_json_block, parse_extraction, parse_with_repair
from vision_agent.schemas import ReceiptExtraction

VALID = """{
  "is_receipt": true,
  "supplier_name": "Al-Madina Kiryana Store",
  "items": [
    {"item": "chai patti", "qty": 2, "unit": "packet", "unit_price": 350}
  ],
  "stated_total": 700,
  "unclear_parts": [],
  "self_confidence": 0.9
}"""


class TestExtractJsonBlock:
    def test_plain_json(self):
        assert json.loads(extract_json_block(VALID))["is_receipt"] is True

    def test_fenced_json(self):
        assert json.loads(extract_json_block(f"```json\n{VALID}\n```"))["stated_total"] == 700

    def test_bare_fence(self):
        assert json.loads(extract_json_block(f"```\n{VALID}\n```"))["is_receipt"] is True

    def test_leading_prose(self):
        text = "Here is the extraction you asked for:\n" + VALID
        assert json.loads(extract_json_block(text))["is_receipt"] is True

    def test_braces_inside_strings_do_not_break_balance(self):
        text = '{"supplier_name": "store {x}", "items": [], "stated_total": null}'
        assert extract_json_block(text) == text

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            extract_json_block("   ")

    def test_no_object_raises(self):
        with pytest.raises(ValueError):
            extract_json_block("sorry, I cannot read this image")

    def test_unbalanced_raises(self):
        with pytest.raises(ValueError):
            extract_json_block('{"items": [ {"item": "chai"')


class TestParseExtraction:
    def test_valid_document(self):
        extraction = parse_extraction(f"```json\n{VALID}\n```")
        assert extraction.is_receipt
        assert extraction.supplier_name == "Al-Madina Kiryana Store"
        assert extraction.items[0].unit_price == 350
        assert extraction.stated_total == 700

    def test_currency_strings_coerced(self):
        data = {
            "is_receipt": True,
            "items": [{"item": "cheeni", "qty": "5", "unit_price": "Rs 180"}],
            "stated_total": "900",
            "self_confidence": "0.8",
        }
        extraction = parse_extraction(json.dumps(data))
        assert extraction.items[0].qty == 5
        assert extraction.items[0].unit_price == 180
        assert extraction.stated_total == 900

    def test_unreadable_line_dropped_not_guessed(self):
        data = {
            "is_receipt": True,
            "items": [
                {"item": "chai patti", "qty": 2, "unit_price": 350},
                {"item": "??", "qty": 0, "unit_price": 0},  # unreadable line
            ],
            "unclear_parts": ["second line unreadable"],
        }
        extraction = parse_extraction(json.dumps(data))
        assert len(extraction.items) == 1  # bad line dropped, good line kept
        assert any("unreadable item line dropped" in note for note in extraction.unclear_parts)
        assert "second line unreadable" in extraction.unclear_parts

    def test_bad_schema_raises_parse_error(self):
        # Document-level errors (unparseable field at the top level) still
        # raise — that is what triggers the repair-retry loop. Item-level
        # unreadable lines are dropped instead (never guessed).
        data = {"is_receipt": "definitely", "items": []}
        with pytest.raises(ExtractionParseError) as excinfo:
            parse_extraction(json.dumps(data))
        assert excinfo.value.problems  # validation problems carried for repair

    def test_items_wrong_type_raises_parse_error(self):
        with pytest.raises(ExtractionParseError):
            parse_extraction('{"is_receipt": true, "items": {"a": 1}}')

    def test_non_dict_top_level_raises(self):
        with pytest.raises(ExtractionParseError):
            parse_extraction("[1, 2, 3]")


class TestParseWithRepair:
    def test_repair_recovers_and_reports(self):
        bad = '{"is_receipt": true, "items": [], "self_confidence": "high"}'
        responses = [bad, VALID]

        def call(prompt: str) -> str:
            assert "extract" in prompt.lower() or "corrected" in prompt.lower()
            return responses.pop(0)

        extraction, raw, repaired = parse_with_repair(call, repair_retries=1)
        assert isinstance(extraction, ReceiptExtraction)
        assert extraction.stated_total == 700
        assert repaired is True
        assert raw == VALID

    def test_no_repair_when_first_answer_valid(self):
        def call(prompt: str) -> str:
            return VALID

        _, raw, repaired = parse_with_repair(call, repair_retries=1)
        assert repaired is False
        assert raw == VALID

    def test_exhausted_retries_raise(self):
        def call(prompt: str) -> str:
            return "not json at all"

        with pytest.raises(ExtractionParseError):
            parse_with_repair(call, repair_retries=1)
