"""Vision pipeline mock outputs vs the qa-agent schema.md mirror (§1 + §6).

Includes the D0-12 occurred_at check: the Orchestrator patch coerces datetime
inputs to ISO strings — these tests pin whether that weakened validation.
"""

from __future__ import annotations

import datetime as dt

import pytest

from mirror_schema import MirrorTransaction, mock_marker_locations

from vision_agent.adapters import MockOcrAdapter
from vision_agent.config import Settings as VisionSettings
from vision_agent.pipeline import ReceiptRejected, process_receipt_image
from vision_agent.schemas import TransactionResult

VISION_SETTINGS = VisionSettings(mock_mode="always")


def _image(tmp_path, stem: str) -> str:
    p = tmp_path / f"{stem}.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + b"mock-image")
    return str(p)


def _run(tmp_path, stem: str, **kw):
    kw.setdefault("settings", VISION_SETTINGS)
    return process_receipt_image(_image(tmp_path, stem), **kw)


def test_clean_receipt_conforms_to_schema_mirror(tmp_path):
    tx = _run(tmp_path, "clean")  # filename without tokens -> CLEAN scenario
    mirror = MirrorTransaction.model_validate(tx)
    assert mirror.kind == "expense"
    assert mirror.amount_pkr == 2560  # stated total wins (D-V4)
    assert len(mirror.item_lines) == 3
    assert mirror.source.model.startswith("mock:")  # D-V7: mock id prefix
    assert "source.raw_output.mock" in mock_marker_locations(tx)  # §6.3 canonical marker


def test_blurry_receipt_flags_low_confidence_and_never_guesses(tmp_path):
    tx = _run(tmp_path, "blurry")
    mirror = MirrorTransaction.model_validate(tx)
    assert mirror.flag == "low_confidence"
    assert 0 < mirror.amount_pkr == 700  # single readable line only; no guessed digits
    assert mirror.source.confidence < VISION_SETTINGS.confidence_confirm_threshold
    assert mirror.confirmation_ur.strip()


def test_wrong_price_without_history_has_no_anomaly_flag(tmp_path):
    """Price anomaly needs history (min_samples). With none, the entry is simply
    clean — this pins that the flag never fires on a single receipt alone."""
    tx = _run(tmp_path, "wrong_price")
    assert tx["flag"] == "none"
    MirrorTransaction.model_validate(tx)


def test_not_a_receipt_is_rejected_with_polite_urdu(tmp_path):
    with pytest.raises(ReceiptRejected) as excinfo:
        _run(tmp_path, "selfie")
    assert excinfo.value.reason == "not_a_receipt"
    assert excinfo.value.reply_ur.strip()  # polite Urdu reply for WhatsApp


def test_occurred_at_datetime_input_coerced_to_iso_string(tmp_path):
    """The D0-12 patch's purpose: server dispatch passes a tz-aware datetime."""
    when = dt.datetime(2026, 8, 21, 14, 3, tzinfo=dt.timezone.utc)
    tx = _run(tmp_path, "clean", occurred_at=when)
    assert isinstance(tx["occurred_at"], str)
    assert dt.datetime.fromisoformat(tx["occurred_at"]) == when
    MirrorTransaction.model_validate(tx)  # full contract still holds


def test_occurred_at_patch_weakened_string_validation():
    """Current (patched) behavior: ANY string passes — ISO-8601 is no longer
    enforced on the wire field. Documents the weakening for the review."""
    ok = TransactionResult.model_validate(
        {
            "kind": "expense",
            "amount_pkr": 100,
            "occurred_at": "definitely-not-a-timestamp",
            "source": {"type": "photo", "confidence": 0.9},
            "confirmation_ur": "x",
        }
    )
    assert ok.occurred_at == "definitely-not-a-timestamp"  # accepted today


@pytest.mark.xfail(
    reason="F-3 [P2]: the D0-12 occurred_at patch changed datetime->str without "
    "an ISO-8601 format check, so schema.md §6.6's 'ALWAYS the ISO-8601 string' "
    "is no longer enforced at the vision boundary (server still catches it).",
    strict=False,
)
def test_occurred_at_non_iso_string_rejected_per_6_6():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TransactionResult.model_validate(
            {
                "kind": "expense",
                "amount_pkr": 100,
                "occurred_at": "definitely-not-a-timestamp",
                "source": {"type": "photo", "confidence": 0.9},
                "confirmation_ur": "x",
            }
        )


def test_price_anomaly_fires_with_history_pipeline_level(tmp_path):
    """Pipeline-level truth: with history, wrong_price IS caught."""
    history = [
        {
            "kind": "expense",
            "amount_pkr": 2560,
            "item_lines": [{"item": "chai patti", "unit_price": 350}],
            "counterparty": {"name": "Al-Madina Kiryana Store"},
            "occurred_at": "2026-08-20T10:00:00+00:00",
            "status": "confirmed",
        }
    ]
    tx = _run(tmp_path, "wrong_price", history=history)
    assert tx["flag"] == "price_anomaly"


@pytest.mark.xfail(
    reason="F-4 [P1]: server dispatch never passes `history` to "
    "process_receipt_image (dispatch.py:104 calls fn with path/merchant/"
    "occurred_at only), so price_anomaly/duplicate_suspect can never fire on "
    "the WhatsApp path — verified end-to-end in test_webhook_contract.py.",
    strict=False,
)
def test_price_anomaly_fires_through_server_dispatch(tmp_path):
    """Same receipt, same history, but via dispatch's real call signature."""
    import inspect
    from server.app import dispatch

    src = inspect.getsource(dispatch.process_receipt_image)
    assert "history" in src  # dispatch threads history to the pipeline
