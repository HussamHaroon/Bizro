"""Check which models the configured DashScope key can reach (HANDOFF.md ①).

    python server/scripts/verify_key.py

- No key (MOCK_MODE=auto): prints a clear mock notice and exits 0 — this is the
  expected pre-key state, not an error.
- With a key: GETs {DASHSCOPE_BASE_URL}/models and checks every MODEL_* env
  against the reachable list, so a typo'd or drifted model id is caught before
  the demo. Findings source: server/docs/model-notes.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from server.app import dashscope_client  # noqa: E402
from server.app.config import get_settings  # noqa: E402


def main() -> int:
    s = get_settings()
    print(f"base_url : {s.dashscope_base_url}")
    print(f"mock_mode: {s.mock_mode}")
    print(f"key      : {'set (' + s.dashscope_api_key[:6] + '...)' if s.dashscope_api_key else 'NOT SET'}")
    print()

    if not s.dashscope_api_key:
        print(
            "No DASHSCOPE_API_KEY configured — running in MOCK mode.\n"
            "This is expected until HANDOFF.md ① is done; nothing here reflects the real API.\n"
            "To go live: create a key in the Model Studio console and put it in .env, then re-run."
        )
        return 0

    try:
        result = dashscope_client.list_models()
    except dashscope_client.DashScopeError as exc:
        # /models is not documented on every regional endpoint (model-notes.md §1)
        # — fall back to per-model chat probes.
        print(f"GET /models failed ({exc}) — falling back to per-model probes.\n")
        return _probe_check()

    if result.get("mock"):
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    ids = sorted(m.get("id", "") for m in result.get("data", []))
    print(f"reachable models ({len(ids)}):")
    for mid in ids:
        print(f"  {mid}")

    print("\nMODEL_* env check:")
    all_ok = True
    for label, model_id in [
        ("MODEL_VOICE", s.model_voice),
        ("MODEL_OCR_VL", s.model_ocr_vl),
        ("MODEL_OCR_NEW", s.model_ocr_new),
        ("MODEL_REASONING", s.model_reasoning),
    ]:
        exact = model_id in ids
        prefix_ok = any(i == model_id or i.startswith(model_id + "-") for i in ids)
        if exact or prefix_ok:
            print(f"  {label:16} {model_id:24} FOUND")
        else:
            near = [i for i in ids if model_id.split("-")[0] in i][:5]
            print(f"  {label:16} {model_id:24} NOT FOUND — near matches: {near if near else 'none'}")
            all_ok = False

    if not all_ok:
        print("\nSome MODEL_* ids are not reachable — check server/docs/model-notes.md "
              "and correct the values in .env.")
    return 0 if all_ok else 1


def _probe_check() -> int:
    s = get_settings()
    all_ok = True
    for label, model_id in [
        ("MODEL_VOICE", s.model_voice),
        ("MODEL_OCR_VL", s.model_ocr_vl),
        ("MODEL_OCR_NEW", s.model_ocr_new),
        ("MODEL_REASONING", s.model_reasoning),
    ]:
        try:
            ok = dashscope_client.probe_model(model_id)
            print(f"  {label:16} {model_id:24} {'REACHABLE' if ok else 'NOT REACHABLE'}")
            all_ok &= ok
        except Exception as exc:  # network-level failure
            print(f"  {label:16} {model_id:24} ERROR: {exc}")
            all_ok = False
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
