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
import hmac
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from . import dispatch, whatsapp_client
from .config import get_settings
from .db import MediaBlob, Merchant, ProcessedMessage, db_session
from .media import MediaValidationError, store_blob, validate_media

logger = logging.getLogger("bizro.webhook")

router = APIRouter()

# Simple English for every merchant-facing reply (owner ruling 2026-09-04).
# Constant names keep their historical *_UR suffixes — DB columns, stored
# outbound kinds, and API consumers depend on the names, not the language.
HELP_REPLY_UR = (
    "Send Bizro a voice note or a photo. Speak your sale, expense, or credit "
    "entry, or send a picture of a receipt. "
    "Reply '1' to confirm an entry and '0' to remove it."
)

MEDIA_INVALID_REPLY_UR = (
    "We could not read that file, or it was too big. "
    "Please send a smaller file and try again."
)

# --- onboarding (first contact) ----------------------------------------------
# A merchant whose TEXT message is exactly one of these (case-insensitive;
# English or Urdu) gets a short two-message onboarding sequence instead of the
# generic help line. "help" shares the same sequence by design. The Urdu
# trigger words stay: inbound language is the merchant's choice.
ONBOARDING_TRIGGER_WORDS = frozenset(
    {"hello", "hi", "start", "help", "ہیلو", "شروع"}
)

ONBOARDING_WELCOME_UR = (
    "Welcome to Bizro! Bizro is your voice ledger. Send a voice note or a "
    "receipt photo, and we write the entry for you. The same record also "
    "builds your credit history."
)

ONBOARDING_HOWTO_UR = (
    "How to use it: 1) Send a voice note about a sale or credit. "
    "2) Send a photo of a purchase receipt. "
    "3) When an entry comes in, reply '1' if it is correct."
)

# Sent (and stored) in this order.
ONBOARDING_SEQUENCE_UR = (ONBOARDING_WELCOME_UR, ONBOARDING_HOWTO_UR)


def _is_onboarding_trigger(body: str) -> bool:
    normalized = body.strip().casefold()
    return normalized in ONBOARDING_TRIGGER_WORDS


@router.get("/webhook/whatsapp")
def webhook_verify(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
):
    s = get_settings()
    # SEC: constant-time compare (bizro-security) — a plain == leaks token
    # length/prefix information through timing.
    token_ok = hmac.compare_digest(
        str(hub_verify_token or ""), str(s.whatsapp_verify_token or "")
    )
    if hub_mode == "subscribe" and token_ok:
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
                # F-5 (§6.8): claim the wamid before any processing — a Meta
                # redelivery is acknowledged as deduped and never re-processed.
                wamid = msg.get("id")
                if wamid and not _claim_message_id(str(wamid)):
                    results.append({"message_id": wamid, "deduped": True})
                    continue
                try:
                    outcome = _handle_message(msg, contacts, sim_envelope)
                    results.append(outcome)
                except Exception:  # never let one message kill the webhook
                    logger.exception("Message handling failed (wamid=%s)", wamid)
                    results.append({"message_id": wamid, "ok": False, "error": "internal"})

    return {"processed": len(results), "results": results}


def _claim_message_id(message_id: str) -> bool:
    """Insert-or-ignore into processed_messages; False when already seen."""
    with db_session() as session:
        try:
            session.add(ProcessedMessage(message_id=message_id))
            session.commit()
            return True
        except IntegrityError:
            session.rollback()
            return False


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
            if _is_onboarding_trigger(body):
                outcome = _onboarding_outcome(msg, session, merchant)
                outcome["merchant_id"] = str(merchant.id)
                return outcome
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
        if msg_type == "button":
            # §7.1: one-tap reply to our interactive confirm/correct buttons.
            # Graph API carries button.payload; older versions only button.text.
            button = msg.get("button") or {}
            outcome = dispatch.handle_button_reply(
                session, merchant, button.get("payload"), button.get("text")
            )
            reply = outcome["reply"]
            if reply is None:
                reply = HELP_REPLY_UR  # unknown press — help, never silence
            send_result = whatsapp_client.send_text(merchant.wa_id, reply)
            return {
                "message_id": msg.get("id"),
                "ok": True,
                "type": "button",
                "merchant_id": str(merchant.id),
                "action": outcome["action"],
                # wire row of the acted-on transaction (same row the REST
                # confirm returns), or null when nothing was pending
                "transaction": outcome["transaction"],
                "reply": reply,
                "sent": send_result,
            }

        logger.info("Unsupported message type %r ignored (wamid=%s)", msg_type, msg.get("id"))
        return {"message_id": msg.get("id"), "ok": True, "type": msg_type, "ignored": True}


