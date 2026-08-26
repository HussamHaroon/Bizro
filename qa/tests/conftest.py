"""qa-agent test bootstrap.

Env is pinned HERE, before any `server` / `voice_agent` / `vision_agent` import,
because server.app.db binds its SQLAlchemy engine at import time and the
pipelines read MOCK_MODE from the process env. Everything is offline,
deterministic (MOCK_MODE=always), zero credentials.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

WORKTREE = Path(__file__).resolve().parents[2]  # .../.worktrees/qa (repo root copy)

_TMP = Path(tempfile.mkdtemp(prefix="bizro-qa-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'qa.db').as_posix()}"
os.environ["MOCK_MODE"] = "always"
os.environ["DASHSCOPE_API_KEY"] = ""
os.environ["WHATSAPP_TOKEN"] = ""
os.environ["WHATSAPP_PHONE_NUMBER_ID"] = ""
os.environ["WHATSAPP_APP_SECRET"] = ""
os.environ.pop("MOCK_SCENARIO", None)

if str(WORKTREE) not in sys.path:
    sys.path.insert(0, str(WORKTREE))
# Pipelines live in hyphenated dirs (voice-agent/...); mirror what
# server.app.config.ensure_repo_root_on_path does so test modules can import
# voice_agent / vision_agent directly.
for _sub in ("voice-agent", "vision-agent", "credit-agent"):
    _p = str(WORKTREE / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)
