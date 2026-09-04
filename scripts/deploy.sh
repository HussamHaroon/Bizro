#!/usr/bin/env bash
# Bizro — one-command production deploy (Vercel CLI). Run from anywhere.
# Prereqs: `npx vercel login` done once; DATABASE_URL + all env vars set in
# the Vercel dashboard/CLI (see .env.example).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> building dashboard + site"
(cd dashboard && npm run build)
(cd site && npm run build)

echo "==> deploying to production (API + static dists)"
npx --yes vercel deploy --prod --yes

echo "==> re-pointing friendly aliases to the new production deployment"
LATEST=$(npx --yes vercel ls bizro 2>/dev/null | grep -oE 'https://bizro-[a-z0-9]+-hussamharoons-projects\.vercel\.app' | head -1)
for d in bizro-pk getbizro bizro-app bizro-ai; do
  npx --yes vercel alias set "$LATEST" $d.vercel.app >/dev/null && echo "  $d.vercel.app ok"
done

echo "==> verifying"
curl -s -o /dev/null -w "  health: %{http_code}\n" -L "https://bizro-pk.vercel.app/health"
curl -s -o /dev/null -w "  home:   %{http_code}\n" -L "https://bizro-pk.vercel.app/"
echo "deploy complete."
