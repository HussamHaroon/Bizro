# Two-way toggle — Phase 1 findings (file:line evidence)

Branch `agent5/two-way-toggle`, 2026-09-07. Feature: per-merchant
`two_way_confirmation_required` (DEFAULT OFF, officer-flipped). OFF = exactly
today's rubric; ON = +0.15 CORROBORATION pillar, existing pillars × 0.85.
Demo-eve constraints (owner, tonight): OFF path byte-identical; ON note is ONE
appended clause; the only flag exposure in the payload is
`report_json.readiness.two_way_required`.

## 1. Where the column goes — server/app/db.py

- `MerchantSettings` at `server/app/db.py:61-83`: PK `merchant_id` (FK
  merchants.id, :76-78), `language` (:79), `numeral_style` (:80),
  `updated_at` (:81-83). The new column goes after `numeral_style`:
  `two_way_confirmation_required: Mapped[bool] = mapped_column(Boolean,
  default=False, nullable=False)`. No CHECK needed (plain bool).
- `_ensure_additive_columns` at `server/app/db.py:345-366` is the additive
  migration pattern: column-presence check via `inspector.get_columns`, then
  `ALTER TABLE ... ADD COLUMN` inside one `engine.begin()`. Today it handles
  `outbound_messages.payload` (:356-358) and the three transactions columns
  (:359-366). The merchant_settings branch slots into the same block:
  `ALTER TABLE merchant_settings ADD COLUMN two_way_confirmation_required
  BOOLEAN NOT NULL DEFAULT FALSE` — SQLite backfills existing rows with 0,
  Postgres uses a fast default; same DDL works on both dialects.
- Guard note: the function early-returns when `outbound_messages` is missing
  (:352-354). Safe to keep — a FRESH database gets the column from
  `create_all` (:281), and any pre-existing DB predating the toggle still has
  `outbound_messages` (original schema), so the guard never skips the new
  ALTER on a DB that needs it.
- `Boolean` must join the `sqlalchemy` import list at `server/app/db.py:17-28`
  (not currently imported).

## 2. Exact settings wire shape (today)

- `MerchantSettingsPut` — `server/app/schemas.py:100-108`:
  `model_config = ConfigDict(extra="forbid")` (:105) so unknown keys 422;
  fields `language: Literal["ur","en","mixed"] | None`, `numeral_style:
  Literal["western","urdu"] | None`. New field:
  `two_way_confirmation_required: bool | None = None`.
- Wire out — `server/app/api.py:1086-1091` `_settings_to_wire` returns
  `{language, numeral_style, updated_at}`; gains `two_way_confirmation_required`.
- GET — `server/app/api.py:1094-1107`: missing row → implied defaults dict
  `{"language": "mixed", "numeral_style": _default_numeral_style(),
  "updated_at": None}` (:1103-1107); gains `"two_way_confirmation_required":
  False` (a missing settings row can never mean ON).
- PUT — `server/app/api.py:1110-1142`: `model_dump(exclude_unset=True)` then
  explicit-null filter `if v is not None` (:1116-1119). `False` survives the
  filter, so a PUT of only `{"two_way_confirmation_required": false}` is a
  valid non-empty save (and the empty-body 422 at :1120-1121 still fires for
  `{}` / all-null bodies). First-save constructor (:1129-1134) must pass
  `two_way_confirmation_required=updates.get(..., False)`; the existing-row
  branch (:1137-1138, generic setattr) needs no change.
- Breaking existing pins (must be updated with the feature):
  `server/tests/test_settings.py:60` and `:198` assert the FULL
  default-GET JSON by equality — both gain
  `"two_way_confirmation_required": False`. Roundtrip tests (:91-102) compare
  PUT response to GET response, both from `_settings_to_wire`, so they pass
  unchanged.

## 3. How corroboration_pct reaches score() — today it doesn't

- `credit-agent/credit_agent/report.py:87`: `scored = score(agg)` runs BEFORE
  `trust = compute_trust(list(txs))` at :94 — corroboration is computed after
  scoring and used purely as §12 disclosure.
- `compute_trust` — `credit-agent/credit_agent/trust.py:48-71`: filters to
  `CONFIRMED_STATUSES` (:51), sums revenue kinds `("sale",
  "udhar_settlement")` (:35, = aggregates cash_in), tiers via
  `normalize_tier` (:43-45; unknown/NULL → self_reported), returns
  `corroboration_pct = round(corroborated/total*100, 1)` with an honest 0.0
  when total is 0 (:64). This is the exact number the new pillar consumes.
- Plan: move the `compute_trust` call above `score()` and pass
  `trust["corroboration_pct"]` plus the merchant flag into `score()`.
