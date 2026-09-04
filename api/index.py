"""Vercel serverless entry — wraps the Bizro FastAPI app (D6-2 deploy switch).

One Python lambda serves everything: the API, the WhatsApp webhook, and the
static site/dashboard builds (server/app/main.py already routes them). The
repo-root `requirements.txt` is what Vercel installs for this runtime.

Vercel's FS is read-only except /tmp:
  - set MEDIA_DIR=/tmp/media
  - SQLite lives in /tmp and is EPHEMERAL — set DATABASE_URL to a free
    Postgres (Neon) for anything beyond a single warm invocation.
"""

import sys
from pathlib import Path

# api/index.py → parents[1] is the repo root; expose the pipeline packages
# exactly like server.app.config.ensure_repo_root_on_path does locally.
_REPO = Path(__file__).resolve().parents[1]
for p in (
    _REPO,
    _REPO / "voice-agent",
    _REPO / "vision-agent",
    _REPO / "credit-agent",
):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from server.app.main import app  # noqa: E402

handler = app  # Vercel's ASGI adapter looks for `app` in the module
