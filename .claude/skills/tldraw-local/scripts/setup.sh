#!/usr/bin/env bash
#
# tldraw-local — setup & start the board server.
# Installs deps (first run) and launches the Vite dev server, then waits until
# the board answers on /api/ping. Safe to run repeatedly: it no-ops if the
# server is already up.
#
# Usage:  bash scripts/setup.sh
# Env:    PORT (default 7777)

set -euo pipefail

PORT="${PORT:-7777}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR/../app"
LOG="${TMPDIR:-/tmp}/tldraw-local-dev.log"
PING="http://localhost:${PORT}/api/ping"

up() { curl -sf "$PING" >/dev/null 2>&1; }

# Already running? Done.
if up; then
  echo "✓ board already running at http://localhost:${PORT}/  (ping ok)"
  exit 0
fi

# Prerequisites.
command -v node >/dev/null 2>&1 || { echo "✗ Node.js is required (https://nodejs.org)"; exit 1; }
command -v npm  >/dev/null 2>&1 || { echo "✗ npm is required"; exit 1; }

cd "$APP_DIR"

# Install deps on first run.
if [ ! -d node_modules ]; then
  echo "→ installing dependencies (first run)…"
  if [ -f package-lock.json ]; then npm ci; else npm install; fi
fi

# Launch the dev server in the background.
echo "→ starting board on port ${PORT}…  (logs: ${LOG})"
PORT="$PORT" nohup npm run dev -- --port "$PORT" >"$LOG" 2>&1 &

# Wait for it to answer.
for _ in $(seq 1 60); do
  if up; then
    echo "✓ board is up → http://localhost:${PORT}/  (open /design-board.html or /)"
    exit 0
  fi
  sleep 0.5
done

echo "✗ board did not come up within 30s — check ${LOG}"
exit 1
