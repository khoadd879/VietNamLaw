#!/bin/bash
# Run both frontend and backend concurrently
# Usage: ./run.sh [dev|start]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-dev}"

echo "Starting VietNamLaw (mode: $MODE)"
echo "=================================="

# Backend
echo "[1/2] Starting backend on :8000..."
cd "$SCRIPT_DIR/backend"
if [ ! -f .env ]; then
    echo "Warning: backend/.env not found, copying from .env.example"
    cp .env.example .env 2>/dev/null || true
fi
.venv/bin/python -m uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

# Frontend
echo "[2/2] Starting frontend on :3000..."
cd "$SCRIPT_DIR/frontend"
if [ ! -d node_modules ]; then
    echo "Warning: node_modules not found, running npm install..."
    npm install
fi
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Services started:"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:3000"
echo ""
echo "PIDs: backend=$BACKEND_PID, frontend=$FRONTEND_PID"
echo "Press Ctrl+C to stop both"

# Wait for either process
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait $BACKEND_PID $FRONTEND_PID