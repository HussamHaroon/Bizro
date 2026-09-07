# Server security review — 2026-09-07 (demo-eve) · Orchestrator audit

Verdict: **PASS-WITH-NOTES** — no P0/P1 findings. The build-time baseline (signature-gated
webhook, fail-closed prod boot, UUID media storage, pydantic boundaries, in-process rate
limits) held under this pass. Findings below are P2 hardening + accepted-demo-tradeoffs.

## Findings

- [P2] server/app/dispatch.py:618 — WhatsApp delivery failures embed upstream Graph-API error
  text (≤300 chars) in the `sent` block of webhook responses. Evidence: `deliver()` catches all
  exceptions and returns `str(exc)`. The text never reaches the merchant (merchant-visible
  replies are confirmation_ur/reply_ur only) and contains no secrets (token is header-side).
  Fix-not-taken: truncate to error `code`+`message` fields only. ROADMAP.
- [P2] server/app/middleware_security.py:14 — rate-limit state is per-process; on Vercel each
  lambda instance holds its own budget (effective limit × instances). Already documented in the
  module docstring; Redis is the roadmap swap. ROADMAP.
- [P2] server/app/ledger.py — two concurrent inserts could read the same `chain_tail` and fork
  the chain; `verify_chain` then reports a broken link (a false "tampering" signal on innocent
  concurrency). Demo reality: inserts happen only in the webhook's synchronous path, one message
  at a time. ROADMAP (serialize via a per-merchant advisory lock if traffic ever grows).
- [ROADMAP-ACCEPTED] server/app/api.py — confirm/patch/delete/verify-supplier endpoints are
  unauthenticated; protection today = UUIDv4 ids (unguessable) + general rate limit. **Say it out
  loud if asked**: "the demo API trusts possession of the merchant URL; production adds
  per-merchant auth tokens — it's a one-session feature, not architecture."
- [ROADMAP-ACCEPTED] server/app/webhook.py — `bizro_sim` unsigned envelope honored only for the
  three hardcoded sandbox wa_ids (evidence: `_sim_sandbox_only` + signature gate order); real
  wa_ids always require a valid X-Hub-Signature-256. No bypass path found.
- VERIFIED-CLEAN: wamid claim race (IntegrityError → rollback → dedupe, webhook.py
  `_claim_message_id`); media serving (UUID-parsed id → DB-owned path, no client-controlled
  path component); raw SQL (fixed DDL strings only, no interpolation); security headers on every
  response incl. 429s (middleware registered on the same app object the Vercel handler imports,
  api/index.py:29); secrets never echoed into merchant-visible payloads.

## Presenter one-liners (if a judge probes)
- Auth: "the demo trusts possession of the merchant's URL — production adds per-merchant tokens."
- Rate limits: "per-instance in memory at demo scale; Redis when it grows."
- Integrity: "the hash chain makes every later edit and every deletion detectable — by design."
