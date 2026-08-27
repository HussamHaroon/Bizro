"""Drive the Bizro inbound flow with zero Meta setup (SKILL.md deliverable 5).

POSTs standard-shape WhatsApp webhook payloads (plus a clearly-namespaced
bizro_sim media envelope, honored only while WhatsApp is in mock mode) against
a running server, then reads back the persisted transactions to prove the
end-to-end path: webhook -> media blob (sha256) -> pipeline -> transaction ->
outbound confirmation.

Usage (server must be running — see server/README.md):
    python server/scripts/simulate_inbound.py --voice
    python server/scripts/simulate_inbound.py --image
    python server/scripts/simulate_inbound.py --text "1"
    python server/scripts/simulate_inbound.py --voice --image --text "1"   # full flow

All synthetic media is clearly labeled as mock (STATUS.md D0-3).
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_WA_ID = "923001234567"
DEFAULT_NAME = "Karyana Store (sim)"


def _request(url: str, method: str = "GET", payload: dict | None = None) -> tuple[int, dict | str]:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            return resp.status, (json.loads(body) if body.startswith(("{", "[")) else body)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body


def synth_voice_bytes() -> bytes:
    """Synthetic, clearly-labeled 'voice note' bytes. NOT real opus audio —
    distinct per run (timestamp) so each blob has a distinct sha256."""
    stamp = time.time_ns()
    header = f"BIZRO-MOCK-SYNTHETIC-AUDIO not-real-opus ts={stamp}".encode()
    return header + b"\x00" + uuid.uuid4().bytes + b"\x00" + stamp.to_bytes(8, "big")


def synth_receipt_png() -> bytes:
    """Synthetic receipt image labeled MOCK — generated with Pillow (no real
    handwriting; useless for the OCR bake-off by design, see samples/README.md)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        # Pillow missing: fall back to labeled bytes; mock pipelines don't decode.
        return synth_voice_bytes().replace(b"AUDIO", b"IMAGE")

    img = Image.new("RGB", (320, 180), color=(247, 242, 231))
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "BIZRO MOCK SYNTHETIC RECEIPT", fill=(166, 51, 43))
    draw.text((10, 30), f"ts={time.time_ns()}", fill=(33, 30, 26))
    draw.text((10, 50), "chai patti x N @ price", fill=(33, 30, 26))
    draw.text((10, 70), "NOT REAL DATA - FOR PIPELINE TEST ONLY", fill=(11, 93, 59))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_payload(wa_id: str, name: str, media_b64: str | None, mime: str | None, text: str | None,
                  button: str | None = None) -> dict:
    msg: dict = {"from": wa_id, "id": f"wamid.SIM{uuid.uuid4().hex[:12]}", "timestamp": str(int(time.time()))}
    if media_b64 is not None:
        media_kind = "audio" if mime == "audio/ogg; codecs=opus" else "image"
        msg["type"] = media_kind
        msg[media_kind] = {"id": f"SIM_MEDIA_{uuid.uuid4().hex[:10]}", "mime_type": mime}
    elif button is not None:
        # one-tap reply to our interactive confirm/correct buttons (§7.1)
        title = "درست ہے" if button == "confirm" else "بدلیں"
        msg["type"] = "button"
        msg["button"] = {"payload": button, "text": title}
    else:
        msg["type"] = "text"
        msg["text"] = {"body": text or ""}

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "SIM_WABA",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "15550001111", "phone_number_id": "SIM_PHONE_ID"},
                            "contacts": [{"profile": {"name": name}, "wa_id": wa_id}],
                            "messages": [msg],
                        },
                    }
                ],
            }
        ],
    }
    if media_b64 is not None:
        # namespaced simulator envelope — only honored in WhatsApp mock mode
        payload["bizro_sim"] = {"media_b64": media_b64, "mime_type": mime}
    return payload


def post_flow(base_url: str, label: str, payload: dict) -> dict:
    status, body = _request(f"{base_url}/webhook/whatsapp", method="POST", payload=payload)
    print(f"\n--- {label}: POST /webhook/whatsapp -> HTTP {status}")
    print(json.dumps(body, indent=2, ensure_ascii=False))
    if status != 200 or not body.get("processed"):
        print(f"FAILED: {label} did not process (see above)")
        sys.exit(1)
    return body


