"""OCR bake-off: Qwen-VL-OCR vs Qwen3.5-OCR on the REAL sample receipts.

Run:  cd vision-agent && python -m vision_agent.bakeoff
(Requires DASHSCOPE_API_KEY + photos in samples/receipts/ — HANDOFF.md ①③.)

The bake-off decides the winning model, not vibes (design.md §2, §9;
AGENTS.md vision-agent). This harness:

- runs BOTH adapters over every image in samples/receipts/,
- scores each against optional human ground truth
  (samples/receipts/ground_truth.json, see README),
- writes vision-agent/ocr-bakeoff.md INCLUDING the verbatim OCR outputs,
- never fabricates numbers: with no samples, no key, or no ground truth it
  writes an honest PENDING state and exits 0 (so orchestrators can run it
  unattended the moment photos + key land).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vision_agent.adapters import OcrResult, Qwen35OcrAdapter, QwenVlOcrAdapter
from vision_agent.config import Settings, default_settings, load_settings
from vision_agent.sanity import normalize_name, similar

VISION_AGENT_DIR = Path(__file__).resolve().parents[1]  # <root>/vision-agent
REPO_ROOT = Path(__file__).resolve().parents[2]  # worktree root
DEFAULT_SAMPLES = REPO_ROOT / "samples" / "receipts"
DEFAULT_OUT = VISION_AGENT_DIR / "ocr-bakeoff.md"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

SIMILARITY = 0.8  # item-name match threshold (same as sanity.py)


# ----------------------------------------------------------------- utilities


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a or not b:
        return max(len(a), len(b))
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def digit_errors(a: float | int | None, b: float | int | None) -> int:
    """Levenshtein distance between the plain digit strings of two numbers."""
    if a is None or b is None:
        return 99
    sa = f"{a:g}".replace(".", "").replace("-", "")
    sb = f"{b:g}".replace(".", "").replace("-", "")
    return _levenshtein(sa, sb)


@dataclass
class ItemScore:
    gt_item: str
    matched: bool
    qty_digit_errors: int = 0
    price_digit_errors: int = 0


@dataclass
class ReceiptScore:
    receipt: str
    adapter: str
    model: str
    ok: bool  # call + parse succeeded
    failure: str  # worst-case failure category ("" when none)
    item_name_accuracy: float | None = None
    matched_items: int = 0
    gt_items: int = 0
    extra_items: int = 0
    digit_error_items: int = 0
    digit_error_total: int = 0
    total_category: str = "n/a"  # exact | near | wrong | missing | n/a
    timing_ms: float | None = None


@dataclass
class ReceiptRun:
    receipt: str
    results: dict[str, OcrResult] = field(default_factory=dict)
    scores: dict[str, ReceiptScore] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


# ------------------------------------------------------------------ scoring


def match_items(
    gt_items: list[dict[str, Any]], extracted_items: list[dict[str, Any]]
) -> tuple[list[ItemScore], int]:
    """Greedy fuzzy name matching GT→extracted; returns scores + extras count."""
    remaining = list(range(len(extracted_items)))
    scores: list[ItemScore] = []
    for gt in gt_items:
        best_index, best_ratio = None, 0.0
        for index in remaining:
            ratio = similar(str(gt.get("item", "")), str(extracted_items[index].get("item", "")))
            if ratio > best_ratio:
                best_index, best_ratio = index, ratio
        if best_index is not None and best_ratio >= SIMILARITY:
            ex = extracted_items[best_index]
            remaining.remove(best_index)
            scores.append(
                ItemScore(
                    gt_item=str(gt.get("item", "")),
                    matched=True,
                    qty_digit_errors=digit_errors(gt.get("qty"), ex.get("qty")),
                    price_digit_errors=digit_errors(gt.get("unit_price"), ex.get("unit_price")),
                )
            )
        else:
            scores.append(ItemScore(gt_item=str(gt.get("item", "")), matched=False))
    return scores, len(remaining)


def classify_total(stated: float | None, gt_total: float | None) -> str:
    if gt_total is None:
        return "n/a"
    if stated is None:
        return "missing"
    if abs(stated - gt_total) < 1e-9:
        return "exact"
    if abs(stated - gt_total) <= max(1.0, gt_total * 0.005):
        return "near"
    return "wrong"


def worst_case(
    ok: bool,
    false_reject: bool,
    missed: int,
    extra: int,
    digit_error_items: int,
    total_category: str,
) -> str:
    """Severity ladder, highest first (per-receipt worst-case failure mode)."""
    if not ok:
        return "crash/parse-failure"
    if false_reject:
        return "rejected-a-real-receipt"
    if missed > 0:
        return f"missed-{missed}-item(s)"
    if extra > 0:
        return f"hallucinated-{extra}-item(s)"
    if digit_error_items > 0:
        return "digit-error"
    if total_category in {"wrong", "missing"}:
        return f"total-{total_category}"
    return ""


def score_against_ground_truth(
    receipt: str, adapter: str, model: str, result: OcrResult, gt: dict[str, Any]
) -> ReceiptScore:
    gt_items = [x for x in gt.get("items", []) if isinstance(x, dict)]
    ex_items = [x.model_dump() for x in result.extraction.items]
    item_scores, extras = match_items(gt_items, ex_items)
    matched = sum(1 for s in item_scores if s.matched)
    digit_items = sum(
        1
        for s in item_scores
        if s.matched and (s.qty_digit_errors > 0 or s.price_digit_errors > 0)
    )
    digit_total = sum(
        s.qty_digit_errors + s.price_digit_errors
        for s in item_scores
        if s.matched
    )
    total_cat = classify_total(result.extraction.stated_total, gt.get("total"))
    accuracy = round(matched / len(gt_items), 3) if gt_items else None
    failure = worst_case(
        ok=result.error is None,
        false_reject=(not result.extraction.is_receipt),
        missed=len(gt_items) - matched,
        extra=extras,
        digit_error_items=digit_items,
        total_category=total_cat,
    )
    return ReceiptScore(
        receipt=receipt,
        adapter=adapter,
        model=model,
        ok=result.error is None,
        failure=failure,
        item_name_accuracy=accuracy,
        matched_items=matched,
        gt_items=len(gt_items),
        extra_items=extras,
        digit_error_items=digit_items,
        digit_error_total=digit_total,
        total_category=total_cat,
        timing_ms=result.timing_ms,
    )


def score_no_ground_truth(
    receipt: str, adapter: str, model: str, result: OcrResult
) -> ReceiptScore:
    failure = ""
    if result.error is not None:
        failure = "crash/parse-failure"
    elif not result.extraction.is_receipt:
        failure = "not-a-receipt (no GT to confirm)"
    return ReceiptScore(
        receipt=receipt,
        adapter=adapter,
        model=model,
        ok=result.error is None,
        failure=failure,
        gt_items=0,
        total_category="n/a",
        timing_ms=result.timing_ms,
    )


# ------------------------------------------------------------------- report


def _fence(text: str, language: str = "") -> str:
    body = text if (not text or text.endswith("\n")) else text + "\n"
    return f"```{language}\n{body}```"


def build_report(
    settings: Settings,
    runs: list[ReceiptRun],
    ground_truth: dict[str, Any] | None,
    pending_reason: str | None,
    sample_dir: Path,
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []
    lines.append("# OCR bake-off — Qwen-VL-OCR vs Qwen3.5-OCR")
    lines.append("")
    if pending_reason:
        lines.append(f"> **STATUS: PENDING — {pending_reason}**")
        lines.append(">")
        lines.append("> No numbers below are real model results. This file is")
        lines.append("> regenerated automatically the moment the missing input lands;")
        lines.append("> nothing here is hand-written or fabricated (SKILL.md hard rule).")
        lines.append("")
    else:
        lines.append("> STATUS: COMPLETE — real model calls on real photos, outputs verbatim below.")
        lines.append("")
    lines.append(f"Generated: {now} · `python -m vision_agent.bakeoff`")
    lines.append(
        f"Models: `{settings.model_ocr_vl}` (adapter `vl`) vs `{settings.model_ocr_new}` "
        f"(adapter `new`) · endpoint: `{settings.dashscope_base_url}`"
    )
    lines.append(
        f"Samples dir: `{sample_dir}` · receipts run: {len(runs)} · "
        f"ground truth: {'yes' if ground_truth else 'NO (transcribe-only mode)'}"
    )
    lines.append("")
    lines.append("Decision rule (design.md §2/§9): the winner becomes `OCR_MODEL=vl|new` —")
    lines.append("both adapters stay in the codebase, so the choice stays reversible.")
    lines.append("")

    # ---- score table ----
    lines.append("## Scores")
    lines.append("")
    if not runs:
        lines.append("_No receipts to score yet._")
    elif not ground_truth:
        lines.append(
            "No `ground_truth.json` found next to the photos — scoring is DISABLED\n"
            "(transcribe-only mode: outputs below await human scoring). To enable:\n"
            "create `samples/receipts/ground_truth.json` mapping each filename to\n"
            "`{\"supplier\", \"items\": [{\"item\", \"qty\", \"unit_price\"}], \"total\"}`\n"
            "then re-run the bake-off."
        )
    else:
        lines.append("| Adapter | Model | Item-name accuracy | Digit-error items | Digit errors (Σ) | Total (exact/near/wrong/missing) | Worst-case failures |")
        lines.append("|---|---|---|---|---|---|---|")
        for adapter in ("vl", "new"):
            scores = [run.scores[adapter] for run in runs if adapter in run.scores]
            if not scores:
                continue
            n_receipts = len(scores)
            acc_values = [s.item_name_accuracy for s in scores if s.item_name_accuracy is not None]
            avg_acc = f"{sum(acc_values) / len(acc_values):.0%}" if acc_values else "n/a"
            digit_items = sum(s.digit_error_items for s in scores)
            digit_sum = sum(s.digit_error_total for s in scores)
            totals = {
                cat: sum(1 for s in scores if s.total_category == cat)
                for cat in ("exact", "near", "wrong", "missing")
            }
            failures = sum(1 for s in scores if s.failure)
            lines.append(
                f"| `{adapter}` | `{scores[0].model}` | {avg_acc} avg | "
                f"{digit_items}/{sum(s.gt_items for s in scores)} items | {digit_sum} | "
                f"{totals['exact']}/{totals['near']}/{totals['wrong']}/{totals['missing']} | "
                f"{failures}/{n_receipts} receipts |"
            )
    lines.append("")

    # ---- per-receipt detail ----
    lines.append("## Per-receipt results (verbatim OCR outputs — auditable)")
    lines.append("")
    if not runs:
        lines.append("_No receipts found._")
        lines.append("")
    for run in runs:
        lines.append(f"### {run.receipt}")
        lines.append("")
        for adapter in ("vl", "new"):
            result = run.results.get(adapter)
            score = run.scores.get(adapter)
            if result is None:
                error = run.errors.get(adapter, "not run")
                lines.append(f"#### `{adapter}` — FAILED")
                lines.append("")
                lines.append(_fence(error or "unknown error"))
                lines.append("")
                continue
            model = result.model
            status = "ok" if result.error is None else f"error: {result.error}"
            timing = f"{result.timing_ms:.0f} ms" if result.timing_ms is not None else "n/a"
            lines.append(f"#### `{adapter}` (`{model}`) — {status} · {timing}")
            lines.append("")
            if score is not None and ground_truth:
                lines.append(
                    f"items matched {score.matched_items}/{score.gt_items}"
                    + (f" · +{score.extra_items} extra" if score.extra_items else "")
                    + f" · total: {score.total_category}"
                    + (f" · worst-case: {score.failure}" if score.failure else " · worst-case: none")
                )
                lines.append("")
            lines.append("Raw model output:")
            lines.append("")
            lines.append(_fence(result.raw_text))
            lines.append("")
        lines.append("---")
        lines.append("")

    # ---- verdict ----
    lines.append("## Verdict")
    lines.append("")
    if pending_reason:
        lines.append("PENDING — no verdict until real samples + key exist and the")
        lines.append("bake-off has actually run. `OCR_MODEL` default remains `vl`.")
    elif not ground_truth:
        lines.append("TRANScribe-only — outputs above need human ground truth before")
        lines.append("any winner is declared. Do not set `OCR_MODEL` from vibes.")
    else:
        vl = [run.scores["vl"] for run in runs if "vl" in run.scores]
        new = [run.scores["new"] for run in runs if "new" in run.scores]

        def quality(scores: list[ReceiptScore]) -> tuple[int, float, int]:
            """(worst-case failure count, avg item-name accuracy, Σ digit errors)"""
            failures = sum(1 for s in scores if s.failure)
            accs = [s.item_name_accuracy if s.item_name_accuracy is not None else 0.0 for s in scores]
            avg_acc = sum(accs) / len(accs) if accs else 0.0
            return failures, avg_acc, sum(s.digit_error_total for s in scores)

        vl_fail, vl_acc, vl_digits = quality(vl)
        new_fail, new_acc, new_digits = quality(new)
        lines.append(
            f"`vl`: {vl_fail} worst-case receipts, item accuracy {vl_acc:.0%}, "
            f"{vl_digits} digit errors · "
            f"`new`: {new_fail} worst-case receipts, item accuracy {new_acc:.0%}, "
            f"{new_digits} digit errors"
        )
        if vl_fail != new_fail:
            winner = "vl" if vl_fail < new_fail else "new"
        elif vl_digits != new_digits:
            winner = "vl" if vl_digits < new_digits else "new"
        elif vl_acc != new_acc:
            winner = "vl" if vl_acc > new_acc else "new"
        else:
            winner = None
        if winner:
            lines.append("")
            lines.append(f"Suggested winner: `{winner}`.")
            lines.append(f"Set `OCR_MODEL={winner}` in the environment (notes.md D-V6).")
        else:
            lines.append("")
            lines.append(
                "Dead tie on every metric — inspect the verbatim outputs above "
                "(failure MODES differ even when counts match), then set `OCR_MODEL` "
                "manually. Not decided by vibes."
            )
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------- main


def load_ground_truth(sample_dir: Path) -> dict[str, Any] | None:
    gt_path = sample_dir / "ground_truth.json"
    if not gt_path.is_file():
        return None
    try:
        data = json.loads(gt_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError) as exc:
        print(f"[bakeoff] ground_truth.json unreadable ({exc}); continuing without GT", file=sys.stderr)
        return None


def run_bakeoff(
    settings: Settings | None = None,
    sample_dir: Path = DEFAULT_SAMPLES,
    out_path: Path = DEFAULT_OUT,
) -> int:
    settings = settings or default_settings()
    sample_dir = Path(sample_dir)
    out_path = Path(out_path)

    images = sorted(
        p for p in sample_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    ) if sample_dir.is_dir() else []
    ground_truth = load_ground_truth(sample_dir)

    pending_reason = None
    if not images:
        pending_reason = f"waiting on real receipt photos in `{sample_dir}` (HANDOFF.md ③)"
    elif settings.mock_mode != "never" and not settings.has_api_key:
        pending_reason = "waiting on DASHSCOPE_API_KEY (HANDOFF.md ①); refusing to fabricate results"
    elif settings.mock_mode == "always":
        pending_reason = "MOCK_MODE=always — a mock bake-off is meaningless by definition"

    runs: list[ReceiptRun] = []
    if pending_reason is None:
        adapters = {"vl": QwenVlOcrAdapter(settings), "new": Qwen35OcrAdapter(settings)}
        for image in images:
            run = ReceiptRun(receipt=image.name)
            for adapter_name, adapter in adapters.items():
                try:
                    result = adapter.extract(image)
                except Exception as exc:  # noqa: BLE001 — per-receipt isolation
                    run.errors[adapter_name] = f"{type(exc).__name__}: {exc}"
                    continue
                run.results[adapter_name] = result
                gt_entry = ground_truth.get(image.name) if ground_truth else None
                if isinstance(gt_entry, dict):
                    run.scores[adapter_name] = score_against_ground_truth(
                        image.name, adapter_name, result.model, result, gt_entry
                    )
                else:
                    run.scores[adapter_name] = score_no_ground_truth(
                        image.name, adapter_name, result.model, result
                    )
                print(f"[bakeoff] {image.name} × {adapter_name}: {'ok' if result.error is None else result.error}")
            runs.append(run)

    report = build_report(settings, runs, ground_truth, pending_reason, sample_dir)
    out_path.write_text(report, encoding="utf-8")
    print(f"[bakeoff] wrote {out_path}")
    if pending_reason:
        print(f"[bakeoff] PENDING: {pending_reason}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bizro OCR bake-off (vision_agent)")
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLES, help="receipt photos dir")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output markdown path")
    parser.add_argument("--env", action="store_true", help="read settings from process env")
    args = parser.parse_args(argv)
    settings = load_settings() if args.env else default_settings()
    return run_bakeoff(settings, sample_dir=args.samples, out_path=args.out)


if __name__ == "__main__":
    raise SystemExit(main())
