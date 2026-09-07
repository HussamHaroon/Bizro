# Deterministic structuring accuracy — benchmark results

_Generated 2026-10-24 by `voice-agent/scripts/benchmark_structuring.py` from `transcripts.jsonl` (32 fixtures). Re-run the script to regenerate; floors are asserted in CI by `voice-agent/tests/test_benchmark.py`._

## Scope — read this before quoting any number

This benchmark measures the **deterministic parsing layers only**:

1. **Number normalization** — spoken Urdu / Roman-Urdu number words →
   bracketed digit hints, with a non-destructiveness invariant
   (stripping hints reproduces the verbatim transcript byte-for-byte).
2. **Amount-signal counting** (item quantities must NOT look like amounts).
3. **Person-join counting** (ASCII + Urdu comma, aur/and/or).
4. **Collapse-guard rulings** — merged-total detection fires on
   under-reported people and passes correct extractions untouched.
5. **Validation + confirmation** — hand-authored model-shaped JSON run
   through the pipeline's real `_assemble_all`: schema validation, the
   ambiguous-must-flag guarantee (unclear amount → `amount_pkr=null` +
   `flag=low_confidence`, never a guess), guard clarifications, and a
   confirmation with the trailing question present.

**It does NOT measure end-to-end model accuracy.** ASR quality and the
language model's extraction accuracy on real shop audio are unmeasured
here: fixtures are curated transcripts, not live audio, and the
structured outputs paired with them are hand-authored. Measuring that
requires real recorded voice notes and a **human** to listen,
transcribe and judge — a pending task, and the prerequisite for any
end-to-end accuracy claim in pitch or demo material.

## Category results

| Category | Fixtures | Passed | Accuracy | Floor | Verdict |
|---|---|---|---|---|---|
| single_entry | 8 | 8 | 100.0% | 100% | PASS |
| multi_split | 11 | 11 | 100.0% | 90% | PASS |
| ambiguous_flag | 6 | 6 | 100.0% | 100% | PASS |
| phonetic_numbers | 7 | 7 | 100.0% | 100% | PASS |
| normalization (all fixtures) | 72 | 72 | 100.0% | 100% | PASS |
| collapse-guard rulings | 44 | 44 | 100.0% | 100% | PASS |
| **Overall** | 32 | 32 | 100.0% | 90% | PASS |

## Methodology

- 32 curated voice-note transcripts (single_entry: 8, multi_split: 11, ambiguous_flag: 6, phonetic_numbers: 7), written the way karyana merchants actually speak: Urdu script and
  Roman Urdu, numbers as words, code-switched English, multi-person
  notes, ambiguous amounts, ledger queries.
- Each fixture runs through the SAME functions the webhook path uses:
  `normalize_spoken_numbers`, `count_amount_signals`,
  `count_person_joins`, `collapse_suspected`, and `_assemble_all`
  (mock-marked: every assembled row carries `mock: true` and is never
  presentable as real model output).
- Known deterministic limitation (documented, not hidden): the
  collapse guard is a best-effort heuristic — a two-person note whose
  amounts are both small hundreds can produce fewer strong signals
  than persons; the guard then stays silent rather than nagging. It
  NEVER dismisses a suspicion: silence only means no evidence of a
  merged total, and a wrong number still cannot slip through as a
  confirmed entry because every entry is confirmed by the merchant.

## Failures

None — every fixture passed every declared check.
