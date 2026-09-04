"""Narrative synthesis — the ONLY place a model touches the report.

Owner ruling (2026-09-04): the loan officer reads ENGLISH, so the narrative is
simple English — short sentences, everyday words. The stored key stays
`narrative_ur` (DB column + report JSON contract keep the historical name; only
the content changed).

Receives finished Aggregates + Scored (never raw rows), returns prose. Without
DASHSCOPE_API_KEY: deterministic templated English, clearly marked mock
(D0-3/D0-8). On any API error: same labeled fallback — narrative never blocks
the report.
"""

from __future__ import annotations

import json
import os

from .aggregates import Aggregates
from .rubric import Scored

SystemPromptUr = (
    "You write a short credit report summary in simple English for a microfinance "
    "loan officer. Use only the numbers given. Do not invent new numbers. "
    "Write three to four short sentences with everyday words."
)

# rubric.py (not editable here) keeps Urdu band labels for legacy keys; the
# narrative must be English, so map the band to simple English words locally.
_BAND_LABELS_EN = {
    "ready": "ready for a loan",
    "nearly": "almost ready for a loan",
    "not_yet": "not ready for a loan yet",
    "insufficient_data": "not enough data to decide",
}


def _band_label_en(scored: Scored) -> str:
    return _BAND_LABELS_EN.get(scored.band, scored.band)


def _template_ur(agg: Aggregates, scored: Scored, merchant: str) -> str:
    """Deterministic simple-English fallback (mock-marked by the caller)."""
    return (
        f"Review of {merchant}'s record: {agg.total_entries} entries were logged "
        f"in this period, across {agg.weeks_active} weeks. Spending was "
        f"PKR {agg.cash_out:,.0f} and income was PKR {agg.cash_in:,.0f}. "
        f"Credit of PKR {agg.udhar_outstanding:,.0f} is still to be collected. "
        f"The median confidence of the data is {agg.median_confidence or 0:.2f}. "
        f"Overall rating: {_band_label_en(scored)}."
    )


def _mock(agg: Aggregates, scored: Scored, merchant: str) -> tuple[str, bool]:
    return _template_ur(agg, scored, merchant), True


def _call_reasoning_model(payload: dict) -> str | None:
    import httpx  # lazy: only needed on the live path

    key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not key:
        return None
    base = os.environ.get(
        "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ).rstrip("/")
    model = os.environ.get("MODEL_REASONING", "qwen3.7-plus")
    try:
        import llm_guard  # free-tier budget guard (repo root; D6-2)

        llm_guard.allow(model)
        resp = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SystemPromptUr},
                    {
                        "role": "user",
                        "content": (
                            "Write a simple English summary from these numbers "
                            "(JSON):\n" + json.dumps(payload, ensure_ascii=False)
                        ),
                    },
                ],
                "temperature": 0.3,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        llm_guard.record(model, usage=data.get("usage"))
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None


def build_narrative(
    agg: Aggregates, scored: Scored, merchant: str
) -> tuple[str, bool]:
    """Returns (narrative_ur, is_mock). The key name is historical — the text
    is simple English now."""
    payload = {
        "merchant": merchant,
        "total_entries": agg.total_entries,
        "weeks_active": agg.weeks_active,
        "weeks_in_span": agg.weeks_in_span,
        "cash_in": agg.cash_in,
        "cash_out": agg.cash_out,
        "net": agg.net_cashflow,
        "udhar_outstanding": agg.udhar_outstanding,
        "median_confidence": agg.median_confidence,
        "flags": agg.flag_counts,
        "band": scored.band,
        "score": scored.score,
    }
    text = _call_reasoning_model(payload)
    if text and text.strip():
        return text.strip(), False
    return _mock(agg, scored, merchant)
