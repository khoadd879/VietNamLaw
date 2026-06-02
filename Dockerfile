# ─── Stage 1: build Next.js frontend ──────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend

# Install deps first (better layer caching)
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund

# Build
COPY frontend/ ./
RUN npm run build

# ─── Stage 2: install Python deps ──────────────────────────────────────────
FROM python:3.12-slim AS backend-deps

WORKDIR /app/backend

# System deps for psycopg + bcrypt
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ─── Stage 3: runtime ─────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# supervisord runs both Next.js (needs node) + FastAPI in one container.
# Pin Node to a known LTS via NodeSource so the standalone build is compatible.
RUN apt-get update && apt-get install -y --no-install-recommends \
        supervisor libpq5 curl ca-certificates gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpg-key/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x bookworm main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version && npm --version \
    && useradd --create-home --shell /bin/bash app

WORKDIR /app

# Python deps from stage 2
COPY --from=backend-deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend-deps /usr/local/bin /usr/local/bin

# Backend source
COPY --from=backend-deps /app/backend /app/backend
COPY backend/ /app/backend/

# Frontend standalone build (output: 'standalone' in next.config.js)
COPY --from=frontend-build /app/frontend/.next/standalone /app/frontend/
COPY --from=frontend-build /app/frontend/.next/static /app/frontend/.next/static
COPY --from=frontend-build /app/frontend/public /app/frontend/public

# supervisord + entrypoint
COPY supervisord.conf /etc/supervisor/conf.d/app.conf
COPY backend/scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Data dir for BM25 index (regenerated on first start)
RUN mkdir -p /app/backend/data && chown -R app:app /app

# Public port (frontend on 5647, backend on 8000 stays internal)
EXPOSE 5647

# Health check: Next.js root returns 200 once it's up
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:5647/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
