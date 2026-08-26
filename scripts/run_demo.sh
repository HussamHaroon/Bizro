#!/usr/bin/env bash
# Bizro — one-command demo: install deps, seed data, serve UI+API on :8000.
# Usage: bash scripts/run_demo.sh          (from the repo root, any machine with
#        Python 3.12+; Node only needed for the optional dashboard rebuild)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> 1/4 Python environment"
if [ ! -x .venv/Scripts/python ] && [ ! -x .venv/bin/python ]; then
  python -m venv .venv
fi
PY=.venv/Scripts/python; [ -x "$PY" ] || PY=.venv/bin/python
"$PY" -m pip install -q --disable-pip-version-check -r requirements.txt

echo "==> 2/4 Dashboard build (skip with BIZRO_SKIP_UI=1 if dist/ already exists)"
if [ "${BIZRO_SKIP_UI:-0}" != "1" ] && command -v npm >/dev/null 2>&1; then
  (cd dashboard && [ -d node_modules ] || npm install --no-audit --no-fund; npm run build)
else
  echo "    npm not found — using existing dashboard/dist if present"
fi

echo "==> 3/4 Database (seed demo merchant + 90 days of history if empty)"
if [ ! -f bizro.db ] && [ -z "${DATABASE_URL:-}" ]; then
  "$PY" credit-agent/scripts/seed_demo.py >/dev/null && echo "    seeded"
else
  echo "    existing DB kept"
fi

echo "==> 4/4 Serving on http://localhost:8000  (Ctrl+C to stop)"
echo "    Dashboard: http://localhost:8000/ledger   Credit: /credit"
echo "    WhatsApp webhook: POST /webhook/whatsapp  (see HANDOFF.md ②)"
exec "$PY" -m uvicorn server.app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
