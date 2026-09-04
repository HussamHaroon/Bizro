"""Voice Khata pipeline: one WhatsApp voice note → schema.md §1 transaction dict.

Single-prompt design: the omni model transcribes AND structures in ONE call (no
separate ASR step — that's the point of omni). Pydantic validates the model's JSON
against the contract with one repair-retry; anything still failing, ambiguous, or
low-confidence becomes flag=low_confidence + a clarification question — the pipeline
NEVER guesses an amount (schema.md §1 rule).

Text-only confirmation is the MVP (design.md §2). Mock mode shares the exact same
assembly code; only the network call is faked.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from voice_agent.config import Settings, load_settings
from voice_agent.confirmation import UNCLEAR_KIND_MARKER, build_confirmation_ur
from voice_agent.dashscope_client import DashScopeClient, DashScopeError
from voice_agent.decode import DecodeError, decode_audio
from voice_agent.mock_data import SCENARIOS, infer_scenario, mock_response_text
from voice_agent.models import Transaction

SYSTEM_PROMPT = """You are Bizro's voice-ledger parser for Pakistani karyana (corner-store) merchants.
You receive ONE short WhatsApp voice note in casual Urdu, often mixed with English words and brand
names, numbers spoken as words ("panch hazar", "پندرہ سو"). Transcribe it, then extract the transaction.

Respond with ONLY a JSON object, no prose, in exactly this shape:
{
  "transcript": "<verbatim transcription, Urdu script; keep code-switched English words as spoken>",
  "confidence": <float 0..1 — your honest confidence in the EXTRACTION, not the transcription>,
  "transaction": {
    "kind": "sale | expense | udhar_given | udhar_settlement | null",
    "amount_pkr": <positive number, PKR rupees | null>,
    "counterparty": {"name": "<customer or supplier name | null>", "phone": null},
    "description": "<short English summary for the ledger>",
    "item_lines": [{"item": "...", "qty": <number>, "unit": "packet|tin|bag|...", "unit_price": <number>, "line_total": <number>}],
    "unclear": [<list of field names you are NOT sure about: "amount", "kind", "counterparty_name">]
  }
}

Kind semantics (direction is implied by kind; amount is always positive):
- "sale": customer bought and PAID now (cash in).
- "udhar_given": merchant extended credit — customer owes the merchant (the classic khata entry).
- "udhar_settlement": customer repaid part or all of an earlier udhar.
- "expense": merchant bought stock/paid a supplier (receipt photos also land here).

HARD RULES:
- If the note is NOT a transaction (a question, small talk), set kind=null and list "kind" in unclear.
- If the amount is ambiguous ("پانچ یا چھ ہزار"), set amount_pkr=null and list "amount" in unclear.
  NEVER pick one of several possible amounts. NEVER invent digits.
- Convert spoken number words to digits: "panch hazar"=5000, "پندرہ سو"=1500, "aath bori"=8 bags.
- English number words are often written in Urdu script PHONETICALLY by the transcriber:
  "سون تھاؤزن" = 7000, "ٹو ان ہزار" = 2000, "پوائنٹ فائیو" = 0.5, "فورٹی فائیو" = 45.
  Always convert these phonetic English numbers to digits like any other spoken number.
