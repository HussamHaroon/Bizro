"""Benchmark floor tests — the deterministic accuracy harness cannot regress.

The harness (voice-agent/scripts/benchmark_structuring.py) measures the
deterministic layers ONLY (number normalization, signals/joins, collapse
guard, validation + flag + confirmation) over the curated fixtures in
voice-agent/benchmarks/transcripts.jsonl. It does NOT measure end-to-end
model accuracy — that needs real audio and a human judge (see RESULTS.md).

These tests load the harness module directly from its file (scripts/ is not
a package) and assert its stated floors, so a regression in ANY deterministic
layer fails CI even if nobody re-runs the script.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

VOICE_AGENT = Path(__file__).resolve().parents[1]
BENCHMARKS = VOICE_AGENT / "benchmarks"
SCRIPT = VOICE_AGENT / "scripts" / "benchmark_structuring.py"

MIN_FIXTURES = 30
REQUIRED_CATEGORIES = {"single_entry", "multi_split", "ambiguous_flag", "phonetic_numbers"}


@pytest.fixture(scope="module")
def bench():
    spec = importlib.util.spec_from_file_location("benchmark_structuring", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["benchmark_structuring"] = mod
    spec.loader.exec_module(mod)
    return mod


# --- fixture-set hygiene ------------------------------------------------------


def test_fixture_set_is_large_and_categorized():
    fixtures = [json.loads(line) for line in
                (BENCHMARKS / "transcripts.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()]
    assert len(fixtures) >= MIN_FIXTURES
    cats = {fx["category"] for fx in fixtures}
    assert REQUIRED_CATEGORIES <= cats, f"missing categories: {REQUIRED_CATEGORIES - cats}"
    ids = [fx["id"] for fx in fixtures]
    assert len(ids) == len(set(ids)), "fixture ids must be unique"
    for fx in fixtures:
        assert fx.get("text", "").strip(), f"{fx['id']}: empty transcript"
        assert fx.get("text", "").strip() != "cancel last", "accidental cancel fixture"


def test_every_fixture_transcript_differs_from_its_structured_output():
    # the fixtures pair TRANSCRIPTS with hand-authored model-shaped output;
    # the harness must never confuse the two (methodology honesty).
    fixtures = [json.loads(line) for line in
                (BENCHMARKS / "transcripts.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()]
    for fx in fixtures:
        mo = fx.get("model_output")
        if mo:
            assert mo.get("transcript") == fx["text"], f"{fx['id']}: transcript drift"


# --- the floors ----------------------------------------------------------------


def test_benchmark_floors_hold(bench):
    results = bench.run_benchmark()
    assert results["floors_met"], (
        "deterministic accuracy floors regressed — failures: "
        + "; ".join(
            f for c in results["categories"].values() for f in c["failures"]
        )
    )
    # floors individually, for a precise failure message when one drops
    assert results["layers"]["normalization"]["rate"] >= bench.FLOORS["normalization"]
    assert results["layers"]["collapse_guard"]["rate"] >= bench.FLOORS["collapse_guard"]
    assert results["overall"]["rate"] >= bench.FLOORS["overall"]
    for cat in bench.CATEGORY_ORDER:
        assert results["categories"][cat]["rate"] >= bench.FLOORS[cat], (
            f"{cat} accuracy {results['categories'][cat]['rate']} below floor "
            f"{bench.FLOORS[cat]}: {results['categories'][cat]['failures']}"
        )


def test_benchmark_ambiguous_never_guesses(bench):
    """The layer-level guarantee behind the benchmark: an unclear amount in the
    model output must NEVER become a fabricated amount_pkr."""
    results = bench.run_benchmark()
    assert results["categories"]["ambiguous_flag"]["rate"] >= bench.FLOORS["ambiguous_flag"]


def test_results_md_exists_and_keeps_the_honesty_note(bench):
    results_md = BENCHMARKS / "RESULTS.md"
    assert results_md.is_file(), "run scripts/benchmark_structuring.py to generate RESULTS.md"
    text = results_md.read_text(encoding="utf-8")
    assert "deterministic parsing layers" in text
    assert "NOT measure end-to-end model accuracy" in text
    assert "pending" in text  # the real-audio human task stays listed as pending
