"""Env-driven settings for the voice pipeline.

Same conventions as the repo-root `.env.example` (canonical list: server/schema.md §5).
Loads `.env` from the repo root if present so Windows devs don't need shell exports.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv(repo_root: Path) -> None:
    """Tiny .env loader — KEY=VALUE lines, '#' comments, no interpolation."""
    env_file = repo_root / ".env"
    if not env_file.is_file():
        return
    try:
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass  # unreadable .env → behave as if absent


def _find_repo_root() -> Path:
    """Walk up from this file to the worktree root (the dir containing .gitignore)."""
    cur = Path(__file__).resolve()
    for parent in cur.parents:
        if (parent / ".gitignore").is_file() and (parent / ".env.example").is_file():
            return parent
    return cur.parents[2]


@dataclass
class Settings:
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model_voice: str = "qwen3.5-omni-plus"
    mock_mode: str = "auto"  # auto | always | never
    confidence_confirm_threshold: float = 0.75
    numeral_style: str = "western"  # western | urdu (design.md §4.2 — settled by user test)
    audio_decode: str = "ffmpeg"  # ffmpeg | pyav | raw  (swappable decode step)
    probe_voice: str = "Tina"  # voice for the speech-out probe (notes.md §1)
    repo_root: Path = field(default_factory=_find_repo_root)

    @property
    def use_mock(self) -> bool:
        if self.mock_mode == "always":
            return True
        if self.mock_mode == "never":
            return False
        return not self.dashscope_api_key  # auto


def load_settings(env: dict[str, str] | None = None) -> Settings:
    """Build Settings from env (test-injectable) falling back to process env/.env."""
    if env is None:
        _load_dotenv(_find_repo_root())
        env = dict(os.environ)

    def get(key: str, default: str = "") -> str:
        return (env.get(key) or default).strip()

    return Settings(
        dashscope_api_key=get("DASHSCOPE_API_KEY"),
        dashscope_base_url=get("DASHSCOPE_BASE_URL", Settings.dashscope_base_url),
        model_voice=get("MODEL_VOICE", "qwen3.5-omni-plus"),
        mock_mode=get("MOCK_MODE", "auto").lower(),
        confidence_confirm_threshold=float(get("CONFIDENCE_CONFIRM_THRESHOLD", "0.75")),
        numeral_style=get("NUMERAL_STYLE", "western").lower(),
        audio_decode=get("AUDIO_DECODE", "ffmpeg").lower(),
        probe_voice=get("PROBE_VOICE", "Tina"),
    )
