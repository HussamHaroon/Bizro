"""Urdu narrative synthesis — the ONLY place a model touches the report.

Receives finished Aggregates + Scored (never raw rows), returns prose. Without
DASHSCOPE_API_KEY: deterministic templated Urdu, clearly marked mock (D0-3/D0-8).
On any API error: same labeled fallback — narrative never blocks the report.
"""

from __future__ import annotations

import json
import os

from .aggregates import Aggregates
from .rubric import Scored

SystemPromptUr = (
    "آپ مائیکرو فائنانس کے لیو آفیسر کے لیے اردو میں مختصر رپورٹ لکھتے ہیں۔ "
    "صرف دیے گئے اعداد و شمار استعمال کریں۔ کوئی نیا عدد نہ بنائیں۔ "
    "تین سے چار جملے لکھیں۔"
)


def _template_ur(agg: Aggregates, scored: Scored, merchant: str) -> str:
    return (
        f"{merchant} کے رکارڈ کا جائزہ: اس عرصے میں کل {agg.total_entries} اندراجات "
        f"({agg.weeks_active} ہفتوں میں) درج ہوئے۔ خرچ PKR {agg.cash_out:,.0f}، "
        f"آمدنی PKR {agg.cash_in:,.0f}۔ اُدھار ابھی PKR {agg.udhar_outstanding:,.0f} "
        f"وصول ہونا ہے۔ درج معلومات کا میڈین اعتماد {agg.median_confidence or 0:.2f} ہے۔ "
        f"مجموعی درجہ بندی: {scored.label_ur}۔"
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
                            "ان اعداد و شمار کی بنیاد پر اردو خلاصہ لکھیں "
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
    """Returns (narrative_ur, is_mock)."""
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
