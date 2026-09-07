"""Language mirroring (owner ruling 2026-10-02): the reply language mirrors
the inbound message — Urdu script in → Urdu out, otherwise simple English.
Preference persists per merchant (merchant_settings.language) so button taps
and photos (no text of their own) follow the conversation's last language."""

from __future__ import annotations

from sqlalchemy.orm import Session

from .db import Merchant, MerchantSettings

# (urdu, english) pairs for every webhook-owned reply constant.
HELP_PAIR = (
    "بزرو کو ایک وائس نوٹ یا تصویر بھیجیں۔ اپنی فروخت، خرچ، یا ادھار بول کر "
    "بتائیں، یا رسید کی تصویر بھیجیں۔ اندراج درست ہو تو '1' اور ہٹانے کے "
    "لیے '0' لکھیں۔",
    "Send Bizro a voice note or a photo. Speak your sale, expense, or credit "
    "entry, or send a picture of a receipt. Reply '1' to confirm an entry "
    "and '0' to remove it.",
)
MEDIA_INVALID_PAIR = (
    "یہ فائل پڑھی نہیں جا سکی یا بہت بڑی تھی۔ چھوٹی فائل بھیجیں۔",
    "We could not read that file, or it was too big. Please send a smaller "
    "file and try again.",
)
TEXT_MISS_PAIR = (
    "پڑھ نہیں سکے — رقم دوبارہ بتائیں۔",
    "I couldn't read that — try saying the amount again.",
)
MODEL_OUTAGE_PAIR = (
    "بزرو ابھی AI سروس سے نہیں جڑ سکا۔ کچھ محفوظ نہیں ہوا۔ ایک منٹ بعد "
    "دوبارہ بھیجیں۔",
    "Bizro could not reach the AI service just now. Nothing was saved. "
    "Please send the message again in a minute.",
)
ONBOARDING_WELCOME_PAIR = (
    "بزرو میں خوش آمدید! بزرو آپ کی آوازی کھاتہ ہے۔ وائس نوٹ یا رسید کی "
    "تصویر بھیجیں، اندراج ہم لکھ دیں گے۔ یہی ریکارڈ آپ کی کریڈٹ ہسٹری بھی "
    "بناتا ہے۔",
    "Welcome to Bizro! Bizro is your voice ledger. Send a voice note or a "
    "receipt photo, and we write the entry for you. The same record also "
    "builds your credit history.",
)
ONBOARDING_HOWTO_PAIR = (
    "استعمال: ۱) فروخت یا ادھار کا وائس نوٹ بھیجیں۔ ۲) خریداری کی رسید کی "
    "تصویر بھیجیں۔ ۳) اندراج آئے تو درست ہو تو '1' لکھیں۔",
    "How to use it: 1) Send a voice note about a sale or credit. 2) Send a "
    "photo of a purchase receipt. 3) When an entry comes in, reply '1' if "
    "it is correct.",
)
CONFIRM_ACK_PAIR = ("شکریہ! اندراج درست کر دیا گیا۔", "Thank you! The entry is confirmed.")
CORRECT_ACK_PAIR = (
    "ٹھیک ہے — اندراج محفوظ ہے مگر زیرِ التوا ہے۔ درست رقم کا نیا وائس نوٹ بھیجیں۔",
    "Okay — the entry is saved but still pending. Please send a new voice "
    "note with the correct amount.",
)
NO_PENDING_PAIR = ("کوئی زیرِ التوا اندراج نہیں ملا۔", "No pending entry was found.")
REMOVED_ACK_PAIR = ("ٹھیک ہے، اندراج ہٹا دیا گیا۔", "Okay, the entry was removed.")


def pick(lang: str | None, pair: tuple[str, str]) -> str:
    return pair[0] if lang == "ur" else pair[1]


def onboarding_sequence(lang: str | None) -> tuple[str, str]:
    return (
        pick(lang, ONBOARDING_WELCOME_PAIR),
        pick(lang, ONBOARDING_HOWTO_PAIR),
    )


def detect_language(text: str) -> str:
    """"ur" when materially Arabic-script, else "en" (mirrors the
    voice-agent helper; kept dependency-free for the server package)."""
    s = text or ""
    letters = [ch for ch in s if ch.isalpha()]
    if not letters:
        return "en"
    arabic = sum(
        1 for ch in letters if "؀" <= ch <= "ۿ" or "ݐ" <= ch <= "ݿ"
    )
    return "ur" if arabic / len(letters) >= 0.10 else "en"


def get_merchant_lang(session: Session, merchant: Merchant) -> str:
    row = (
        session.query(MerchantSettings)
        .filter(MerchantSettings.merchant_id == merchant.id)
        .first()
    )
    return (getattr(row, "language", None) or "en") if row else "en"


def set_merchant_lang(session: Session, merchant: Merchant, lang: str) -> None:
    """Best-effort preference persistence — never breaks the reply path."""
    if lang not in ("ur", "en"):
        return
    try:
        row = (
            session.query(MerchantSettings)
            .filter(MerchantSettings.merchant_id == merchant.id)
            .first()
        )
        if row is None:
            row = MerchantSettings(merchant_id=merchant.id, language=lang)
            session.add(row)
        else:
            row.language = lang
        session.commit()
    except Exception:  # noqa: BLE001
        session.rollback()
