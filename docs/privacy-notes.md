# Bizro — data notes in plain language

This is the plain-language companion to `PRIVACY_POLICY.md` (which has an
Urdu summary). No lawyer-speak — just what Bizro keeps, why, for how long,
who can see it, and how to make it go away.

## What Bizro stores per entry

When a shopkeeper sends a voice note or a receipt photo, Bizro keeps:

- **The original bytes** — the voice note (audio, capped at 16 MB) or the
  receipt photo (capped at 5 MB). These are sha256-hashed on arrival and
  kept as the audit trail: if anyone ever asks "where did this 3,000-rupee
  entry come from?", the answer is the actual recording or photo, not a
  summary of it.
- **The transcript** — what the speech-to-text engine heard (voice notes
  only).
- **The extracted fields** — the structured ledger line: sale/purchase/udhar
  type, amount in PKR, item lines, date, description, which model parsed it,
  the raw model output, and a confidence score.
- **Customer names** — as the merchant speaks them ("sold ghee to Rahmat").
  Customer **phone numbers** are stored **only when the merchant provides
  one** (e.g. for a reminder). Many entries have no phone at all.

Plus the merchant's own WhatsApp number and display name, which is how the
account works at all.

## Why it's kept

The bytes are the point, not a side effect. A ledger that only kept the
parsed numbers would be a ledger that couldn't be checked — by the merchant
("did I really say 3,000?"), by a loan officer weighing a credit report, or
by Bizro itself when a parse looks wrong and the merchant is asked to
confirm. The audit trail is what makes the whole thing more than a chatbot's
word.

## Who processes it

The audio, photos and transcripts are sent to the configured AI providers —
Alibaba Cloud Model Studio (ASR, OCR, parsing, narratives) and, depending on
configuration, Groq or OpenAI for transcription — strictly to produce the
ledger entry. Per the privacy policy, providers may not use the content to
train their models. Nothing is sold, and reports go nowhere unless the
merchant shares them.

## Retention (recommended)

Bizro's guidance for anyone running a deployment:

- **Audio and photo bytes: purge after 24 months.** They exist for the audit
  trail; two years is generous for any dispute window, and old voice of
  real people shouldn't sit around forever.
- **Ledger rows: keep.** They are the merchant's books — the record of the
  business itself. They stay until the merchant asks for deletion.
- Reports and message logs follow the ledger they belong to.

The current code keeps media bytes until deleted; the 24-month purge is a
recommendation a production deployment should implement as a scheduled job.

## Deletion

The merchant sends **"data delete"** in the Bizro WhatsApp chat (or emails
the contact in the privacy policy). That removes the merchant's account and
records — ledger entries, customer records, stored audio/photos, generated
reports — within 30 days. The ledger's integrity chain records that entries
were removed; it does not keep the removed data itself.

## Who can see it

- **The merchant** — their ledger, via WhatsApp and the dashboard.
- **The lending institution's loan officer** — only what the merchant
  shares: a Credit Readiness report, deliberately, when applying. Not the
  raw chat history by default.
- **The operators of the deployment** — the database, as with any hosted
  service. Access is restricted to the service account.

## About customers (the people in the entries)

This is the part worth saying plainly:

- Customers are **identifiable** in udhar entries — a name, sometimes a
  phone number, attached to an amount the merchant says they owe.
- Those customers never messaging Bizro don't have an account, didn't sign
  up, and may not know a ledger line about them exists.
- Their phone number is only stored when the merchant provides it — but the
  name-plus-amount alone is personal data.

**Recommendation:** merchants using Bizro for udhar should tell customers
they keep a digital ledger that may include their name (and number if a
reminder is wanted). A short verbal disclosure — "I keep khata on WhatsApp
now" — is a reasonable minimum; deployment operators should put proper
notice language in the onboarding flow. This is a product gap, flagged
honestly rather than smoothed over.

## Contact

Questions or deletion requests: see the contact in `PRIVACY_POLICY.md`.
