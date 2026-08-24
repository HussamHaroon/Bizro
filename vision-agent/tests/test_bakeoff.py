"""Bake-off harness: scoring math, PENDING honesty, and report generation.
No network, no fabricated numbers — synthetic runs are constructed explicitly."""

from __future__ import annotations

from pathlib import Path

from vision_agent.adapters import OcrResult
from vision_agent.bakeoff import (
    ReceiptRun,
    build_report,
    classify_total,
    digit_errors,
    match_items,
    run_bakeoff,
    score_against_ground_truth,
    worst_case,
)
from vision_agent.config import Settings
from vision_agent.schemas import ExtractedItem, ReceiptExtraction

GT = {
    "receipt1.jpg": {
        "supplier": "Al-Madina Kiryana Store",
        "items": [
            {"item": "chai patti", "qty": 2, "unit_price": 350},
            {"item": "cheeni", "qty": 5, "unit_price": 180},
        ],
        "total": 1600,
    }
}


def make_result(
    *, is_receipt=True, items=None, stated=None, self_confidence=0.9, error=None
) -> OcrResult:
    return OcrResult(
        model="qwen-vl-ocr",
        extraction=ReceiptExtraction(
            is_receipt=is_receipt,
            supplier_name="Al-Madina Kiryana Store",
            items=[ExtractedItem(**item) for item in (items or [])],
            stated_total=stated,
            self_confidence=self_confidence,
        ),
        raw_text="{}",
        mock=False,
        error=error,
        timing_ms=123.0,
    )


class TestScoringPrimitives:
    def test_digit_errors(self):
        assert digit_errors(350, 350) == 0
        assert digit_errors(350, 360) == 1   # 350 vs 360 -> one substitution
        assert digit_errors(350, 35) == 1    # deletion
        assert digit_errors(350, None) == 99

    def test_match_items_fuzzy_and_extras(self):
        gt = [{"item": "chai patti", "qty": 2, "unit_price": 350}]
        extracted = [
            {"item": "Chai Patti", "qty": 2, "unit_price": 350},
            {"item": "sabun", "qty": 1, "unit_price": 60},
        ]
        scores, extras = match_items(gt, extracted)
        assert scores[0].matched is True and scores[0].price_digit_errors == 0
        assert extras == 1  # sabun has no GT counterpart -> hallucinated

    def test_classify_total(self):
        assert classify_total(1600, 1600) == "exact"
        assert classify_total(1601, 1600) == "near"
        assert classify_total(1700, 1600) == "wrong"
        assert classify_total(None, 1600) == "missing"
        assert classify_total(1600, None) == "n/a"

    def test_worst_case_ladder(self):
        assert worst_case(False, False, 0, 0, 0, "exact") == "crash/parse-failure"
        assert worst_case(True, True, 0, 0, 0, "exact") == "rejected-a-real-receipt"
        assert worst_case(True, False, 1, 0, 0, "exact") == "missed-1-item(s)"
        assert worst_case(True, False, 0, 2, 0, "exact") == "hallucinated-2-item(s)"
        assert worst_case(True, False, 0, 0, 1, "exact") == "digit-error"
        assert worst_case(True, False, 0, 0, 0, "missing") == "total-missing"
        assert worst_case(True, False, 0, 0, 0, "exact") == ""


class TestScoreAgainstGroundTruth:
    def test_perfect_read_scores_clean(self):
        result = make_result(
            items=[
                {"item": "chai patti", "qty": 2, "unit_price": 350},
                {"item": "cheeni", "qty": 5, "unit_price": 180},
            ],
            stated=1600,
        )
        score = score_against_ground_truth("receipt1.jpg", "vl", "qwen-vl-ocr", result, GT["receipt1.jpg"])
        assert score.item_name_accuracy == 1.0
        assert score.digit_error_items == 0
        assert score.total_category == "exact"
        assert score.failure == ""

    def test_digit_error_and_wrong_total(self):
        result = make_result(
            items=[
                {"item": "chai patti", "qty": 2, "unit_price": 380},  # 350 -> 380
                {"item": "cheeni", "qty": 5, "unit_price": 180},
            ],
            stated=1700,
        )
        score = score_against_ground_truth("receipt1.jpg", "vl", "qwen-vl-ocr", result, GT["receipt1.jpg"])
        assert score.digit_error_items == 1
        assert score.digit_error_total == 1  # 350 -> 380 is one substitution
        assert score.total_category == "wrong"
        assert score.failure == "digit-error"  # digits rank above total


class TestPendingHonesty:
    def test_no_samples_writes_pending(self, tmp_path):
        out = tmp_path / "bakeoff.md"
        code = run_bakeoff(Settings(dashscope_api_key="sk-test"), sample_dir=tmp_path / "empty", out_path=out)
        report = out.read_text(encoding="utf-8")
        assert code == 0
        assert "STATUS: PENDING" in report
        assert "waiting on real receipt photos" in report
        assert "OCR bake-off" in report  # sane header
        assert "qwen-vl-ocr" in report and "qwen3.5-ocr" in report

    def test_samples_but_no_key_writes_pending(self, tmp_path):
        samples = tmp_path / "receipts"
        samples.mkdir()
        (samples / "r1.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")
        out = tmp_path / "bakeoff.md"
        code = run_bakeoff(Settings(), sample_dir=samples, out_path=out)
        report = out.read_text(encoding="utf-8")
        assert code == 0
        assert "PENDING" in report
        assert "DASHSCOPE_API_KEY" in report
        # and crucially: no fabricated per-receipt results
        assert "r1.jpg" not in report.split("## Per-receipt")[1]

    def test_mock_always_never_runs(self, tmp_path):
        samples = tmp_path / "receipts"
        samples.mkdir()
        (samples / "r1.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")
        out = tmp_path / "bakeoff.md"
        code = run_bakeoff(
            Settings(dashscope_api_key="sk-x", mock_mode="always"), sample_dir=samples, out_path=out
        )
        assert code == 0
        assert "MOCK_MODE=always" in out.read_text(encoding="utf-8")


class TestReportWithGroundTruth:
    def test_verdict_names_a_winner(self):
        good = make_result(
            items=[
                {"item": "chai patti", "qty": 2, "unit_price": 350},
                {"item": "cheeni", "qty": 5, "unit_price": 180},
            ],
            stated=1600,
        )
        bad = make_result(
            items=[{"item": "chai patti", "qty": 2, "unit_price": 380}],
            stated=None,
        )
        run = ReceiptRun(receipt="receipt1.jpg")
        run.results = {"vl": good, "new": bad}
        run.scores = {
            "vl": score_against_ground_truth("receipt1.jpg", "vl", "qwen-vl-ocr", good, GT["receipt1.jpg"]),
            "new": score_against_ground_truth("receipt1.jpg", "new", "qwen3.5-ocr", bad, GT["receipt1.jpg"]),
        }
        report = build_report(Settings(dashscope_api_key="sk-test"), [run], GT, None, Path("samples"))
        assert "STATUS: COMPLETE" in report
        assert "receipt1.jpg" in report
        assert "Suggested winner: `vl`" in report
        # verbatim OCR outputs are included for auditability
        assert "Raw model output" in report