- item_lines only when the note clearly lists items; else [].
- If item_lines exist and their line_totals do not sum to amount_pkr, still report what was said —
  do NOT silently fix; the pipeline flags the mismatch."""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def process_voice_note(
    audio_path: str | Path,
    merchant: dict | None = None,
    occurred_at: str | dt.datetime | None = None,
    *,
    media_id: str | None = None,
    settings: Settings | None = None,
    mock_scenario: str | None = None,
) -> dict:
    """Process one WhatsApp voice note → schema.md §1 transaction dict.

    `merchant`: optional {"display_name": ...} — used on the invoice header only.
    `occurred_at`: message timestamp (defaults to now, Asia/Karachi).
    `mock_scenario`: test/demo hook to pin a canned scenario in mock mode.
    """
    settings = settings or load_settings()
    when = _coerce_occurred_at(occurred_at)
    audio_bytes = Path(audio_path).read_bytes()

    if settings.use_mock:
        scenario = (
            mock_scenario
            or os.environ.get("MOCK_SCENARIO")
            or infer_scenario(audio_bytes)
        )
        if scenario not in SCENARIOS:
            raise ValueError(
                f"unknown mock scenario {scenario!r}; options: {sorted(SCENARIOS)}"
            )
        model_text = mock_response_text(scenario)
    else:
        client = DashScopeClient(settings)  # fail fast on missing key
        decoded = None
        if settings.stt_api_key:
            # D6-3 free-tier path: STT transcribes, the text model structures.
            # (The OpenRouter free tier has no audio-input models.) The omni
            # single-call path stays for when a DashScope voucher lands.
            try:
                from voice_agent.stt_client import STTError, transcribe

                decoded = decode_audio(audio_bytes, strategy=settings.audio_decode)
                transcript = transcribe(
                    decoded.data, filename=f"voice.{decoded.api_format}", settings=settings
                )
                # plain text call — generic hosts reject the omni field set
                model_text = client.chat_text(
                    system=SYSTEM_PROMPT,
                    user_text=(
                        f"السماعی نوٹ کا متن (transcript):\n{transcript}\n\n"
                        + _user_prompt(when)
                    ),
                ).text
            except Exception as exc:  # noqa: BLE001 — webhook path never crashes
                # Corrupt audio or STT failure → ask again; never crash the webhook.
                return _low_confidence_fallback(
                    transcript="", when=when, media_id=media_id, confidence=0.0,
                    settings=settings, mock=False, note=f"stt path failed: {exc}",
                )
        else:
            try:
                decoded = decode_audio(audio_bytes, strategy=settings.audio_decode)
            except DecodeError as exc:
                # Corrupt/undecodable audio → ask again; never crash the webhook path.
                return _low_confidence_fallback(
                    transcript="", when=when, media_id=media_id, confidence=0.0,
                    settings=settings, mock=False, note=f"audio decode failed: {exc}",
                )
            model_text = client.omni_chat(
                system=SYSTEM_PROMPT, user_text=_user_prompt(when)
            ).text

    tx_dict, errors = _assemble(
        model_text, when, media_id, settings, mock=settings.use_mock,
        mock_scenario=scenario if settings.use_mock else None,
    )
    if errors and not settings.use_mock:
        # One repair-retry against the real model (mock scenarios are always valid).
        model_text = _repair_call(client, settings, model_text, errors)
        tx_dict, errors = _assemble(model_text, when, media_id, settings, mock=False)
        if errors:
            tx_dict = _low_confidence_fallback(
                transcript=_extract_transcript(model_text), when=when, media_id=media_id,
                confidence=0.0, settings=settings, mock=False,
                note="model output failed schema validation after repair",
            )
    return tx_dict


# ---------------------------------------------------------------------------
# Assembly: model text → validated, flagged, confirmed transaction dict
# ---------------------------------------------------------------------------


def _assemble(
    model_text: str, when: dt.datetime, media_id: str | None,
    settings: Settings, *, mock: bool, mock_scenario: str | None = None,
) -> tuple[dict, list[str]]:
    """Parse + validate + apply flag rules. Returns (tx_dict, validation_errors)."""
    parsed, extract_err = _extract_json(model_text)
    if extract_err:
        return _low_confidence_fallback(
            transcript=_extract_transcript(model_text), when=when, media_id=media_id,
            confidence=0.0, settings=settings, mock=mock, note=extract_err,
        ), [extract_err]

    transcript = str(parsed.get("transcript") or "")
    inner: dict = parsed.get("transaction") or {}
    unclear = set(inner.get("unclear") or [])
    confidence = _safe_confidence(parsed.get("confidence"))

    # -- garbage / no-transaction path --------------------------------------
    if not inner or inner.get("kind") is None or not transcript:
        return _low_confidence_fallback(
            transcript=transcript, when=when, media_id=media_id, confidence=confidence,
            settings=settings, mock=mock, kind_hint=inner.get("kind") if inner else None,
            counterparty_name=(inner.get("counterparty") or {}).get("name"),
            mock_scenario=mock_scenario,
        ), []

    # -- unclear extraction → flag, never guess ------------------------------
    amount = _safe_amount(inner.get("amount_pkr"))
    unknown_amount = ("amount" in unclear) or amount is None
    if "kind" in unclear or unknown_amount:
        return _low_confidence_fallback(
            transcript=transcript, when=when, media_id=media_id, confidence=confidence,
            settings=settings, mock=mock, kind_hint=inner.get("kind"),
            counterparty_name=(inner.get("counterparty") or {}).get("name"),
            kind=None if "kind" in unclear else inner.get("kind"),
            amount=None,
            mock_scenario=mock_scenario,
        ), []

    raw_out: dict = {"transcript": transcript}
    if mock:
        raw_out["mock"] = True  # §6.3/§6.11: stored-row mock marker
    if mock_scenario:
        raw_out["mock_scenario"] = mock_scenario

    try:
        tx = Transaction(
            kind=inner["kind"],
            amount_pkr=amount,
            counterparty=(inner.get("counterparty") or {}),
            description=str(inner.get("description") or ""),
            item_lines=inner.get("item_lines") or [],
            occurred_at=when,
            source={
                "type": "voice",
                "media_id": media_id,
                "model": None if mock else settings.model_voice,
                "confidence": confidence,
                "raw_output": raw_out,
            },
            mock=mock,
        )
    except ValidationError as exc:
        errs = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        return _low_confidence_fallback(
            transcript=transcript, when=when, media_id=media_id, confidence=confidence,
            settings=settings, mock=mock, note="schema validation failed: " + "; ".join(errs[:4]),
            mock_scenario=mock_scenario,
        ), errs

    # -- derived flags -------------------------------------------------------
    _apply_derived_flags(tx, settings)
    tx.confirmation_ur = build_confirmation_ur(tx, settings.numeral_style)
    return tx.model_dump(mode="json"), []


def _apply_derived_flags(tx: Transaction, settings: Settings) -> None:
    if tx.flag == "none":
        if tx.source.confidence < settings.confidence_confirm_threshold:
            tx.flag = "low_confidence"
        elif tx.item_lines and tx.amount_pkr is not None:
            total = sum(li.line_total for li in tx.item_lines)
            if abs(total - tx.amount_pkr) > 0.01:
                tx.flag = "total_mismatch"
    # status stays "pending": every AI entry awaits the merchant's WhatsApp reply.


def _low_confidence_fallback(
    *,
    transcript: str,
    when: dt.datetime,
    media_id: str | None,
    confidence: float,
    settings: Settings,
    mock: bool,
    note: str = "",
    kind_hint: str | None = None,
    counterparty_name: str | None = None,
    kind: str | None = None,
    amount: float | None = None,
    mock_scenario: str | None = None,
) -> dict:
    """Schema-conformant 'ask again' payload. amount None = unknown, never a guess
    (§6.2/§6.9: the server must persist NOTHING and send the clarification instead)."""
    # kind is required by the contract enum; carry what was determinable, else mark
    # the description with UNCLEAR_KIND so the confirmation builder asks about kind.
    final_kind = kind if kind in ("sale", "expense", "udhar_given", "udhar_settlement") else "udhar_given"
    if kind in ("sale", "expense", "udhar_given", "udhar_settlement"):
        description = f"Unconfirmed {kind}{': ' + note if note else ''}"
    else:
        description = f"{UNCLEAR_KIND_MARKER} — needs clarification{': ' + note if note else ''}"

    raw_out: dict = {"transcript": transcript}
    if mock:
        raw_out["mock"] = True  # §6.3/§6.11: stored-row mock marker
    if mock_scenario:
        raw_out["mock_scenario"] = mock_scenario
    elif mock:
        raw_out["mock_note"] = note or "canned scenario: clarification"

    tx = Transaction(
        kind=final_kind,
        amount_pkr=amount,
        counterparty={"name": counterparty_name, "phone": None},
        description=description,
        item_lines=[],
        occurred_at=when,
        source={
            "type": "voice",
            "media_id": media_id,
            "model": None if mock else settings.model_voice,
            "confidence": confidence,
            "raw_output": raw_out,
        },
        flag="low_confidence",
        status="pending",
        mock=mock,
    )
    tx.confirmation_ur = build_confirmation_ur(tx, settings.numeral_style)
    return tx.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Helpers: JSON extraction, transcript salvage, repair call, time
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _extract_json(text: str) -> tuple[dict | None, str]:
    """Pull the JSON object out of a (possibly fenced / chatty) model reply."""
    candidates: list[str] = []
    for m in _FENCE_RE.finditer(text or ""):
        candidates.append(m.group(1).strip())
    candidates.append((text or "").strip())
    for cand in candidates:
        start, end = cand.find("{"), cand.rfind("}")
        if start == -1 or end <= start:
            continue
        try:
            obj = json.loads(cand[start : end + 1])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj, ""
    return None, "no parsable JSON object in model output"


def _extract_transcript(model_text: str) -> str:
    parsed, _ = _extract_json(model_text)
    if parsed and parsed.get("transcript"):
        return str(parsed["transcript"])
    # fall back to whatever prose the model emitted, minus fences
    text = _FENCE_RE.sub(lambda m: m.group(1), model_text or "").strip()
    return text[:500]


def _safe_confidence(value: Any) -> float:
    try:
        c = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(max(c, 0.0), 1.0)


def _safe_amount(value: Any) -> float | None:
    """Real-model amount → float, or None when absent/blank/unparseable/≤0.
    None = unknown → low-confidence clarification path (§6.9); the 10M upper
    bound (§6.10) is enforced by the Transaction contract model, whose
    ValidationError also routes to that path."""
    if value is None or value == "":
        return None
    try:
        amt = float(value)
    except (TypeError, ValueError):
        return None
    return amt if amt > 0 else None


def _repair_call(client: DashScopeClient, settings: Settings,
                 bad_output: str, errors: list[str]) -> str:
    prompt = (
        "Your previous reply violated the required schema. Violations:\n- "
        + "\n- ".join(errors)
        + "\n\nPrevious reply:\n"
        + bad_output[:4000]
        + "\n\nReply again with ONLY the corrected JSON object per the system instructions."
    )
    try:
        return client.omni_chat(system=SYSTEM_PROMPT, user_text=prompt).text
    except DashScopeError:
        return bad_output  # assembled path will fall back to low_confidence


def _user_prompt(when: dt.datetime) -> str:
    return (
        "Parse this merchant voice note. Note timestamp (Asia/Karachi): "
        f"{when.isoformat()}. Reply with the JSON object only."
    )


def _coerce_occurred_at(value: str | dt.datetime | None) -> dt.datetime:
    if value is None:
        return dt.datetime.now(dt.timezone.utc).astimezone(
            dt.timezone(dt.timedelta(hours=5))
        )
    if isinstance(value, str):
        return dt.datetime.fromisoformat(value)
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone(dt.timedelta(hours=5)))  # Asia/Karachi
    return value