- `score()` — `credit-agent/credit_agent/rubric.py:102-135`. Weights :18-21
  (0.40/0.25/0.20/0.15); insufficient-data gate :103-113 (unchanged — the new
  pillar never rescues a thin ledger); weighted total :127;
  `round(total*100)` :128; bands :23-24, :129 (unchanged). Pillars render as
  `name -> (raw rounded 3, weight, note)` (:134). No renderer iterates pillars
  (grep: only rubric.py/report.py; narrative.py, committee_summary.py,
  render.py never touch the dict), so adding a `"corroboration"` key is safe.
- New signature: `score(agg, corroboration_pct=None, two_way_required=False)`
  — default args keep every existing caller byte-identical (single call site
  in product code: report.py:87).

## 4. Reading the flag in report.py

- `credit-agent/credit_agent/db_view.py` mirrors ONLY
  merchants/customers/media_blobs/transactions/credit_reports (:21-94) — no
  `MerchantSettings` ORM, and db_view.py is outside this agent's ownership.
- Chosen approach: raw SELECT on the report session in report.py:
  `SELECT two_way_confirmation_required FROM merchant_settings WHERE
  merchant_id = :mid`, wrapped in `except SQLAlchemyError → False` (covers a
  standalone credit-agent DB without the table, and any pre-migration
  deployment — a failed read can only mean OFF, i.e. today's semantics).
- Dialect binding (verified empirically against the repo venv): SQLAlchemy
  `Uuid` stores CHAR(32) hex WITHOUT dashes on SQLite (`3b3dab52e7c7...`;
  binding `str(mid)` matched 0 rows, `mid.hex` matched 1). Postgres keeps
  native UUID and binds `uuid.UUID` directly. So: bind `mid.hex` on sqlite,
  `mid` on postgresql.
- `bool(val)` normalizes SQLite 0/1 and Postgres boolean alike.

## 5. Boundary cases — score with the flag ON vs OFF

With T = today's weighted total (0..1) and c = clamp(corroboration_pct/100, 0, 1):

| flag | corroboration | weighted total | score |
|---|---|---|---|
| OFF | (ignored) | T | round(100·T) — today's exact number |
| ON | 0% | 0.85·T | strictly < OFF for any T>0 (gap 15·T; ≥1 score point once T ≥ 0.067) |
| ON | 50% | 0.85·T + 0.075 | crosses OFF exactly at T=0.5 (score 50); lower below, higher above |
| ON | 100% | 0.85·T + 0.15 | ≥ OFF for all T ≤ 1 (equality only at T=1) |

- Renormalized weights when ON: consistency 0.34, confidence 0.2125, cashflow
  0.17, cleanliness 0.1275, corroboration 0.15 — sum exactly 1.0.
- `corroboration_pct` with the flag OFF is ignored entirely
  (`two_way_required and corroboration_pct is not None` gate) — OFF is
  byte-identical to the pre-feature rubric even when a pct is passed.
- insufficient_data gate (:103-113) runs before any pillar math; bands and
  `BAND_LABELS_UR` untouched.

## 6. Demo-invisibility contract (owner adjustment, tonight)

1. OFF byte-identical: `readiness.note` stays the byte-equal
   `INDICATOR_NOTE` (rubric.py:36) — the existing pin
   `credit-agent/tests/test_honest_labeling.py:39` keeps passing unmodified;
   no `note_ur` key when OFF; pillars unchanged.
2. ON: `note` = INDICATOR_NOTE + `" · two-way confirmation required:
   unconfirmed revenue lowers this score"` (one appended clause, no banner);
   a short `note_ur` clause rides alongside (additive key, only when ON).
3. The single flag exposure anywhere in the payload is
   `report_json.readiness.two_way_required` (bool, always present). The
   dashboard never reads it (verified: dashboard/src reads
   readiness.score_0_100/level/summary_en/summary_ur via reportAdapter.ts;
   `readiness.note` has no dashboard consumer), so default demo rendering is
   untouched.

## 7. Follow-ups outside this worktree's ownership

- `server/schema.md` §8 (settings wire) and the report §6.5 skeleton need the
  `two_way_confirmation_required` field + `readiness.two_way_required`
  documented — filed for the Orchestrator/doc owner.
- The server-fallback report path (`server/app/api.py:1145+`
  `_refresh_report` → `dispatch.generate_report_preview`, dispatch.py not
  owned) builds its own payload when credit_agent is unavailable; it does not
  gain the flag — acceptable (fallback is a mock artifact, §6.3).
- Officer Review screen toggle UI: separate agent builds against
  PUT/GET `/api/merchants/{id}/settings` field `two_way_confirmation_required`.
