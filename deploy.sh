#!/bin/bash
# SSH-based deploy for VietNamLaw.
#
# Build image locally → save → SCP to remote → load + restart container.
#
# Required env / config (set in your shell or .env.deploy):
#   DEPLOY_REMOTE   SSH target, e.g. "user@vps.example.com"
#   DEPLOY_DIR      Remote working dir, e.g. "/opt/vietnamlaw"
#   DEPLOY_PORT     Public port (default 5647, must match docker-compose)
#   SSH_KEY         Optional: path to SSH key (default: ~/.ssh/id_rsa)
#
# Pre-reqs on remote:
#   - docker + docker compose v2 installed
#   - SSH key auth enabled
#   - Port 5647 open in firewall
#
# Usage:
#   cp .env.production.example .env.production   # fill in real secrets
#   ./deploy.sh
#
# Or override via env:  DEPLOY_REMOTE=user@1.2.3.4 DEPLOY_DIR=/srv/app ./deploy.sh

set -euo pipefail

REMOTE="${DEPLOY_REMOTE:?DEPLOY_REMOTE not set (e.g. user@vps.example.com)}"
REMOTE_DIR="${DEPLOY_DIR:-/opt/vietnamlaw}"
DEPLOY_PORT="${DEPLOY_PORT:-5647}"
SSH_KEY="${SSH_KEY:-${HOME}/.ssh/id_rsa}"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30)
[[ -f "$SSH_KEY" ]] && SSH_OPTS+=(-i "$SSH_KEY")

LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_TAG="vietnamlaw:$(date -u +%Y%m%d-%H%M%S)"
ARCHIVE="/tmp/${IMAGE_TAG//[:\/]/_}.tar.gz"

log()  { printf "\033[1;36m▶ %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m⚠ %s\033[0m\n" "$*" >&2; }
die()  { printf "\033[1;31m✗ %s\033[0m\n" "$*" >&2; exit 1; }

# ── Preflight ────────────────────────────────────────────────────────────────
[[ -f "$LOCAL_DIR/.env.production" ]] || die ".env.production not found in $LOCAL_DIR"
command -v docker >/dev/null || die "docker not installed locally"

log "Preflight OK — deploying to ${REMOTE}:${REMOTE_DIR} (port ${DEPLOY_PORT})"

# ── Step 1: build image locally ─────────────────────────────────────────────
log "Building image ${IMAGE_TAG}..."
docker build -t "$IMAGE_TAG" "$LOCAL_DIR"
docker tag "$IMAGE_TAG" vietnamlaw:latest

# ── Step 2: save + SCP image to remote ──────────────────────────────────────
log "Saving image to ${ARCHIVE}..."
docker save "$IMAGE_TAG" | gzip > "$ARCHIVE"
trap 'rm -f "$ARCHIVE"' EXIT

log "Copying image + compose + env to ${REMOTE}..."
ssh "${SSH_OPTS[@]}" "$REMOTE" "mkdir -p ${REMOTE_DIR}"
scp "${SSH_OPTS[@]}" "$ARCHIVE" "${REMOTE}:${REMOTE_DIR}/image.tar.gz"
scp "${SSH_OPTS[@]}" "$LOCAL_DIR/docker-compose.yml" "${REMOTE}:${REMOTE_DIR}/"
scp "${SSH_OPTS[@]}" "$LOCAL_DIR/.env.production" "${REMOTE}:${REMOTE_DIR}/"

# ── Step 3: remote load + restart ───────────────────────────────────────────
log "Loading image and restarting container on ${REMOTE}..."
ssh "${SSH_OPTS[@]}" "$REMOTE" REMOTE_DIR="$REMOTE_DIR" DEPLOY_PORT="$DEPLOY_PORT" bash <<'REMOTE_SCRIPT'
set -euo pipefail
cd "$REMOTE_DIR"

# Load new image
docker load < image.tar.gz

# Pull config from .env.production (just to log — actual values come from env_file in compose)
echo "Loaded image. Restarting container..."

# Stop old, start new
docker compose --project-name vietnamlaw down --remove-orphans || true
docker compose --project-name vietnamlaw up -d vietnamlaw

# Wait for healthcheck (max 2 min)
echo "Waiting for healthcheck (port ${DEPLOY_PORT})..."
for i in $(seq 1 24); do
    if curl -fsS "http://localhost:${DEPLOY_PORT}/" >/dev/null 2>&1; then
        echo "✓ Healthcheck passed after ${i}*5s"
        break
    fi
    sleep 5
    if [ "$i" = "24" ]; then
        echo "✗ Healthcheck timeout — last 50 log lines:"
        docker compose --project-name vietnamlaw logs --tail=50 vietnamlaw
        exit 1
    fi
done

# Cleanup
rm -f image.tar.gz
echo "✓ Deploy complete. Listening on :${DEPLOY_PORT}"
REMOTE_SCRIPT

log "Done. App available at: http://${REMOTE#*@}:${DEPLOY_PORT}/"
