#!/usr/bin/env bash
# No-Docker VPS run: Python app on :80 + WhatsApp bridge on 127.0.0.1:8090.
# Run on the VPS:  bash ~/bizro/deploy/native.sh   (re-run any time to restart)
set -euo pipefail
DIR=${BIZRO_DIR:-$HOME/bizro}
BRANCH=${BIZRO_BRANCH:-claude/restore-whatsapp-simulator-bq9oa8}
cd "$DIR"
git fetch -q origin "$BRANCH" && git checkout -q -B "$BRANCH" "origin/$BRANCH"
mkdir -p data logs

# Python 3.12 via uv (Ubuntu 22.04 ships 3.10)
if ! command -v uv >/dev/null && [ ! -x "$HOME/.local/bin/uv" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
[ -x .venv/bin/python ] || uv venv -q -p 3.12 .venv
uv pip install -q -p .venv/bin/python -r requirements.txt

# Node 22 for the bridge
if ! command -v node >/dev/null || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 20 ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y -qq nodejs
fi
(cd bridge && npm install --omit=dev --no-audit --no-fund --silent)

SECRET=$(grep '^WHATSAPP_APP_SECRET=' .env | cut -d= -f2-)
[ -n "$SECRET" ] || { SECRET=$(openssl rand -hex 32); echo "WHATSAPP_APP_SECRET=$SECRET" >> .env; }

# stop previous runs
sudo pkill -f "[u]vicorn server.app.main:app" || true
pkill -f "[n]ode index.mjs" || true
sleep 1

sudo -b env PATH="$PATH" \
  DATABASE_URL="sqlite:///$DIR/data/bizro.db" \
  WHATSAPP_GRAPH_BASE=http://127.0.0.1:8090 WHATSAPP_TOKEN=bridge WHATSAPP_PHONE_NUMBER_ID=bridge \
  WHATSAPP_APP_SECRET="$SECRET" PYTHONUNBUFFERED=1 \
  sh -c "cd '$DIR' && exec .venv/bin/python -m uvicorn server.app.main:app --host 0.0.0.0 --port 80 >> logs/app.log 2>&1"

(cd bridge && BACKEND_URL=http://127.0.0.1:80 BRIDGE_PORT=8090 BRIDGE_SELF_URL=http://127.0.0.1:8090 \
  WHATSAPP_APP_SECRET="$SECRET" WHATSAPP_PHONE_NUMBER_ID=bridge AUTH_DIR="$DIR/data/wa-auth" \
  nohup node index.mjs >> "$DIR/logs/bridge.log" 2>&1 &)

for i in $(seq 1 30); do curl -fsS http://127.0.0.1/health >/dev/null 2>&1 && break; sleep 1; done
curl -fsS http://127.0.0.1/health && echo
IP=$(curl -fsS https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')
echo ">> Dashboard: http://$IP/   simulator: http://$IP/simulator   health: http://$IP/health"
echo ">> App log: $DIR/logs/app.log"
echo ">> Scan the QR below in WhatsApp -> Linked devices -> Link a device (Ctrl+C just stops watching):"
tail -n 40 -f "$DIR/logs/bridge.log"
