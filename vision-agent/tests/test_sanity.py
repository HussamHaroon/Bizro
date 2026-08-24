"""Price-sanity logic: price_anomaly, total_mismatch, duplicate_suspect,
and the single-flag precedence — all pure functions over schema §1 dicts."""

from __future__ import annotations

from vision_agent.sanity import (
    check_duplicate_suspect,
    check_price_anomaly,
    check_total_mismatch,
    evaluate_flags,
)
from vision_agent.schemas import ExtractedItem, ReceiptExtraction

HISTORY = [
    {
        "kind": "expense",
        "amount_pkd": 2560,
        "counterparty": {"name": "Al-Madina Kiryana Store", "phone": None},
        "item_lines": [
            {"item": "chai patti", "qty": 2, "unit": "packet", "unit_price": 350, "line_total": 700},
            {"item": "cheeni", "qty": 5, "unit": "kg", "unit_price": 180, "line_total": 900},
        ],
        "occurred_at": "2026-08-18T10:00:00+05:00",
        "status": "confirmed",
    },
    {
        "kind": "sale",  # sales never contribute price history
        "amount_pkd": 400,
        "item_lines": [{"item": "chai patti", "qty": 1, "unit": "packet", "unit_price": 400}],
        "occurred_at": "2026-08-19T10:00:00+05:00",
        "status": "confirmed",
    },
]


def extraction(items: list[tuple[str, float, float]], stated: float | None) -> ReceiptExtraction:
    return ReceiptExtraction(
        is_receipt=True,
        supplier_name="Al-Madina Kiryana Store",
        items=[
            ExtractedItem(item=name, qty=qty, unit_price=price) for name, qty, price in items
        ],
        stated_total=stated,
        self_confidence=0.9,
    )


class TestPriceAnomaly:
    def test_ten_fold_increase_flags(self):
        detail = check_price_anomaly(
            [{"item": "chai patti", "qty": 2, "unit_price": 3500}],
            HISTORY,
            ratio_threshold=0.25,
            min_samples=1,
            window=5,
        )
        assert detail is not None and detail.kind == "price_anomaly"
        assert detail.data["historical_median"] == 350
        assert detail.data["unit_price"] == 3500

    def test_small_variation_does_not_flag(self):
        detail = check_price_anomaly(
            [{"item": "chai patti", "qty": 2, "unit_price": 360}],  # ~3% off 350
            HISTORY,
            ratio_threshold=0.25,
            min_samples=1,
            window=5,
        )
        assert detail is None

    def test_no_history_does_not_flag(self):
        detail = check_price_anomaly(
            [{"item": "sabun", "qty": 1, "unit_price": 99999}],
            HISTORY,
            ratio_threshold=0.25,
            min_samples=1,
            window=5,
        )
        assert detail is None

    def test_fuzzy_item_match_case_and_spacing_insensitive(self):
        detail = check_price_anomaly(
            [{"item": "  Chai Patti ", "qty": 2, "unit_price": 3500}],
            HISTORY,
            ratio_threshold=0.25,
            min_samples=1,
            window=5,
        )
        assert detail is not None

    def test_dissimilar_item_is_not_matched(self):
        detail = check_price_anomaly(
            [{"item": "chai patti extra special premium gold", "qty": 2, "unit_price": 3500}],
            HISTORY,
            ratio_threshold=0.25,
            min_samples=1,
            window=5,
        )
        assert detail is None  # <0.8 similarity -> no history for this item


class TestTotalMismatch:
    def test_real_mismatch_flags(self):
        ext = extraction([("chai patti", 2, 350)], stated=800)  # lines sum 700
        detail = check_total_mismatch(ext, tolerance_pkd=1.0)
        assert detail is not None and detail.kind == "total_mismatch"
        assert detail.data == {"stated_total": 800, "computed_total": 700}

    def test_within_one_rupee_does_not_flag(self):
        ext = extraction([("chai patti", 2, 350)], stated=700.5)
        assert check_total_mismatch(ext, tolerance_pkd=1.0) is None

    def test_missing_stated_total_does_not_flag(self):
        ext = extraction([("chai patti", 2, 350)], stated=None)
        assert check_total_mismatch(ext, tolerance_pkd=1.0) is None


class TestDuplicateSuspect:
    def test_same_supplier_amount_within_window_flags(self):
        detail = check_duplicate_suspect(
            "Al-Madina Kiryana Store",
            2560,
            "2026-08-18T10:20:00+05:00",  # 20 min after HISTORY[0]
            HISTORY,
            window_minutes=30,
        )
        assert detail is not None and detail.kind == "duplicate_suspect"
        assert detail.data["minutes_apart"] == 20.0

    def test_outside_window_does_not_flag(self):
        detail = check_duplicate_suspect(
            "Al-Madina Kiryana Store",
            2560,
            "2026-08-18T12:00:00+05:00",  # 2 h later
            HISTORY,
            window_minutes=30,
        )
        assert detail is None

    def test_different_amount_does_not_flag(self):
        detail = check_duplicate_suspect(
            "Al-Madina Kiryana Store",
            2561,
            "2026-08-18T10:20:00+05:00",
            HISTORY,
            window_minutes=30,
        )
        assert detail is None

    def test_different_supplier_does_not_flag(self):
        detail = check_duplicate_suspect(
            "Bismillah Store",
            2560,
            "2026-08-18T10:20:00+05:00",
            HISTORY,
            window_minutes=30,
        )
        assert detail is None


class TestEvaluateFlags:
    def settings_kwargs(self):
        return dict(
            ratio_threshold=0.25,
            min_samples=1,
            history_window=5,
            total_tolerance_pkd=1.0,
            duplicate_window_minutes=30,
        )

    def test_precedence_low_confidence_wins(self):
        # stated 2560 matches HISTORY[0] amount+supplier (duplicate), lines sum
        # 7000 != 2560 (total_mismatch), chai 3500 vs 350 (price_anomaly).
        ext = extraction([("chai patti", 2, 3500)], stated=2560)
        flag, details = evaluate_flags(
            True, ext, HISTORY, "Al-Madina Kiryana Store", 2560,
            "2026-08-18T10:20:00+05:00", **self.settings_kwargs(),
        )
        kinds = {d.kind for d in details}
        assert kinds == {"price_anomaly", "total_mismatch", "duplicate_suspect"}
        assert flag == "low_confidence"

    def test_precedence_total_mismatch_over_price_anomaly(self):
        ext = extraction([("chai patti", 2, 3500)], stated=9999)
        flag, _ = evaluate_flags(
            False, ext, HISTORY, "Al-Madina Kiryana Store", 9999,
            "2026-08-25T10:00:00+05:00", **self.settings_kwargs(),
        )
        assert flag == "total_mismatch"

    def test_clean_history_clean_receipt_flags_none(self):
        ext = extraction([("chai patti", 2, 350), ("cheeni", 5, 180)], stated=1600)
        flag, details = evaluate_flags(
            False, ext, HISTORY, "Al-Madina Kiryana Store", 1600,
            "2026-08-25T10:00:00+05:00", **self.settings_kwargs(),
        )
        assert flag == "none"
        assert details == []
