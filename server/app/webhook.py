"""WhatsApp Cloud API webhook — schema.md §4.

- GET  /webhook/whatsapp : Meta verification handshake (hub.challenge echo)
- POST /webhook/whatsapp : message ingest (audio → voice pipeline, image →
  vision pipeline, text → confirm/reject reply handling)

X-Hub-Signature-256 is validated when WHATSAPP_APP_SECRET is set; without it,
validation is disabled (logged + surfaced in /health) so the zero-credential
simulator path works (SKILL.md hard rule).

Simulator envelope (mock mode only, never honored when WhatsApp is live):
the local simulator POSTs the standard Meta payload plus a top-level
"bizro_sim": {"media_b64": ..., "mime_type": ..., "filename": ...} carrying
the inbound media bytes, so the full store→sha256→pipeline→persist→outbound
path runs with zero Meta setup.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import select

from . import dispatch, whatsapp_client
from .config import get_settings
from .db import MediaBlob, Merchant, db_session
from .media import store_blob

logger = logging.getLogger("bizro.webhook")

router = APIRouter()

HELP_REPLY_UR = (
    "bizro کو آواز یا تصویر بھیجیں — بول کر لین دین لکھیں، یا رسید کی تصویر بھیجیں۔ "
    "تصدیق کے لیے '1' اور رد کے لیے '0' لکھیں۔"
)


@router.get("/webhook/whatsapp")
def webhook_verify(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
):
    s = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == s.whatsapp_verify_token:
        return Response(content=hub_challenge or "", media_type="text/plain")
    return Response(content="verification failed", status_code=403)


@router.post("/webhook/whatsapp")
async def webhook_ingest(request: Request):
    raw = await request.body()

    if not whatsapp_client.verify_signature(raw, request.headers.get("x-hub-signature-256")):
        return Response(content="invalid signature", status_code=403)

    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        # Meta retries malformed posts; acknowledge and log.
        logger.warning("Webhook received non-JSON body (%d bytes) — ignored", len(raw))
        return {"processed": 0, "results": []}

    sim_envelope = payload.get("bizro_sim") or {}
    results: list[dict[str, Any]] = []

    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value") or {}
            messages = value.get("messages", []) or []
            contacts = {c.get("wa_id"): c for c in (value.get("contacts") or [])}
            if not messages:
                # statuses (delivery receipts) and others: acknowledged, ignored
                continue

            for msg in messages:
                try:
                    outcome = _handle_message(msg, contacts, sim_envelope)
                    results.append(outcome)
                except Exception:  # never let one message kill the webhook
                    logger.exception("Message handling failed (wamid=%s)", msg.get("id"))
                    results.append({"message_id": msg.get("id"), "ok": False, "error": "internal"})

    return {"processed": len(results), "results": results}


def _handle_message(
    msg: dict[str, Any], contacts: dict[str, Any], sim_envelope: dict[str, Any]
) -> dict[str, Any]:
    wa_id: str = msg.get("from", "")
    ts = msg.get("timestamp")
    occurred_at = (
        datetime.fromtimestamp(int(ts), tz=timezone.utc) if ts else datetime.now(timezone.utc)
    )
    msg_type: str = msg.get("type", "")

    with db_session() as session:
        merchant = _upsert_merchant(session, wa_id, contacts.get(wa_id))
        session.refresh(merchant)

        if msg_type == "audio":
            outcome = _ingest_media(
                session, merchant, msg, sim_envelope, occurred_at, kind="voice"
            )
            outcome["merchant_id"] = str(merchant.id)
            return outcome
        if msg_type == "image":
            outcome = _ingest_media(
                session, merchant, msg, sim_envelope, occurred_at, kind="image"
            )
            outcome["merchant_id"] = str(merchant.id)
            return outcome
        if msg_type == "text":
            body = ((msg.get("text") or {}).get("body") or "").strip()
            reply = dispatch.handle_text_reply(session, merchant, body)
            if reply is None:
                reply = HELP_REPLY_UR
            send_result = whatsapp_client.send_text(merchant.wa_id, reply)
            return {
                "message_id": msg.get("id"),
                "ok": True,
                "type": "text",
                "merchant_id": str(merchant.id),
                "reply": reply,
                "sent": send_result,
            }

        logger.info("Unsupported message type %r ignored (wamid=%s)", msg_type, msg.get("id"))
        return {"message_id": msg.get("id"), "ok": True, "type": msg_type, "ignored": True}


def _upsert_merchant(session, wa_id: str, contact: dict[str, Any] | None) -> Merchant:
    merchant = session.scalar(select(Merchant).where(Merchant.wa_id == wa_id))
    display_name = ((contact or {}).get("profile") or {}).get("name")
    if merchant is None:
        merchant = Merchant(wa_id=wa_id, display_name=display_name)
        session.add(merchant)
        session.flush()
    elif display_name and merchant.display_name != display_name:
        merchant.display_name = display_name
        session.flush()
    return merchant


def _ingest_media(
    session,
    merchant: Merchant,
    msg: dict[str, Any],
    sim_envelope: dict[str, Any],
    occurred_at,
    kind: str,
) -> dict[str, Any]:
    media_meta: dict[str, Any] = msg.get(msg["type"]) or {}
    mime_type: str = media_meta.get("mime_type") or sim_envelope.get("mime_type") or "application/octet-stream"

    data, source_note = _get_media_bytes(media_meta, sim_envelope, mime_type, kind)
    path, digest = store_blob(data, mime_type, kind)

    blob = MediaBlob(
        merchant_id=merchant.id,
        kind=kind,
        mime_type=mime_type,
        storage_path=str(path),
        sha256=digest,
    )
    session.add(blob)
    session.flush()

    if kind == "voice":
        tx_data = dispatch.process_voice_note(str(path), merchant, occurred_at, digest)
    else:
        tx_data = dispatch.process_receipt_image(str(path), merchant, occurred_at, digest)

    # Link the pipeline output to the stored blob before validation/persist.
    src = tx_data.get("source") or {}
    src.setdefault("media_id", str(blob.id))
    tx_data["source"] = src

    tx = dispatch.persist_transaction(session, merchant, tx_data, blob.id)
    confirmation = tx_data.get("confirmation_ur") or ""
    sent = dispatch.send_confirmation(merchant, tx, confirmation) if confirmation else None
    return {
        "message_id": msg.get("id"),
        "ok": True,
        "type": msg["type"],
        "media": {
            "id": str(blob.id),
            "sha256": digest,
            "bytes": len(data),
            "storage_path": str(path),
            "source": source_note,
        },
        "transaction_id": str(tx.id),
        "status": tx.status,
        "confirmation_ur": confirmation,
        "sent": sent,
    }


def _get_media_bytes(
    media_meta: dict[str, Any], sim_envelope: dict[str, Any], mime_type: str, kind: str
) -> tuple[bytes, str]:
    """Live: two-step Graph API download. Mock: decode the simulator envelope
    (clearly-labeled synthetic bytes)."""
    if whatsapp_client.is_live() and media_meta.get("id"):
        data, _ = whatsapp_client.download_media(media_meta["id"])
        return data, "whatsapp_graph_api"

    if sim_envelope.get("media_b64"):
        data = base64.b64decode(sim_envelope["media_b64"])
        return data, "simulator_envelope"

    raise RuntimeError(
        f"Cannot obtain {kind} media: WhatsApp not live and no bizro_sim envelope. "
        "Use scripts/simulate_inbound.py or configure WhatsApp credentials (HANDOFF.md ②)."
    )
