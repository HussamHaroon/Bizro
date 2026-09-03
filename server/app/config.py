"""Env-driven configuration for the Bizro server.

Canonical environment contract: server/schema.md §5 / .env.example at repo root.
Loads `.env` from the repo root if present (python-dotenv), then falls back to
process env, then to the defaults below.

MOCK_MODE semantics (STATUS.md D0-3):
- auto    → real calls when the needed credential exists, clearly-labeled mock otherwise
- always  → always mock, even if credentials exist (demo-safe)
- never   → never mock; a missing credential raises when a real call is attempted
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Alibaba Cloud Model Studio / DashScope ---
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model_voice: str = "qwen3.5-omni-plus"
    model_ocr_vl: str = "qwen-vl-ocr"
    model_ocr_new: str = "qwen3.5-ocr"
    model_reasoning: str = "qwen3.7-plus"

    # --- WhatsApp Cloud API ---
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = "bizro-verify"
    # Optional: App Secret for X-Hub-Signature-256 validation. When empty,
    # signature validation is DISABLED (logged + surfaced in /health) so the
    # zero-credential simulator path works (SKILL.md hard rule).
    whatsapp_app_secret: str = ""

    # --- Storage / behavior ---
    database_url: str = "sqlite:///./bizro.db"
    # Serverless hosts (Vercel) have a read-only FS except /tmp — override with
    # MEDIA_DIR=/tmp/media there (D6-2 provider/deploy switch).
    media_dir_override: str = Field(default="", validation_alias=AliasChoices("MEDIA_DIR", "media_dir_override"))
    mock_mode: str = "auto"  # auto | always | never
    confidence_confirm_threshold: float = 0.75
    numeral_style: str = "western"  # western | urdu
    port: int = 8000

    @property
    def media_dir(self) -> Path:
        if self.media_dir_override:
            return Path(self.media_dir_override)
        return REPO_ROOT / "media"

    def dashscope_is_live(self) -> bool:
        """True when DashScope calls will hit the real API (never in MOCK_MODE=always)."""
        if self.mock_mode == "always":
            return False
        if self.mock_mode == "never":
            return bool(self.dashscope_api_key)  # caller must raise if missing
        return bool(self.dashscope_api_key)  # auto

    def whatsapp_is_live(self) -> bool:
        """True when outbound messages go to the real WhatsApp Cloud API."""
        if self.mock_mode == "always":
            return False
        return bool(self.whatsapp_token and self.whatsapp_phone_number_id)

    def signature_enforced(self) -> bool:
        return bool(self.whatsapp_app_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def ensure_repo_root_on_path() -> None:
    """Make repo-root packages (`voice_agent`, `vision_agent`, `credit_agent`)
    importable regardless of the cwd uvicorn was started from.

    The on-disk agent directories are hyphenated (`voice-agent/`, ...), so both
    the repo root and each hyphenated directory are added — whichever layout the
    parallel pipeline agents shipped wins at import time (see dispatch.py).
    """
    candidates = [
        REPO_ROOT,
        REPO_ROOT / "voice-agent",
        REPO_ROOT / "vision-agent",
        REPO_ROOT / "credit-agent",
    ]
    for path in candidates:
        p = str(path)
        if p not in sys.path:
            sys.path.insert(0, p)
