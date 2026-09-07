#!/usr/bin/env python3
"""Offline accuracy benchmark for Bizro's DETERMINISTIC structuring layers.

WHAT THIS MEASURES (be honest about it):
  Only the deterministic, no-model layers of the Voice Khata pipeline, driven
  by curated transcript fixtures (voice-agent/benchmarks/transcripts.jsonl):

    1. Number normalization   — normalize_spoken_numbers must insert the right
       bracketed digit hints for spoken Urdu / Roman-Urdu numbers, and must be
       NON-DESTRUCTIVE (stripping the hints reproduces the verbatim text —
       the audit transcript is never rewritten).
    2. Amount-signal counting — count_amount_signals must count real
       person-amounts and ignore item quantities.
    3. Person-join counting   — count_person_joins must count the connectors
       that join multi-person clauses (ASCII + Urdu comma, aur/and/or).
    4. Collapse-guard rulings — collapse_suspected must fire when the model
       under-reports people (merged-total protection) and pass a correct
       extraction through untouched.
    5. Validation + confirmation — each fixture's hand-authored, model-shaped
       JSON is run through the pipeline's own `_assemble_all` (the same
       assembly the webhook path uses): schema validation, the
       ambiguous-must-flag guarantee (unclear amount → amount_pkr=null +
       flag=low_confidence, never a guess), the collapse-guard clarification
       on merged outputs, and a non-empty confirmation whose trailing question
       is present.

WHAT THIS DOES NOT MEASURE (the honest part):
  NOT end-to-end model accuracy. ASR quality and the language model's
  extraction accuracy on REAL shop audio are unmeasured here — that needs
  real recorded voice notes and a HUMAN to listen/transcribe/judge
  (transcripts.jsonl fixtures are curated text, not live audio). That
  human-data task is explicitly pending and is the prerequisite for any
  claimed end-to-end accuracy number.

Run:
    BIZRO_OFFLINE=1 .venv/Scripts/python voice-agent/scripts/benchmark_structuring.py
        [--fixtures PATH] [--results PATH] [--stdout]

Exit code 0 iff all floors hold (see FLOORS); CI/regression-friendly. The
pytest suite (voice-agent/tests/test_benchmark.py) asserts the same floors so
a regression fails CI even if nobody re-runs this script.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # voice-agent/
sys.path.insert(0, str(ROOT))

from voice_agent.config import Settings  # noqa: E402
from voice_agent.confirmation import QUESTION, QUESTION_UR  # noqa: E402
from voice_agent.numbers import (  # noqa: E402
    collapse_suspected,
    count_amount_signals,
    count_person_joins,
    normalize_spoken_numbers,
)
from voice_agent.pipeline import _assemble_all  # noqa: E402

BENCHMARKS_DIR = ROOT / "benchmarks"
FIXTURES_PATH = BENCHMARKS_DIR / "transcripts.jsonl"
RESULTS_PATH = BENCHMARKS_DIR / "RESULTS.md"

CATEGORY_ORDER = ["single_entry", "multi_split", "ambiguous_flag", "phonetic_numbers"]

# Regression floors: if a deterministic layer drops below its floor, CI fails.
# multi_split gets 0.90 rather than 1.00 — the collapse-guard heuristic is
# deliberately best-effort (documented in numbers.py) and this floor leaves
# room for honest fixture growth without a false alarm today.
FLOORS: dict[str, float] = {
    "normalization": 1.00,      # hint insertion + non-destructive, ALL fixtures
    "single_entry": 1.00,
    "multi_split": 0.90,
    "ambiguous_flag": 1.00,     # unclear → flag, never a guess: no tolerance
    "phonetic_numbers": 1.00,
    "collapse_guard": 1.00,     # guard rulings on fixtures that declare them
    "overall": 0.90,
}

# Hint tokens are inserted as "span [digits]" — stripping them must restore
# the fixture text byte-for-byte.
_HINT_RE = re.compile(r" ?\[[\d.,]+\]")

_WHEN = dt.datetime(2026, 10, 24, 12, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=5)))


def load_fixtures(path: Path = FIXTURES_PATH) -> list[dict]:
    fixtures: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                fixtures.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{lineno}: bad fixture JSON: {exc}") from exc
    return fixtures


def _check(failures: list[str], fid: str, check: str, ok: bool, detail: str = "") -> None:
    if not ok:
        failures.append(f"{fid}: {check}{(': ' + detail) if detail else ''}")


def run_fixture(fx: dict, settings: Settings) -> list[str]:
    """Run one fixture through the deterministic layers → failure strings."""
    fid = str(fx.get("id") or "?")
    text = str(fx.get("text") or "")
    failures: list[str] = []

    # --- layer 1: number normalization -----------------------------------
    normalized = normalize_spoken_numbers(text)
    for hint in fx.get("expected_hints") or []:
        _check(failures, fid, "normalization.hint", f"[{hint}]" in normalized,
               f"expected [{hint}] in normalized text")
    stripped = _HINT_RE.sub("", normalized)
    _check(failures, fid, "normalization.non_destructive", stripped == text,
           f"stripping hints must reproduce the verbatim text, got {stripped!r}")

    # --- layers 2-3: amount signals + person joins ------------------------
    if "expected_signals" in fx:
        got = count_amount_signals(text)
        _check(failures, fid, "signals", got == fx["expected_signals"],
               f"expected {fx['expected_signals']}, got {got}")
    if "expected_joins" in fx:
        got = count_person_joins(text)
        _check(failures, fid, "joins", got == fx["expected_joins"],
               f"expected {fx['expected_joins']}, got {got}")

    # --- layer 4: collapse-guard rulings ----------------------------------
    for entry_count, expected in fx.get("expected_collapse") or []:
        got = collapse_suspected(text, entry_count)
        _check(failures, fid, f"collapse_guard[n={entry_count}]",
               got is bool(expected),
               f"expected {expected}, got {got}")

    # --- layer 5: validation + flag + confirmation (assembly) -------------
    model_output = fx.get("model_output")
    if model_output:
        model_text = json.dumps(model_output, ensure_ascii=False)
        try:
            txs, reply, _errors = _assemble_all(
                model_text, _WHEN, None, settings, mock=True
            )
        except Exception as exc:  # noqa: BLE001 — a crash IS a bench failure
            failures.append(f"{fid}: assembly crashed: {type(exc).__name__}: {exc}")
            return failures
        _check(failures, fid, "assembly.entries",
               len(txs) == fx.get("expected_entries"),
               f"expected {fx.get('expected_entries')}, got {len(txs)}")
        flags = [t.get("flag") for t in txs]
        _check(failures, fid, "assembly.flags", flags == fx.get("expected_flags"),
               f"expected {fx.get('expected_flags')}, got {flags}")
        amounts = [t.get("amount_pkr") for t in txs]
        expected_amounts = [
            None if a is None else float(a) for a in fx.get("expected_amounts") or []
        ]
        _check(failures, fid, "assembly.amounts", amounts == expected_amounts,
               f"expected {expected_amounts}, got {amounts}")
        if fx.get("expected_guard"):
            note = str((txs[-1] if txs else {}).get("description") or "")
            _check(failures, fid, "assembly.collapse_guard_note",
                   "collapse guard" in note, "guard clarification not appended")
        for t in txs:
            _check(failures, fid, "confirmation.built",
                   bool(str(t.get("confirmation_ur") or "").strip()),
                   f"empty confirmation for entry {t.get('kind')}")
        if txs:
            clean = all(t.get("flag") == "none" for t in txs)
            if clean:
                _check(failures, fid, "confirmation.trailing_question",
                       QUESTION in reply or QUESTION_UR in reply,
                       "clean entries must end with the exact yes/no question")
            else:
                _check(failures, fid, "confirmation.clarification_question",
                       "?" in reply or "؟" in reply,
                       "flagged entries must ask a question, never state a guess")
    return failures


def run_benchmark(fixtures_path: Path = FIXTURES_PATH) -> dict:
    """Run every fixture → structured results (also consumed by the pytest floor test)."""
    fixtures = load_fixtures(fixtures_path)
    settings = Settings()  # direct construction: fully hermetic, no .env/env read

    by_category: dict[str, dict] = {
        cat: {"total": 0, "passed": 0, "failed": []} for cat in CATEGORY_ORDER
    }
    norm: dict = {"total": 0, "passed": 0, "failed": []}
    guard: dict = {"total": 0, "passed": 0, "failed": []}

    for fx in fixtures:
        failures = run_fixture(fx, settings)
        cat = fx.get("category")
        if cat not in by_category:
            raise SystemExit(f"fixture {fx.get('id')}: unknown category {cat!r}")
        bucket = by_category[cat]
        bucket["total"] += 1
        if failures:
            bucket["failed"].extend(failures)
        else:
            bucket["passed"] += 1
        # layer-level buckets cut across categories
        norm_total = 1 + len(fx.get("expected_hints") or [])
        norm["total"] += norm_total
        norm_fail = [f for f in failures if f.startswith(f"{fx.get('id')}: normalization.")]
        norm["failed"].extend(norm_fail)
        norm["passed"] += norm_total - len(norm_fail)
        guard_checks = fx.get("expected_collapse") or []
        if guard_checks:
            guard["total"] += len(guard_checks)
            g_fail = [f for f in failures if ": collapse_guard" in f or ": assembly.collapse_guard_note" in f]
            guard["failed"].extend(g_fail)
            guard["passed"] += len(guard_checks) - len(g_fail)

    categories = {}
    for cat, bucket in by_category.items():
        rate = (bucket["passed"] / bucket["total"]) if bucket["total"] else 0.0
        categories[cat] = {
            "total": bucket["total"], "passed": bucket["passed"],
            "rate": round(rate, 4), "failures": bucket["failed"],
        }
    normalization_rate = (norm["passed"] / norm["total"]) if norm["total"] else 0.0
    guard_rate = (guard["passed"] / guard["total"]) if guard["total"] else 0.0
    overall_total = sum(b["total"] for b in by_category.values())
    overall_passed = sum(b["passed"] for b in by_category.values())
    results = {
        "fixture_count": len(fixtures),
        "categories": categories,
        "layers": {
            "normalization": {"total": norm["total"], "passed": norm["passed"],
                              "rate": round(normalization_rate, 4)},
            "collapse_guard": {"total": guard["total"], "passed": guard["passed"],
                               "rate": round(guard_rate, 4)},
        },
        "overall": {
            "total": overall_total, "passed": overall_passed,
            "rate": round(overall_passed / overall_total, 4) if overall_total else 0.0,
        },
        "floors": FLOORS,
    }
    results["floors_met"] = all(
        results["layers"]["normalization"]["rate"] >= FLOORS["normalization"]
        and results["layers"]["collapse_guard"]["rate"] >= FLOORS["collapse_guard"]
        and results["overall"]["rate"] >= FLOORS["overall"]
        and results["categories"][cat]["rate"] >= FLOORS[cat]
        for cat in CATEGORY_ORDER
    )
    return results


def render_markdown(results: dict, fixtures_path: Path = FIXTURES_PATH) -> str:
    today = dt.date.today().isoformat()
    lines = [
        "# Deterministic structuring accuracy — benchmark results",
        "",
        f"_Generated {today} by `voice-agent/scripts/benchmark_structuring.py` "
        f"from `{fixtures_path.name}` ({results['fixture_count']} fixtures). "
        "Re-run the script to regenerate; floors are asserted in CI by "
        "`voice-agent/tests/test_benchmark.py`._",
        "",
        "## Scope — read this before quoting any number",
        "",
        "This benchmark measures the **deterministic parsing layers only**:",
        "",
        "1. **Number normalization** — spoken Urdu / Roman-Urdu number words →",
        "   bracketed digit hints, with a non-destructiveness invariant",
        "   (stripping hints reproduces the verbatim transcript byte-for-byte).",
        "2. **Amount-signal counting** (item quantities must NOT look like amounts).",
        "3. **Person-join counting** (ASCII + Urdu comma, aur/and/or).",
        "4. **Collapse-guard rulings** — merged-total detection fires on",
        "   under-reported people and passes correct extractions untouched.",
        "5. **Validation + confirmation** — hand-authored model-shaped JSON run",
        "   through the pipeline's real `_assemble_all`: schema validation, the",
        "   ambiguous-must-flag guarantee (unclear amount → `amount_pkr=null` +",
        "   `flag=low_confidence`, never a guess), guard clarifications, and a",
        "   confirmation with the trailing question present.",
        "",
        "**It does NOT measure end-to-end model accuracy.** ASR quality and the",
        "language model's extraction accuracy on real shop audio are unmeasured",
        "here: fixtures are curated transcripts, not live audio, and the",
        "structured outputs paired with them are hand-authored. Measuring that",
        "requires real recorded voice notes and a **human** to listen,",
        "transcribe and judge — a pending task, and the prerequisite for any",
        "end-to-end accuracy claim in pitch or demo material.",
        "",
        "## Category results",
        "",
        "| Category | Fixtures | Passed | Accuracy | Floor | Verdict |",
        "|---|---|---|---|---|---|",
    ]
    for cat in CATEGORY_ORDER:
        c = results["categories"][cat]
        verdict = "PASS" if c["rate"] >= results["floors"][cat] else "FAIL"
        lines.append(
            f"| {cat} | {c['total']} | {c['passed']} | {c['rate'] * 100:.1f}% "
            f"| {results['floors'][cat] * 100:.0f}% | {verdict} |"
        )
    n = results["layers"]["normalization"]
    g = results["layers"]["collapse_guard"]
    o = results["overall"]
    verdict_n = "PASS" if n["rate"] >= results["floors"]["normalization"] else "FAIL"
    verdict_g = "PASS" if g["rate"] >= results["floors"]["collapse_guard"] else "FAIL"
    verdict_o = "PASS" if o["rate"] >= results["floors"]["overall"] else "FAIL"
    lines += [
        f"| normalization (all fixtures) | {n['total']} | {n['passed']} | "
        f"{n['rate'] * 100:.1f}% | {results['floors']['normalization'] * 100:.0f}% | {verdict_n} |",
        f"| collapse-guard rulings | {g['total']} | {g['passed']} | "
        f"{g['rate'] * 100:.1f}% | {results['floors']['collapse_guard'] * 100:.0f}% | {verdict_g} |",
        f"| **Overall** | {o['total']} | {o['passed']} | "
        f"{o['rate'] * 100:.1f}% | {results['floors']['overall'] * 100:.0f}% | {verdict_o} |",
        "",
        "## Methodology",
        "",
        "- {} curated voice-note transcripts ({}), written the way karyana "
        "merchants actually speak: Urdu script and".format(
            results["fixture_count"],
            ", ".join(
                "{}: {}".format(c, results["categories"][c]["total"])
                for c in CATEGORY_ORDER
            ),
        ),
        "  Roman Urdu, numbers as words, code-switched English, multi-person",
        "  notes, ambiguous amounts, ledger queries.",
        "- Each fixture runs through the SAME functions the webhook path uses:",
        "  `normalize_spoken_numbers`, `count_amount_signals`,",
        "  `count_person_joins`, `collapse_suspected`, and `_assemble_all`",
        "  (mock-marked: every assembled row carries `mock: true` and is never",
        "  presentable as real model output).",
        "- Known deterministic limitation (documented, not hidden): the",
        "  collapse guard is a best-effort heuristic — a two-person note whose",
        "  amounts are both small hundreds can produce fewer strong signals",
        "  than persons; the guard then stays silent rather than nagging. It",
        "  NEVER dismisses a suspicion: silence only means no evidence of a",
        "  merged total, and a wrong number still cannot slip through as a",
        "  confirmed entry because every entry is confirmed by the merchant.",
        "",
        "## Failures",
        "",
    ]
    all_failures = [
        f for c in results["categories"].values() for f in c["failures"]
    ]
    if all_failures:
        lines += [f"- {f}" for f in all_failures]
    else:
        lines.append("None — every fixture passed every declared check.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixtures", type=Path, default=FIXTURES_PATH)
    parser.add_argument("--results", type=Path, default=RESULTS_PATH)
    parser.add_argument("--stdout", action="store_true", help="also print the report")
    args = parser.parse_args()

    results = run_benchmark(args.fixtures)
    report = render_markdown(results, args.fixtures)
    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text(report, encoding="utf-8")
    if args.stdout:
        print(report)
    print(
        f"benchmark: {results['fixture_count']} fixtures, overall "
        f"{results['overall']['rate'] * 100:.1f}%, floors met: {results['floors_met']} "
        f"→ {args.results}"
    )
    return 0 if results["floors_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
