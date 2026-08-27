"""Thin WhatsApp Cloud API client.

Live mode: sends text messages via POST graph.facebook.com/{version}/{phone_number_id}/messages
and downloads inbound media (two-step: metadata then bytes).
Mock mode (no WHATSAPP_TOKEN / MOCK_MODE=always): sends are logged and marked
"mock": true, never delivered; media downloads raise a clear error so the
webhook falls back to the simulator media path.

Outbound audit trail: the webhook/dispatch layer persists every message to
`outbound_messages` regardless of mode (schema.md §2).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import get_settings

logger = logging.getLogger("bizro.whatsapp")

GRAPH_API_VERSION = "v22.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class WhatsAppError(RuntimeError):
    pass


class MockModeError(WhatsAppError):
    """MOCK_MODE=never was set but WhatsApp credentials are missing."""


def is_live() -> bool:
    return get_settings().whatsapp_is_live()


def _require_live() -> None:
    s = get_settings()
    if not s.whatsapp_is_live():
        if s.mock_mode == "never":
            raise MockModeError(
                "MOCK_MODE=never but WHATSAPP_TOKEN/WHATSAPP_PHONE_NUMBER_ID missing "
                "— refusing to fake a send."
            )


def send_text(
    to_wa_id: str,
    body: str,
    buttons: list[dict[str, Any]] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Send a WhatsApp text message. Mock mode: log loudly, return mock marker.

    `buttons` (schema.md §7.1): Graph API interactive reply buttons in their
    wire shape ([{"type": "reply", "reply": {"id": ..., "title": ...}}, ...]).
    When WHATSAPP_TOKEN is live the message goes out as
    `interactive.type=button`; in mock mode nothing is delivered but the button
    labels are logged (and returned) so the flow stays observable offline.
    """
    _require_live()
    s = get_settings()
    if not s.whatsapp_is_live():
        if buttons:
            logger.warning(
                "MOCK OUTBOUND BUTTONS (not sent): to=%s body=%r buttons=%s",
                to_wa_id,
                body,
                [b.get("reply", {}).get("title") for b in buttons],
            )
        else:
            logger.warning(
                "MOCK OUTBOUND (not sent — no WhatsApp credentials): to=%s body=%r",
                to_wa_id,
                body,
            )
        result: dict[str, Any] = {
            "mock": True,
            "note": "MOCK send — message logged, not delivered. Configure WHATSAPP_TOKEN (HANDOFF.md ②).",
            "to": to_wa_id,
            "body": body,
        }
        if buttons:
            result["buttons"] = buttons
        return result

    if buttons:
        # §7.1: one-tap confirm/correct — interactive button message instead of
        # plain text (buttons only attach on the live Graph API path).
        message = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_wa_id,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {"buttons": buttons},
            },
        }
    else:
        message = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_wa_id,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }

    resp = httpx.post(
        f"{GRAPH_BASE}/{s.whatsapp_phone_number_id}/messages",
        headers={"Authorization": f"Bearer {s.whatsapp_token}"},
        json=message,
        timeout=timeout,
    )
    if resp.status_code not in (200, 201):
        raise WhatsAppError(f"WhatsApp send HTTP {resp.status_code}: {resp.text[:500]}")
    return resp.json()


def download_media(media_id: str, timeout: float = 60.0) -> tuple[bytes, str]:
    """Two-step media download. Returns (bytes, mime_type).

    Raises WhatsAppError in mock mode — callers use the simulator media path
    instead (webhook.py `bizro_sim` envelope).
    """
    _require_live()
    s = get_settings()
    if not s.whatsapp_is_live():
        raise WhatsAppError(
            "Cannot download real WhatsApp media in mock mode — use the simulator "
            "path (scripts/simulate_inbound.py) or configure WHATSAPP_TOKEN (HANDOFF.md ②)."
        )

    meta = httpx.get(
        f"{GRAPH_BASE}/{media_id}",
        headers={"Authorization": f"Bearer {s.whatsapp_token}"},
        timeout=timeout,
    )
    if meta.status_code != 200:
        raise WhatsAppError(
            f"WhatsApp media meta HTTP {meta.status_code}: {meta.text[:500]}"
        )
    meta_json = meta.json()
    url, mime = meta_json.get("url"), meta_json.get("mime_type", "application/octet-stream")
    if not url:
        raise WhatsAppError(f"No url in media metadata for {media_id}")

    data = httpx.get(url, headers={"Authorization": f"Bearer {s.whatsapp_token}"}, timeout=timeout)
    if data.status_code != 200:
        raise WhatsAppError(f"WhatsApp media bytes HTTP {data.status_code}")
    return data.content, mime


def verify_signature(raw_body: bytes, header_value: str | None) -> bool:
    """X-Hub-Signature-256 validation (hmac-sha256 of the raw body with the App
    Secret). Returns True when validation is disabled (no app secret configured)
    so the zero-credential simulator path works — that state is logged and
    surfaced in /health."""
    import hmac
    import hashlib

    secret = get_settings().whatsapp_app_secret
    if not secret:
        logger.warning(
            "Webhook signature validation DISABLED: WHATSAPP_APP_SECRET not set "
            "(fine for the simulator path; set it before exposing a real tunnel)."
        )
        return True
    if not header_value:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header_value)
