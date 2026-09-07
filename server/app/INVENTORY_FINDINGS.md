# INVENTORY_FINDINGS.md — inventory feature, phase 1 (findings before code)

Scope ruling (demo tomorrow): inventory is **DERIVED, not stored** — zero new
tables, zero migrations. Stock per item = Σ qty from `expense` item_lines
(goods IN) − Σ qty from `sale` + `udhar_given` item_lines (goods OUT), computed
over existing transactions. Agent: inventory-feature agent, branch
`agent3/inventory`, worktree `.worktrees3/inventory`.

## (a) Where item_lines live and their exact shape

- **`server/app/db.py:161`** — the physical store: `item_lines: Mapped[list | None]
  = mapped_column(JSONVariant)` on `Transaction` (JSON on SQLite, JSONB on
  Postgres). Nullable; a list of line dicts, no constraint on contents.
- **`server/app/schemas.py:38-45`** — the wire contract (`model_config =
  ConfigDict(extra="allow")`):

  ```python
  class ItemLine(BaseModel):
      item: str
      qty: float | None = None
      unit: str | None = None
      unit_price: float | None = None
      line_total: float | None = None
  ```

- **server/schema.md §1** (file `server/schema.md`; the repo-root copy currently
  holds only addenda §7-11 — base §1-§6 verified via git history,
  `git show 1cf3029:server/schema.md`, lines 37-39):

  ```json
  "item_lines": [
    { "item": "chai patti", "qty": 2, "unit": "packet", "unit_price": 350, "line_total": 700 }
  ]
  ```

- Round-trip: **`server/app/schemas.py:144`** — `transaction_to_wire` emits
  `"item_lines": tx.item_lines or []`, so the dashboard already receives these
  dicts on every transaction row (`dashboard/src/types/schema.ts:39-45` mirrors
  the shape as `ItemLine`).
- Writes come from both pipelines: **`server/app/dispatch.py:510`** persists
  `item_lines=[line.model_dump() for line in parsed.item_lines]` (voice path
  included, not only OCR).

## (b) How many real fields exist

Five declared fields per line — `item`, `qty`, `unit`, `unit_price`,
`line_total` — but only **`item` is guaranteed** (schemas.py:39; everything
else defaults to None). Inventory needs exactly three:

| field    | required by us | guard |
|----------|----------------|-------|
| `item`   | yes            | skip line when normalized name is empty |
| `qty`    | yes            | skip line when missing or ≤ 0 (same guard as credit-agent `data_quality.py:102-105`) |
| `unit`   | display only   | first-seen unit wins; may be None |

`line_total`/`unit_price` are money fields — out of scope for quantity stock.
Stored rows can pre-date the pydantic contract, so reads must be defensive:
`isinstance(item_lines, list)` per line (credit-agent `_lines`,
`data_quality.py:46-48`) and `str()`/`float()` coercions.

## (c) Normalization rule for merging item spellings

Reuse **`credit-agent/credit_agent/data_quality.py:39-43` `_norm_item`** via
`from credit_agent.data_quality import _norm_item` (importable: server
`config.py:118-135 ensure_repo_root_on_path` adds the hyphenated `credit-agent/`
dir to `sys.path`, and `server/tests/conftest.py` does the same for tests —
proved by credit_agent imports elsewhere in server tests):

1. `unicodedata.normalize("NFC", name)` — one canonical form for Urdu text
2. `.casefold()` — case-insensitive (stricter than lower())
3. translate Urdu-Indic digits `۰۱۲۳۴۵۶۷۸۹` → ASCII `0123456789`
4. collapse whitespace runs to single spaces
5. strip punctuation `[^\w\s]` (regex `\w` keeps Urdu letters; drops commas/dots)
6. `.strip()`

So `"Basmati Rice  5kg bag"` and `"basmati rice 5kg bag"` merge; `""` after
normalization ⇒ line skipped. Deliberately NOT doing fuzzy/similarity matching
(“atta 10kg” vs “atta 20kg” stay separate items) — merging different pack sizes
would corrupt quantities.

## (d) Risks

1. **Qty semantics / direction (schema.md §1 rules).** `amount_pkr` is always
   positive; *direction is implied by kind* (schema.md §1: `sale` — customer
   paid; `expense` — supplier purchase; `udhar_given` — credit extended;
   `udhar_settlement` — customer repaid money). Goods flow therefore is:
   `expense` = goods IN; `sale` + `udhar_given` = goods OUT;
   **`udhar_settlement` = money only, NO goods movement** — the goods left the
   shop when the `udhar_given` row was logged; counting it again would
   double-subtract. This is exactly the mapping credit-agent already ships for
   stock coherence (`data_quality.py:106-109`, schema.md §9 addendum:
   `stock_coherence: per item, sold qty vs purchased qty`).
2. **Systematic undercount of goods OUT.** schema.md §1: "`item_lines` present
   for OCR-parsed expenses; empty list otherwise" — voice sales frequently have
   no item lines, while supplier receipts almost always do. `in_stock` will
   drift negative on busy items without any dishonesty. Consequence: a negative
   number is surfaced as the **"negative" flag (disclosure, same framing as
   §9's stock_coherence violations)** — never hidden, never "corrected", and
   the card's note says stock is *derived from logged lines*.
3. **Name/unit ambiguity.** Same normalized name can carry different units
   across lines (`kg` purchase vs `bag` sale; OCR may read "Basmati Rice 5kg
   Bag" one week and "Chawal 5kg" the next). We sum quantities per normalized
   name and display the first-seen unit; mixed-unit rows are an honest
   approximation, flagged in the response `note`. Also: `status='rejected'`
   rows must be excluded (credit-agent does — `data_quality.py:77`) and the
   udhar radar's convention of counting `confirmed+pending+edited` (api.py udhar
   endpoint) is followed (rejected only).

## (e) Endpoint + UI plan (5 lines)

1. `server/app/inventory.py::compute_inventory(session, merchant_id)` →
   `{"merchant_id", "items": [{"item", "unit", "bought", "sold", "in_stock",
   "flag"}...], "note"}`; in_stock = bought − sold; flag = `"negative"` when
   in_stock < 0, `"low"` when 0 ≤ in_stock ≤ max(2, 10% of bought), else `"ok"`.
2. `GET /api/merchants/{merchant_id}/inventory` appended to api.py following
   the udhar endpoint pattern (`db_session`, `_get_merchant` → 400/404, `me`
   sentinel for free); documented in the api.py module header.
3. Tests `server/tests/test_inventory.py`: empty merchant → empty items;
   seeded bought/sold math; negative flagged; case-insensitive merge; 404.
   Baseline 146 green must stay green.
4. Dashboard: `InventoryView` type in `types/schema.ts`, `fetchInventory()`
   optional-endpoint client fn (absence → null, chip hidden — the
   streak/verify pattern), `deriveInventory` over mock fixtures.
5. `components/InventoryCard.tsx` on the ledger screen below UdharRadar:
   per-item rows (name, in-stock number, icon + word "low"/"negative" in
   ledger-red — never color alone), rule-lines not shadows, 48px targets, empty
   state "Send receipt photos to track stock". Khata Modern tokens only.
