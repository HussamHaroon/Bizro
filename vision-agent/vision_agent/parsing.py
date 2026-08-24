"""Robust JSON extraction from OCR model text + pydantic repair-retry.

The docs note models often wrap JSON answers in ```json fences (their own
ticket-extraction example strips them); we additionally handle leading prose
and balanced-brace scanning as defense in depth (notes.md §2).
"""

from __future__ import annotations

import json
from typing import Callable

from pydantic import ValidationError

from vision_agent.prompts import RECEIPT_EXTRACTION_PROMPT, repair_prompt
from vision_agent.schemas import ReceiptExtraction

MAX_TEXT_SCAN = 200_000  # don't scan megabyte-long answers


class ExtractionParseError(ValueError):
    """Model text could not be turned into a valid ReceiptExtraction."""

    def __init__(self, message: str, raw_text: str, problems: str = "") -> None:
        super().__init__(message)
        self.raw_text = raw_text
        self.problems = problems or message


def extract_json_block(text: str) -> str:
    """Pull the JSON object out of a model answer.

    Handles: ```json fenced blocks, plain JSON, JSON after leading prose.
    Raises ValueError when no balanced {...} object is found.
    """
    if not text or not text.strip():
        raise ValueError("empty model output")
    cleaned = text.strip()

    # 1. fenced block (```json ... ``` or ``` ... ```)
    if "```" in cleaned:
        parts = cleaned.split("```")
        for part in parts[1::2]:  # odd indices are inside fences
            candidate = part.strip()
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
            if candidate.startswith("{"):
                cleaned = candidate
                break

    # 2. first balanced {...} scan (also skips leading prose)
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("no JSON object found in model output")
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, min(len(cleaned), start + MAX_TEXT_SCAN)):
        char = cleaned[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start : index + 1]
    raise ValueError("unbalanced JSON object in model output")


def parse_extraction(text: str) -> ReceiptExtraction:
    """Model text -> ReceiptExtraction. Raises ExtractionParseError on failure."""
    try:
        block = extract_json_block(text)
        data = json.loads(block)
    except ValueError as exc:
        raise ExtractionParseError(f"JSON parse failed: {exc}", raw_text=text) from exc
    if not isinstance(data, dict):
        raise ExtractionParseError("top-level JSON is not an object", raw_text=text)
    try:
        return ReceiptExtraction.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        raise ExtractionParseError(f"schema validation failed: {problems}", raw_text=text, problems=problems) from exc


def parse_with_repair(
    call_model: Callable[[str], str],
    first_prompt: str = RECEIPT_EXTRACTION_PROMPT,
    repair_retries: int = 1,
) -> tuple[ReceiptExtraction, str, bool]:
    """Call the model, validate, and retry with a repair prompt on failure.

    ``call_model(prompt) -> response_text`` abstracts the transport (real client
    or mock). Returns (extraction, last_raw_text, repaired). Raises
    ExtractionParseError after exhausting retries — the pipeline then degrades
    to a low-confidence pending entry rather than guessing (SKILL.md hard rule).
    """
    raw = call_model(first_prompt)
    last_error: ExtractionParseError | None = None
    repaired = False
    for attempt in range(1 + max(0, repair_retries)):
        try:
            return parse_extraction(raw), raw, repaired
        except ExtractionParseError as exc:
            last_error = exc
            if attempt < max(0, repair_retries):
                raw = call_model(repair_prompt(raw[:4000], exc.problems))
                repaired = True
    assert last_error is not None
    raise last_error
