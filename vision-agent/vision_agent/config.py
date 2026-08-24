"""Environment-driven configuration for the vision pipeline.

Reads the shared `.env.example` contract (schema.md §5) plus the vision-only
variables documented in vision-agent/notes.md D-V6. Vision-only vars are NOT
added to `.env.example` (Orchestrator owns that file); every one has a safe
default so the package runs with zero configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

# Values OCR_MODEL accepts -> which real adapter wins (bake-off decides; SKILL.md).
OCR_MODEL_VL = "vl"  # -> MODEL_OCR_VL (qwen-vl-ocr)
OCR_MODEL_NEW = "new"  # -> MODEL_OCR_NEW (qwen3.5-ocr)


@dataclass(frozen=True)
class Settings:
    # --- shared contract (.env.example / schema.md §5) ---
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model_ocr_vl: str = "qwen-vl-ocr"
    model_ocr_new: str = "qwen3.5-ocr"
    mock_mode: str = "auto"  # auto | always | never
    confidence_confirm_threshold: float = 0.75
    numeral_style: str = "western"  # western | urdu (schema.md §1)

    # --- vision-only (notes.md D-V6) ---
    ocr_model: str = OCR_MODEL_VL  # vl | new — the bake-off winner goes here
    price_anomaly_ratio: float = 0.25  # unit price deviates >25% from history median
    price_anomaly_min_samples: int = 1  # historical prices needed before judging
    price_history_window: int = 5  # median over the last N historical prices
    total_mismatch_tolerance_pkd: float = 1.0  # abs PKR slack on stated-vs-computed
    duplicate_window_minutes: int = 30  # same supplier+amount inside N minutes
    ocr_timeout_seconds: int = 60
    ocr_repair_retries: int = 1  # pydantic repair-retry rounds (SKILL.md #2)
    max_image_bytes: int = 20 * 1024 * 1024  # 20 MB (docs: Response-API image cap)

    @property
    def has_api_key(self) -> bool:
        return bool(self.dashscope_api_key)

    @property
    def selected_real_model(self) -> str:
        """Model ID of the winning adapter per OCR_MODEL (notes.md D-V6)."""
        return self.model_ocr_new if self.ocr_model == OCR_MODEL_NEW else self.model_ocr_vl

    def use_mock(self) -> bool:
        """MOCK_MODE resolution.

        auto    -> mock iff no DASHSCOPE_API_KEY (Orchestrator decision D0-3)
        always  -> always mock (clearly labeled, never presentable as real)
        never   -> real calls only; missing key is a configuration error
        """
        if self.mock_mode == "always":
            return True
        if self.mock_mode == "never":
            return False
        return not self.has_api_key  # auto


def load_settings(env: dict[str, str] | None = None) -> Settings:
    """Build Settings from env (injectable for tests; defaults mirror .env.example)."""
    source = os.environ if env is None else {**os.environ, **(env or {})}

    def get(name: str, default: str) -> str:
        value = str(source.get(name, "")).strip()
        return value or default

    def get_float(name: str, default: float) -> float:
        return _float(get(name, str(default)), default)

    def get_int(name: str, default: int) -> int:
        return _int(get(name, str(default)), default)

    return Settings(
        dashscope_api_key=get("DASHSCOPE_API_KEY", ""),
        dashscope_base_url=get("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        model_ocr_vl=get("MODEL_OCR_VL", "qwen-vl-ocr"),
        model_ocr_new=get("MODEL_OCR_NEW", "qwen3.5-ocr"),
        mock_mode=get("MOCK_MODE", "auto").lower(),
        confidence_confirm_threshold=get_float("CONFIDENCE_CONFIRM_THRESHOLD", 0.75),
        numeral_style=get("NUMERAL_STYLE", "western").lower(),
        ocr_model=get("OCR_MODEL", OCR_MODEL_VL).lower(),
        price_anomaly_ratio=get_float("PRICE_ANOMALY_RATIO", 0.25),
        price_anomaly_min_samples=get_int("PRICE_ANOMALY_MIN_SAMPLES", 1),
        price_history_window=get_int("PRICE_HISTORY_WINDOW", 5),
        total_mismatch_tolerance_pkd=get_float("TOTAL_MISMATCH_TOLERANCE_PKD", 1.0),
        duplicate_window_minutes=get_int("DUPLICATE_WINDOW_MINUTES", 30),
        ocr_timeout_seconds=get_int("OCR_TIMEOUT_SECONDS", 60),
        ocr_repair_retries=get_int("OCR_REPAIR_RETRIES", 1),
        max_image_bytes=get_int("MAX_IMAGE_BYTES", 20 * 1024 * 1024),
    )


def _float(text: str, default: float) -> float:
    try:
        return float(text)
    except ValueError:
        return default


def _int(text: str, default: int) -> int:
    try:
        return int(text)
    except ValueError:
        return default


@lru_cache(maxsize=1)
def default_settings() -> Settings:
    """Process-env settings, cached. Tests use load_settings(env={...})."""
    return load_settings()
