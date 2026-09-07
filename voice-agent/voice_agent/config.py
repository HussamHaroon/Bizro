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
    model_voice: str = "qwen-flash"
    mock_mode: str = "auto"  # auto | always | never
    confidence_confirm_threshold: float = 0.75
    numeral_style: str = "western"  # western | urdu (design.md §4.2 — settled by user test)
    audio_decode: str = "ffmpeg"  # ffmpeg | pyav | raw  (swappable decode step)
    probe_voice: str = "Tina"  # voice for the speech-out probe (notes.md §1)
    # --- Free-tier STT (D6-3): Groq whisper transcribes, text model parses ---
    stt_api_key: str = ""
    stt_base_url: str = "https://api.groq.com/openai/v1"
    stt_model: str = "whisper-large-v3-turbo"
    stt_language: str = "ur"  # empty = auto-detect
    # --- Qwen ASR primary (STT_PROVIDER=qwen): qwen3-asr-flash via DashScope
    # chat-completions; any failure falls back to the whisper provider above ---
    stt_provider: str = "groq"  # groq | qwen
    stt_qwen_model: str = "qwen3-asr-flash"
    # --- Cross-check (dual-engine agreement): OpenAI Whisper as an INDEPENDENT
    # second opinion. When both engines agree, transcription confidence is
    # boosted; on disagreement the entries are penalized and the merchant is
    # asked to confirm — a wrong number never slips through silently. ---
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    stt_crosscheck: str = "auto"  # auto | on | off (auto = on iff OPENAI_API_KEY)
    stt_secondary_model: str = "whisper-1"  # or gpt-4o-transcribe
    stt_agree_threshold: float = 0.80  # normalized similarity considered "agree"
    stt_agree_bonus: float = 0.10
    stt_disagree_penalty: float = 0.10
    repo_root: Path = field(default_factory=_find_repo_root)

    @property
    def use_mock(self) -> bool:
        if self.mock_mode == "always":
            return True
        if self.mock_mode == "never":
            return False
        return not self.dashscope_api_key  # auto

    @property
    def crosscheck_enabled(self) -> bool:
        if self.stt_crosscheck == "off":
            return False
        if not self.openai_api_key:
            return False
        return True  # "on" or "auto" with a key present


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
        model_voice=get("MODEL_VOICE", "qwen-flash"),
        mock_mode=get("MOCK_MODE", "auto").lower(),
        confidence_confirm_threshold=float(get("CONFIDENCE_CONFIRM_THRESHOLD", "0.75")),
        numeral_style=get("NUMERAL_STYLE", "western").lower(),
        audio_decode=get("AUDIO_DECODE", "ffmpeg").lower(),
        probe_voice=get("PROBE_VOICE", "Tina"),
        stt_api_key=get("STT_API_KEY"),
        stt_base_url=get("STT_BASE_URL", Settings.stt_base_url),
        stt_model=get("STT_MODEL", Settings.stt_model),
        stt_language=get("STT_LANGUAGE", "ur"),
        stt_provider=get("STT_PROVIDER", "groq").lower(),
        stt_qwen_model=get("STT_QWEN_MODEL", Settings.stt_qwen_model),
        openai_api_key=get("OPENAI_API_KEY"),
        openai_base_url=get("OPENAI_BASE_URL", Settings.openai_base_url),
        stt_crosscheck=get("STT_CROSSCHECK", "auto").lower(),
        stt_secondary_model=get("STT_SECONDARY_MODEL", Settings.stt_secondary_model),
        stt_agree_threshold=float(get("STT_AGREE_THRESHOLD", "0.80")),
        stt_agree_bonus=float(get("STT_AGREE_BONUS", "0.10")),
        stt_disagree_penalty=float(get("STT_DISAGREE_PENALTY", "0.10")),
    )
