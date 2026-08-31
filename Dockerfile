# Bizro — single-container deploy: FastAPI serves API + built dashboard.
# Build:  docker build -t bizro .
# Run:    docker run --env-file .env -p 8000:8000 bizro
# (mount a volume at /app/data to keep the SQLite ledger + media across restarts)

FROM node:25-slim AS ui
WORKDIR /ui
COPY dashboard/package.json dashboard/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY dashboard/ .
RUN npm run build
# Site (marketing homepage) is built from the SAME commit — main.py serves
# /brand/* site-first, so both dists must carry identical brand assets
# (QA wave-7 P2-3).
WORKDIR /site
COPY site/package.json site/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY site/ .
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server/ server/
COPY voice-agent/ voice-agent/
COPY vision-agent/ vision-agent/
COPY credit-agent/ credit-agent/
COPY --from=ui /ui/dist dashboard/dist
COPY --from=ui /site/dist site/dist
ENV DATABASE_URL=sqlite:////app/data/bizro.db PYTHONUNBUFFERED=1
VOLUME /app/data
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "server.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
