#!/usr/bin/env bash
# One-shot VPS deploy: Docker + Bizro + QR-linked WhatsApp bridge.
# Run on the VPS:  curl -fsSL https://raw.githubusercontent.com/HussamHaroon/Bizro/main/deploy/vps.sh | bash
set -euo pipefail
REPO=https://github.com/HussamHaroon/Bizro.git
DIR=${BIZRO_DIR:-$HOME/bizro}
BRANCH=${BIZRO_BRANCH:-main}

if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
fi
DOCKER="docker"; docker info >/dev/null 2>&1 || DOCKER="sudo docker"
command -v git >/dev/null || { sudo apt-get update -qq && sudo apt-get install -y -qq git; }

if [ -d "$DIR/.git" ]; then git -C "$DIR" fetch -q origin "$BRANCH" && git -C "$DIR" checkout -q -B "$BRANCH" "origin/$BRANCH"
else git clone -q -b "$BRANCH" "$REPO" "$DIR"; fi
cd "$DIR"

if [ ! -f .env ]; then
  cat > .env <<ENVFILE
# Fill from Vercel (project bizro -> Settings -> Environment Variables), then re-run.
# Without DASHSCOPE_API_KEY the AI pipelines run in mock mode.
DASHSCOPE_API_KEY=
DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
# Optional overrides - uncomment only the ones you set in Vercel:
# MODEL_VOICE=
# MODEL_REASONING=
# MODEL_OCR_VL=
# STT_PROVIDER=
# STT_QWEN_MODEL=
# STT_API_KEY=
# STT_BASE_URL=
# STT_MODEL=
# STT_LANGUAGE=
# OPENAI_API_KEY=
# Shared by app and bridge for webhook signing (generated):
WHATSAPP_APP_SECRET=$(openssl rand -hex 32)
ENVFILE
  echo ">> Wrote $DIR/.env - put DASHSCOPE_API_KEY in it (nano $DIR/.env), then re-run."
fi
grep -q '^DASHSCOPE_API_KEY=.' .env || echo ">> WARNING: DASHSCOPE_API_KEY empty - AI runs in mock mode."

$DOCKER compose -f docker-compose.vps.yml up -d --build
IP=$(curl -fsS https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')
echo
echo ">> Dashboard:  http://$IP/      health: http://$IP/health   simulator: http://$IP/simulator"
echo ">> WhatsApp QR (scan in WhatsApp -> Linked devices -> Link a device):"
$DOCKER compose -f docker-compose.vps.yml logs -f bridge