def read_back(base_url: str, merchant_id: str) -> None:
    status, body = _request(f"{base_url}/api/merchants/{merchant_id}/transactions")
    if status != 200:
        print(f"read-back GET transactions -> HTTP {status} (skipped)")
        return
    print(f"\n--- read-back: GET /api/merchants/{merchant_id}/transactions -> {body['count']} row(s)")
    for tx in body["transactions"][:5]:
        conf = tx["source"]["confidence"]
        print(
            f"  [{tx['status']:>9}] {tx['kind']:<16} PKR {tx['amount_pkd']:>8} "
            f"conf={conf} flag={tx['flag']} id={tx['id'][:8]}..."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://localhost:8000", help="server base URL")
    parser.add_argument("--wa-id", default=DEFAULT_WA_ID, help="simulated merchant WhatsApp id")
    parser.add_argument("--name", default=DEFAULT_NAME, help="simulated merchant display name")
    parser.add_argument("--voice", action="store_true", help="simulate an Urdu voice note")
    parser.add_argument("--image", action="store_true", help="simulate a receipt photo")
    parser.add_argument("--text", default=None, help="simulate a plain text reply (e.g. '1' to confirm)")
    parser.add_argument("--button", default=None, choices=["confirm", "correct"],
                        help="simulate a one-tap button reply to the latest confirmation (§7.1)")
    parser.add_argument("--voice-file", default=None, help="use a real audio file's bytes instead of synthetic")
    parser.add_argument("--image-file", default=None, help="use a real image file's bytes instead of synthetic")
    args = parser.parse_args()

    if not (args.voice or args.image or args.text is not None or args.button is not None):
        parser.error("nothing to do: pass --voice, --image, --text and/or --button")

    # 0) health + webhook GET handshake
    status, health = _request(f"{args.url}/health")
    print(f"--- GET /health -> HTTP {status}")
    print(json.dumps(health, indent=2, ensure_ascii=False))
    if status != 200:
        sys.exit("server not healthy — start it with: python -m uvicorn server.app.main:app")

    from server.app.config import get_settings
    verify_status, verify_body = _request(
        f"{args.url}/webhook/whatsapp?hub.mode=subscribe&hub.verify_token={get_settings().whatsapp_verify_token}&hub.challenge=ping123"
    )
    ok = verify_status == 200 and verify_body == "ping123"
    print(f"--- GET /webhook/whatsapp (Meta verify handshake) -> HTTP {verify_status} challenge={verify_body!r} {'OK' if ok else 'FAILED'}")
    if not ok:
        sys.exit(1)

    merchant_id = None

    if args.voice:
        data = Path(args.voice_file).read_bytes() if args.voice_file else synth_voice_bytes()
        body = post_flow(
            args.url,
            "VOICE NOTE",
            build_payload(args.wa_id, args.name, base64.b64encode(data).decode(), "audio/ogg; codecs=opus", None),
        )
        merchant_id = body["results"][0].get("merchant_id") or merchant_id

    if args.image:
        data = Path(args.image_file).read_bytes() if args.image_file else synth_receipt_png()
        body = post_flow(
            args.url,
            "RECEIPT PHOTO",
            build_payload(args.wa_id, args.name, base64.b64encode(data).decode(), "image/png", None),
        )
        merchant_id = body["results"][0].get("merchant_id") or merchant_id

    if args.text is not None:
        body = post_flow(args.url, f"TEXT REPLY {args.text!r}", build_payload(args.wa_id, args.name, None, None, args.text))
        merchant_id = body["results"][0].get("merchant_id") or merchant_id

    if args.button is not None:
        body = post_flow(
            args.url,
            f"ONE-TAP BUTTON {args.button!r}",
            build_payload(args.wa_id, args.name, None, None, None, button=args.button),
        )
        merchant_id = body["results"][0].get("merchant_id") or merchant_id

    if merchant_id:
        read_back(args.url, merchant_id)
        status, udhar = _request(f"{args.url}/api/merchants/{merchant_id}/udhar")
        if status == 200:
            print(f"\n--- GET /api/merchants/{merchant_id}/udhar -> total PKR {udhar['total_outstanding_pkd']}")
            for c in udhar["customers"]:
                print(f"  {c['name']}: PKR {c['outstanding_pkd']}")
        status, streak = _request(f"{args.url}/api/merchants/{merchant_id}/streak")
        if status == 200:
            print(f"--- GET /api/merchants/{merchant_id}/streak -> {json.dumps(streak)}")

    print("\nSIMULATION OK")


if __name__ == "__main__":
    main()