def _onboarding_outcome(
    msg: dict[str, Any], session, merchant: Merchant
) -> dict[str, Any]:
    """First-contact onboarding: send + store each message of the sequence
    through dispatch.send_reply — the same path every other reply uses
    (whatsapp_client delivery + an outbound_messages audit row). The bodies
    themselves are plain onboarding text: the only mock marker anywhere is the
    one whatsapp_client already adds to its send result in mock mode."""
    sent = [
        dispatch.send_reply(session, merchant, body, kind="onboarding")
        for body in ONBOARDING_SEQUENCE_UR
    ]
    return {
        "message_id": msg.get("id"),
        "ok": True,
        "type": "text",
        "onboarding": True,
        "replies": list(ONBOARDING_SEQUENCE_UR),
        # last body kept in `reply` so existing consumers of the text outcome
        # shape keep working
        "reply": ONBOARDING_SEQUENCE_UR[-1],
        "sent": sent,
    }


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

    # SEC: size caps + magic-byte sniff BEFORE anything touches disk.
    try:
        validate_media(data, kind)
    except MediaValidationError as exc:
        logger.warning("Rejected inbound %s media from %s: %s", kind, merchant.wa_id, exc)
        sent = dispatch.send_reply(session, merchant, MEDIA_INVALID_REPLY_UR)
        return _rejection_outcome(msg, MEDIA_INVALID_REPLY_UR, sent, reason=str(exc))

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

    media_block = {
        "id": str(blob.id),
        "sha256": digest,
        "bytes": len(data),
        "storage_path": str(path),
        "source": source_note,
    }

    # F-4: prior expense rows feed the vision pipeline's price-sanity flags.
    history = dispatch.price_history(session, merchant.id) if kind == "image" else None

    rejection_reply: str | None = None
    try:
        if kind == "voice":
            tx_data = dispatch.process_voice_note(str(path), merchant, occurred_at, digest)
        else:
            tx_data = dispatch.process_receipt_image(
                str(path), merchant, occurred_at, digest, history=history
            )
    except Exception as exc:
        # §6.4/F-6: ReceiptRejected carries a polite reply — send it,
        # persist nothing, and report the message handled. Anything else
        # propagates to the webhook's per-message error handler.
        rejection_reply = dispatch.rejection_reply_from_exception(exc)
        if rejection_reply is None:
            raise
        tx_data = None

    # §6.9/F-1: ambiguous/no-amount result → clarification, never persistence.
    if rejection_reply is None:
        rejection_reply = dispatch.pipeline_rejection(tx_data)

    if rejection_reply is not None:
        sent = dispatch.send_reply(session, merchant, rejection_reply)
        return _rejection_outcome(msg, rejection_reply, sent, media=media_block)

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
        "media": media_block,
        "transaction_id": str(tx.id),
        "status": tx.status,
        "confirmation_ur": confirmation,
        "sent": sent,
    }


def _rejection_outcome(
    msg: dict[str, Any],
    reply_ur: str,
    sent: dict | None,
    media: dict | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """§6.9 outcome: the message was handled OK (reply sent, nothing persisted)."""
    out: dict[str, Any] = {
        "message_id": msg.get("id"),
        "ok": True,
        "type": msg.get("type"),
        "rejected": True,
        "persisted": False,
        "reply_ur": reply_ur,
        "sent": sent,
    }
    if media is not None:
        out["media"] = media
    if reason:
        out["reason"] = reason
    return out


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
