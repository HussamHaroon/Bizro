"""Does qwen3.8-omni-flash accept IMAGE input? (live 1-call probe)

The free-quota list has no VL model, but if the omni model reads images, the
receipt pipeline keeps its free-tier home. Run: python vision-agent/scripts/test_omni_image.py
"""
from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx


def main() -> None:
    from server.app.config import get_settings

    s = get_settings()
    key = s.dashscope_api_key
    if not key:
        print("NO KEY")
        return
    # 1x3-pixel PNG receipt-stand-in: if the model accepts images at all it
    # will describe/fail-read it; rejection comes back as an API error.
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAMAAAACCAYAAACddLYaAAAAEklEQVR4nGP8z8DwnwEJMDEgAQBGKQEDuXOjLgAAAABJRU5ErkJggg=="
    )
    data_uri = "data:image/png;base64," + base64.b64encode(png).decode()
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3.8-omni-flash"
    resp = httpx.post(
        s.dashscope_base_url.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_uri}},
                    {"type": "text", "text": "What do you see? One sentence."},
                ],
            }],
        },
        timeout=60,
    )
    print("HTTP", resp.status_code)
    body = resp.json()
    if resp.status_code == 200:
        print("IMAGE INPUT ACCEPTED by", model)
        print("reply:", body["choices"][0]["message"].get("content", "")[:200])
    else:
        print("REJECTED:", json.dumps(body)[:300] if (json := __import__("json")) else body)


if __name__ == "__main__":
    main()
