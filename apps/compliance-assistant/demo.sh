#!/usr/bin/env bash
# Start both the backend and frontend for the Compliance Assistant demo.
# Usage: ./apps/compliance-assistant/demo.sh
# Press Ctrl+C to stop both servers.

set -e

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND_DIR="$REPO_ROOT/services/compliance-assistant-api"
FRONTEND_DIR="$REPO_ROOT/apps/compliance-assistant"

cleanup() {
  echo ""
  echo "Shutting down..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
  echo "Done."
}
trap cleanup EXIT

echo "Starting backend (Flask on port 5002)..."
cd "$BACKEND_DIR"
uv run python run.py &
BACKEND_PID=$!

echo "Starting frontend (Vite on port 5173)..."
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Compliance Assistant is running:"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:5002"
echo ""
echo "Press Ctrl+C to stop."

wait
