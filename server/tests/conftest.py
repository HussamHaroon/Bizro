"""server-agent test bootstrap (bizro-testability: offline, deterministic).

Env is pinned HERE, before any `server` import, because server.app.db binds
its SQLAlchemy engine at import time. The database is a throwaway SQLite file
in a temp dir — tests must NEVER touch a real bizro.db (main's live demo DB).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # worktree root (contains server/)

_TMP = Path(tempfile.mkdtemp(prefix="bizro-server-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'server-tests.db').as_posix()}"
os.environ["MOCK_MODE"] = "always"
os.environ["DASHSCOPE_API_KEY"] = ""
os.environ["WHATSAPP_TOKEN"] = ""
os.environ["WHATSAPP_PHONE_NUMBER_ID"] = ""
os.environ["WHATSAPP_APP_SECRET"] = ""
os.environ.pop("MOCK_SCENARIO", None)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# Pipelines live in hyphenated dirs; mirror ensure_repo_root_on_path so test
# modules can import vision_agent / voice_agent for monkeypatching.
for _sub in ("voice-agent", "vision-agent", "credit-agent"):
    _p = str(ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)
