"""End-to-end pipeline tests over the four mock scenarios (MOCK_MODE=auto
with no key present). Everything runs the REAL code path — only the model
output is synthetic and clearly labeled (source.model="mock:...", raw_output
contains "mock": true — never presentable as a real run)."""

from __future__ import annotations

import pytest

from tests.fixtures import standard_fixtures
from vision_agent.config import Settings
from vision_agent.pipeline import ReceiptRejected, process_receipt_image
from vision_agent.schemas import TransactionResult

HISTORY = [
    {
        "kind": "expense",
        "amount_pkr": 2560,
        "counterparty": {"name": "Al-Madina Kiryana Store", "phone": None},
        "item_lines": [
            {"item": "chai patti", "qty": 2, "unit": "packet", "unit_price": 350, "line_total": 700},
            {"item": "cheeni", "qty": 5, "unit": "kg", "unit_price": 180, "line_total": 900},
            {"item": "dal masoor", "qty": 3, "unit": "kg", "unit_price": 320, "line_total": 960},
        ],
        "occurred_at": "2026-08-18T10:00:00+05:00",
        "status": "confirmed",
    }
]

OCCURRED = "2026-08-21T19:03:00+05:00"  # 3 days after history: no duplicate


@pytest.fixture()
def images(tmp_path):
    return standard_fixtures(tmp_path)


@pytest.fixture()
def settings():
    # No DASHSCOPE_API_KEY + MOCK_MODE=auto -> mock adapter (Orchestrator D0-3).
    return Settings()


class TestCleanReceipt:
    def test_full_transaction(self, images, settings):
        tx = process_receipt_image(
            images["clean"], merchant="wa:923001234567", occurred_at=OCCURRED,
            history=HISTORY, media_id="uuid-media-1", settings=settings,
        )
        # schema.md §1 conformance is mechanically enforced on the way out
        TransactionResult.model_validate(tx)

        assert tx["kind"] == "expense"
        assert tx["amount_pkr"] == 2560
        assert tx["currency"] == "PKR"
        assert tx["counterparty"] == {"name": "Al-Madina Kiryana Store", "phone": None}
        assert len(tx["item_lines"]) == 3
        assert tx["item_lines"][0] == {
            "item": "chai patti", "qty": 2, "unit": "packet",
            "unit_price": 350, "line_total": 700,
        }
        assert tx["occurred_at"] == OCCURRED
        assert tx["flag"] == "none"
        assert tx["status"] == "pending"  # every entry gets the confirm step (D-V3)
        assert "خرچ درج ہو گیا" in tx["confirmation_ur"]
        assert "2,560" in tx["confirmation_ur"]

    def test_audit_trail_fields(self, images, settings):
        tx = process_receipt_image(images["clean"], occurred_at=OCCURRED, settings=settings)
        source = tx["source"]
        assert source["type"] == "photo"
        assert source["media_id"] is None
        assert source["model"] == "mock:qwen-vl-ocr"  # unmistakable mock (D-V7)
        assert 0.0 <= source["confidence"] <= 1.0
        assert source["confidence"] >= settings.confidence_confirm_threshold
        assert source["raw_output"]["mock"] is True            # labeled synthetic
        assert "model_response_text" in source["raw_output"]    # verbatim OCR kept


class TestBlurryPhoto:
    def test_flags_low_confidence_and_asks(self, images, settings):
        tx = process_receipt_image(
            images["blurry"], occurred_at=OCCURRED, history=HISTORY, settings=settings,
        )
        TransactionResult.model_validate(tx)
        assert tx["flag"] == "low_confidence"
        assert tx["status"] == "pending"
        assert tx["source"]["confidence"] < settings.confidence_confirm_threshold
        assert "تصویر صاف نہیں" in tx["confirmation_ur"]      # honest admission
        assert "دوبارہ بھیجیں" in tx["confirmation_ur"]       # asks for a re-send
        # only the readable line survived; the unreadable one was dropped, not guessed
        assert tx["item_lines"] == [
            {"item": "chai patti", "qty": 2, "unit": "packet",
             "unit_price": 350, "line_total": 700}
        ]
        assert tx["amount_pkr"] == 700  # computed from the one readable line


class TestWrongPriceReceipt:
    def test_price_anomaly_against_history(self, images, settings):
        tx = process_receipt_image(
            images["wrong_price"], occurred_at=OCCURRED, history=HISTORY, settings=settings,
        )
        TransactionResult.model_validate(tx)
        assert tx["flag"] == "price_anomaly"
        chai = next(l for l in tx["item_lines"] if l["item"] == "chai patti")
        assert chai["unit_price"] == 3500
        assert tx["amount_pkr"] == 8860
        assert "تنبیہ" in tx["confirmation_ur"]               # a warning exists
        assert "3,500" in tx["confirmation_ur"] and "350" in tx["confirmation_ur"]

    def test_no_history_means_no_anomaly_possible(self, images, settings):
        tx = process_receipt_image(
            images["wrong_price"], occurred_at=OCCURRED, history=None, settings=settings,
        )
        assert tx["flag"] == "none"


class TestNonReceiptPhoto:
    def test_polite_reject(self, images, settings):
        with pytest.raises(ReceiptRejected) as excinfo:
            process_receipt_image(images["not_receipt"], occurred_at=OCCURRED, settings=settings)
        assert excinfo.value.reason == "not_a_receipt"
        assert "معاف کیجیے گا" in excinfo.value.reply_ur       # polite
        assert "receipt" in excinfo.value.reply_ur             # says what to send


class TestDuplicateSuspectEndToEnd:
    def test_same_receipt_twice_in_window(self, images, settings):
        first = process_receipt_image(
            images["clean"], occurred_at="2026-08-21T19:00:00+05:00",
            history=HISTORY, settings=settings,
        )
        second = process_receipt_image(
            images["clean"], occurred_at="2026-08-21T19:10:00+05:00",
            history=[first], settings=settings,  # the first tx is now "history"
        )
        assert second["flag"] == "duplicate_suspect"
        assert "منٹ پہلے" in second["confirmation_ur"]


class TestSelectionFollowsOcrModelEnv:
    def test_mock_model_reflects_new_selection(self, images):
        tx = process_receipt_image(
            images["clean"], occurred_at=OCCURRED, settings=Settings(ocr_model="new"),
        )
        assert tx["source"]["model"] == "mock:qwen3.5-ocr"
