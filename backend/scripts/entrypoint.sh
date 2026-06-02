#!/bin/bash
# Container entrypoint: run DB migrations, then start supervisord (which
# brings up backend + frontend).
#
# Env vars are injected by docker-compose `env_file: .env.production` and
# are available to this script (and to children spawned by supervisord) via
# the process environment. We do NOT read a /app/.env file — the compose
# env_file mechanism injects them as process env vars, not as a file.
set -e

cd /app/backend

# Sanity check: critical env vars must be present
: "${NEON_DATABASE_URL:?NEON_DATABASE_URL is required (set in .env.production)}"
: "${QDRANT_URL:?QDRANT_URL is required (set in .env.production)}"

# Run alembic migrations (idempotent — creates tables if missing, no-op otherwise)
echo "[entrypoint] Running alembic upgrade head..."
alembic upgrade head

# If BM25 index is missing, build it now so the first user request doesn't
# block on a 30-60s scroll. Skip silently if the file is already there.
if [ ! -f "${BM25_INDEX_PATH:-./data/bm25_index.pkl}" ]; then
    echo "[entrypoint] BM25 index missing — building (one-time, may take a minute)..."
    python -m scripts.build_bm25_index || \
        echo "[entrypoint] WARN: BM25 build failed; app will retry on first request."
else
    echo "[entrypoint] BM25 index present at ${BM25_INDEX_PATH}, skipping build."
fi

echo "[entrypoint] Starting supervisord (backend :8000 + frontend :5647)..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/app.conf
