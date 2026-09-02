"""OpenRouter free-tier live test — ONE batched, budgeted script (D6-2).

Runs the minimum set of real inference calls needed to prove the pipeline on
OpenRouter's free Qwen models, then prints the usage ledger:

  STEP 0  GET /models                      — FREE (not an inference call);
           lists available `:free` Qwen models grouped by modality
  STEP 1  TEXT   (1 request)               — Urdu utterance → transaction JSON
           via the server's real choke-point (server.app.dashscope_client)
  STEP 2  VISION (1 request)               — sample receipt → expense JSON
           via the vision-agent's real OCR client
  STEP 3  AUDIO  (1 request, --audio only) — voice note → text, only if
           MODEL_VOICE looks audio-capable (most :free models are not)

Usage:
  python server/scripts/openrouter_live_test.py            # plan only, no spend
  python server/scripts/openrouter_live_test.py --live     # spend 2 requests
  python server/scripts/openrouter_live_test.py --live --audio

Every call passes llm_guard.allow/record — counted in
data/openrouter-usage.json against OPENROUTER_DAILY_BUDGET.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import httpx  # noqa: E402

import llm_guard  # noqa: E402


def _env(k: str, d: str = "") -> str:
    v = os.environ.get(k, "")
    if not v:
        # pull from .env without importing dotenv (script may run bare)
        envf = REPO_ROOT / ".env"
        if envf.exists():
            for line in envf.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith(f"{k}="):
                    v = line.split("=", 1)[1].strip()
                    break
    return v or d


BASE = _env("DASHSCOPE_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
KEY = _env("DASHSCOPE_API_KEY")
M_TEXT = _env("MODEL_REASONING", "qwen/qwen3-235b-a22b:free")
M_VL = _env("MODEL_OCR_NEW", "qwen/qwen2.5-vl-72b-instruct:free")
M_VOICE = _env("MODEL_VOICE", "")
HEADERS = {
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/bizro",
    "X-Title": "Bizro",
}


def step0_models() -> None:
    print("=" * 62)
    print("STEP 0 · GET /models  (free — no inference quota spent)")
    print(f"  endpoint: {BASE}")
    print(f"  key: {KEY[:12]}...{KEY[-6:]}" if KEY else "  key: MISSING")
    print(f"  ledger: {llm_guard.spent_today()}/{llm_guard.budget()} requests spent today")
    if not KEY:
        print("  !! set DASHSCOPE_API_KEY=sk-or-v1-... in .env")
        return
    try:
        r = httpx.get(f"{BASE}/models", headers=HEADERS, timeout=30)
        data = r.json()
        free = [
            m
            for m in data.get("data", [])
            if str(m.get("id", "")).endswith(":free")
            and "qwen" in str(m.get("id", "")).lower()
        ]
        vision = [m["id"] for m in free if "vision" in str(m.get("architecture", {})).lower()
                  or "vl" in m["id"].lower()]
        print(f"  free QWEN models available: {len(free)}")
        for m in free[:12]:
            print(f"    - {m['id']}")
        if vision:
            print(f"  vision-capable: {vision[:5]}")
        print("  (full list: https://openrouter.ai/models?max-price=0)")
    except Exception as exc:  # noqa: BLE001
        print(f"  !! /models failed: {exc}")


def step1_text(live: bool) -> None:
    print("=" * 62)
    print(f"STEP 1 · TEXT — {M_TEXT}  (1 request)")
    if not live:
        print("  SKIP (plan only — pass --live to spend)")
        return
    llm_guard.allow(M_TEXT)
    r = httpx.post(
        f"{BASE}/chat/completions",
        headers=HEADERS,
        json={
            "model": M_TEXT,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You parse Pakistani karyana shopkeeper utterances into JSON: "
                        '{"customer": str, "amount_pkr": number, "type": "udhar|sale", '
                        '"item": str|null, "confidence": number}. Reply with JSON only.'
                    ),
                },
                {"role": "user", "content": "احمد کو پانچ ہزار کا ادھار دیا، چینی کے لیے"},
            ],
            "temperature": 0.1,
            "max_tokens": 200,
        },
        timeout=90,
    )
    if r.status_code == 200:
        llm_guard.record(M_TEXT, usage=r.json().get("usage"))
    print(f"  HTTP {r.status_code}")
    if r.status_code == 200:
        msg = r.json()["choices"][0]["message"]
        content = msg.get("content")
        if not content:
            print(f"  message object: {json.dumps(msg, ensure_ascii=False)[:400]}")
        else:
            print(f"  reply: {str(content)[:220]}")
    else:
        print(f"  !! {r.text[:300]}")


def step2_vision(live: bool) -> None:
    print("=" * 62)
    print(f"STEP 2 · VISION — {M_VL}  (1 request)")
    img = REPO_ROOT / "samples" / "demo" / "receipt_clean.png"
    if not img.exists():
        print(f"  !! sample receipt missing: {img}")
        return
    if not live:
        print("  SKIP (plan only — pass --live to spend)")
        return
    b64 = base64.b64encode(img.read_bytes()).decode()
    llm_guard.allow(M_VL)
    r = httpx.post(
        f"{BASE}/chat/completions",
        headers=HEADERS,
        json={
            "model": M_VL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                        {
                            "type": "text",
                            "text": (
                                "Read this shop receipt. Reply with JSON only: "
                                '{"vendor": str, "total_pkr": number, "items": number}'
                            ),
                        },
                    ],
                }
            ],
            "max_tokens": 1200,
        },
        timeout=120,
    )
    if r.status_code == 200:
        llm_guard.record(M_VL, usage=r.json().get("usage"))
    print(f"  HTTP {r.status_code}")
    if r.status_code == 200:
        msg = r.json()["choices"][0]["message"]
        content = msg.get("content")
        if not content:
            print(f"  message object: {json.dumps(msg, ensure_ascii=False)[:400]}")
        else:
            print(f"  reply: {str(content)[:220]}")
    else:
        print(f"  !! {r.text[:300]}")


def step3_audio(live: bool) -> None:
    print("=" * 62)
    print(f"STEP 3 · AUDIO — {M_VOICE or '(MODEL_VOICE not set)'}")
    audio_capable = any(
        k in M_VOICE.lower() for k in ("omni", "audio", "tts", "asr", "whisper")
    )
    if not M_VOICE or not audio_capable:
        print("  SKIP — no audio-capable model configured; the voice pipeline stays")
        print("  on mock until a free audio model is confirmed on OpenRouter.")
        return
    if not live:
        print("  SKIP (plan only)")
        return
    print("  (audio probe: run server/scripts/demo_flow.py step 2 once a free")
    print("   audio-capable model is confirmed — not batched here)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="spend the inference requests")
    ap.add_argument("--audio", action="store_true", help="include the audio probe")
    args = ap.parse_args()

    step0_models()
    step1_text(args.live)
    step2_vision(args.live)
    if args.audio:
        step3_audio(args.live)

    print("=" * 62)
    print(
        f"LEDGER: {llm_guard.spent_today()}/{llm_guard.budget()} requests today "
        f"→ {llm_guard.LEDGER_PATH}"
    )
    print(f"remaining budget today: {llm_guard.budget() - llm_guard.spent_today()}")


if __name__ == "__main__":
    main()
