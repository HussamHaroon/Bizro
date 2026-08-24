"""OCR adapters: Qwen-VL-OCR and Qwen3.5-OCR behind ONE interface, plus mock.

The bake-off decides the winner (design.md §2/§9), never vibes — both real
adapters stay in the codebase forever; the winner is selected by ``OCR_MODEL``
(``vl`` | ``new``, notes.md D-V6), so the choice is reversible and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from vision_agent import mock_data
from vision_agent.config import OCR_MODEL_NEW, Settings, default_settings
from vision_agent.dashscope_client import DashScopeOcrClient, image_to_data_url
from vision_agent.parsing import ExtractionParseError, parse_with_repair
from vision_agent.prompts import RECEIPT_EXTRACTION_PROMPT
from vision_agent.schemas import ReceiptExtraction


@dataclass
class OcrResult:
    """Uniform adapter output, consumed by the pipeline and the bake-off."""

    model: str  # model id actually used ("mock:<id>" for mock runs, notes.md D-V7)
    extraction: ReceiptExtraction
    raw_text: str  # verbatim model answer (audit trail; goes into raw_output)
    mock: bool = False
    repaired: bool = False  # pydantic repair-retry had to fire
    error: str | None = None  # non-fatal adapter-level notes (e.g. repair count)
    timing_ms: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class OcrAdapter(Protocol):
    """The one interface every OCR backend implements."""

    name: str  # adapter nickname: "vl" | "new" | "mock"
    model: str  # concrete model id used on calls

    def extract(self, image_path: str | Path) -> OcrResult: ...


# ---------------------------------------------------------------- real adapters


class _RealOcrAdapter:
    """Shared implementation — both models take the identical compatible-mode
    payload (notes.md §2), so only the model id differs."""

    def __init__(self, settings: Settings, model: str, name: str) -> None:
        self._settings = settings
        self.model = model
        self.name = name
        self._client = DashScopeOcrClient(settings)

    def extract(self, image_path: str | Path) -> OcrResult:
        import time

        data_url = image_to_data_url(image_path, self._settings.max_image_bytes)
        started = time.perf_counter()

        def call(prompt: str) -> str:
            return self._client.chat(self.model, prompt, data_url)

        try:
            extraction, raw_text, repaired = parse_with_repair(
                call, RECEIPT_EXTRACTION_PROMPT, self._settings.ocr_repair_retries
            )
        except ExtractionParseError as exc:
            # Never guess: surface as an unreadable extraction (pipeline turns
            # this into a polite retry request / low-confidence reject).
            return OcrResult(
                model=self.model,
                extraction=ReceiptExtraction(
                    is_receipt=True,
                    items=[],
                    stated_total=None,
                    unclear_parts=[f"model output unparseable: {exc}"],
                    self_confidence=0.0,
                ),
                raw_text=exc.raw_text,
                mock=False,
                error=f"parse failed after retries: {exc}",
                timing_ms=(time.perf_counter() - started) * 1000,
            )
        timing_ms = (time.perf_counter() - started) * 1000
        return OcrResult(
            model=self.model,
            extraction=extraction,
            raw_text=raw_text,
            mock=False,
            repaired=repaired,
            timing_ms=timing_ms,
        )


class QwenVlOcrAdapter(_RealOcrAdapter):
    """Qwen-VL-OCR (Qwen3-VL base) — tables / general handwriting tuning.

    Cites: https://www.alibabacloud.com/help/en/model-studio/qwen-vl-ocr
    """

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, settings.model_ocr_vl, name="vl")


class Qwen35OcrAdapter(_RealOcrAdapter):
    """Qwen3.5-OCR (Qwen3.5 base) — certificates / business-document tuning.

    Cites: https://help.aliyun.com/zh/model-studio/qwen3-5-ocr
    """

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, settings.model_ocr_new, name="new")


# ---------------------------------------------------------------- mock adapter


class MockOcrAdapter:
    """Returns clearly-labeled synthetic OCR output (MOCK_MODE; D0-3 / D-V7).

    Scenario comes from the image filename (mock_data.scenario_for_path) or an
    explicit override. The raw text goes through the REAL parser, so mock mode
    exercises the same code path as production.
    """

    def __init__(self, settings: Settings, scenario: str | None = None) -> None:
        self._settings = settings
        self._forced_scenario = scenario
        # The mock echoes the *selected* real model id behind a "mock:" prefix,
        # so even mock output tells you which adapter the config would use.
        self.model = f"mock:{settings.selected_real_model}"
        self.name = "mock"

    def extract(self, image_path: str | Path) -> OcrResult:
        scenario = self._forced_scenario or mock_data.scenario_for_path(image_path)
        raw_text = mock_data.mock_raw_text(scenario)
        # Real parse path — fences, validators, everything.
        from vision_agent.parsing import parse_extraction

        try:
            extraction = parse_extraction(raw_text)
            error = None
        except ExtractionParseError as exc:  # pragma: no cover - mocks are valid
            extraction = ReceiptExtraction(
                is_receipt=True, items=[], unclear_parts=[str(exc)], self_confidence=0.0
            )
            error = f"mock raw text failed to parse: {exc}"
        return OcrResult(
            model=self.model,
            extraction=extraction,
            raw_text=raw_text,
            mock=True,
            error=error,
            extra={"scenario": scenario, "note": mock_data.mock_note(scenario)},
        )


# ---------------------------------------------------------------- selection


class OcrConfigError(RuntimeError):
    """MOCK_MODE=never but no DASHSCOPE_API_KEY (notes.md §2, HANDOFF.md ①)."""


def get_adapter(settings: Settings | None = None, scenario: str | None = None) -> OcrAdapter:
    """Resolve the adapter per MOCK_MODE + OCR_MODEL.

    auto   -> real adapter if DASHSCOPE_API_KEY present, else mock
    always -> mock (never presentable as real)
    never  -> real only; missing key raises OcrConfigError
    """
    settings = settings or default_settings()
    if settings.mock_mode == "always":
        return MockOcrAdapter(settings, scenario=scenario)
    if not settings.has_api_key:
        if settings.mock_mode == "never":
            raise OcrConfigError(
                "MOCK_MODE=never but DASHSCOPE_API_KEY is missing — set the key "
                "(HANDOFF.md ①) or use MOCK_MODE=auto"
            )
        return MockOcrAdapter(settings, scenario=scenario)  # auto
    adapter_cls = Qwen35OcrAdapter if settings.ocr_model == OCR_MODEL_NEW else QwenVlOcrAdapter
    return adapter_cls(settings)


def both_real_adapters(settings: Settings) -> list[OcrAdapter]:
    """Both adapters, always — for the bake-off (never a vibes decision)."""
    return [QwenVlOcrAdapter(settings), Qwen35OcrAdapter(settings)]
