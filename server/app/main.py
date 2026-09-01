"""Bizro server — FastAPI app assembly.

Run from the repo root (or anywhere — paths are anchored to the repo root):
    python -m uvicorn server.app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from . import dashscope_client, dispatch, whatsapp_client
from .api import router as api_router
from .config import REPO_ROOT, ensure_repo_root_on_path, get_settings
from .db import init_db
from .webhook import router as webhook_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("bizro.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_repo_root_on_path()  # make voice_agent/vision_agent importable
    init_db()
    s = get_settings()
    logger.info(
        "Bizro server up. dashscope=%s whatsapp=%s signature_validation=%s mock_mode=%s db=%s",
        "live" if dashscope_client.is_live() else "mock",
        "live" if whatsapp_client.is_live() else "mock",
        "enforced" if s.signature_enforced() else "disabled",
        s.mock_mode,
        s.database_url,
    )
    if not dashscope_client.is_live():
        logger.warning(
            "DashScope is in MOCK mode — all model output is clearly-labeled "
            "synthetic. Set DASHSCOPE_API_KEY (HANDOFF.md ①) for live calls."
        )
    yield


app = FastAPI(title="Bizro server", version="0.1.0", lifespan=lifespan)

app.include_router(webhook_router)
app.include_router(api_router)

# --- Static surfaces -----------------------------------------------------------
# site/dist (marketing homepage, when built) owns "/"; dashboard/dist (the SPA)
# owns /ledger, /credit and every other non-API path via fallback. Both live in
# their own hashed assets/ dirs, checked in order.

_SITE = REPO_ROOT / "site" / "dist"
_DIST = REPO_ROOT / "dashboard" / "dist"
_INDEX = _DIST / "index.html"


def _file_in(root: Path, rel: str) -> Path | None:
    if not rel or not root.is_dir():
        return None
    candidate = (root / rel).resolve()
    if str(candidate).startswith(str(root.resolve())) and candidate.is_file():
        return candidate
    return None


@app.get("/health")
def health():
    """Liveness + which integrations are live vs mock (schema.md §4).

    H-1: this route MUST stay registered BEFORE the SPA catch-all below —
    Starlette matches routes in registration order, so a catch-all defined
    earlier would shadow /health with index.html.
    """
    s = get_settings()
    return {
        "status": "ok",
        "mock_mode": s.mock_mode,
        "integrations": {
            "dashscope": {
                "mode": "live" if dashscope_client.is_live() else "mock",
                "base_url": s.dashscope_base_url,
            },
            "whatsapp": {
                "mode": "live" if whatsapp_client.is_live() else "mock",
                "signature_validation": "enforced" if s.signature_enforced() else "disabled",
            },
        },
        "pipelines": dispatch.pipeline_status(),
        "confidence_confirm_threshold": s.confidence_confirm_threshold,
    }


def _html(path: Path) -> FileResponse:
    """index.html must always revalidate — hashed asset names carry caching,
    but a stale index.html references bundles that no longer exist."""
    return FileResponse(path, headers={"Cache-Control": "no-cache"})


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    """Static router: site assets → site index at / → dashboard assets → SPA fallback."""
    if (asset := _file_in(_SITE, full_path)) is not None:
        return FileResponse(asset)
    if full_path in ("", "/") and (_SITE / "index.html").is_file():
        return _html(_SITE / "index.html")
    if (asset := _file_in(_DIST, full_path)) is not None:
        return FileResponse(asset)
    if _INDEX.is_file():
        return _html(_INDEX)
    # No built dashboard (source checkout without a build) — say so instead of 500.
    return {
        "detail": "dashboard not built — run `npm install && npm run build` in dashboard/, "
        "or use the dev server (cd dashboard && npm run dev)"
    }
