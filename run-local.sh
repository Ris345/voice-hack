#!/usr/bin/env bash
#
# Pill Buddy — one-command local demo runner.
#
# Starts ngrok (two tunnels), reads the public URLs back from ngrok's local
# API, writes them into backend/.env + voice-agent/.env, then launches both
# FastAPI services. Ctrl-C tears everything down.
#
# Prereqs (one-time):
#   - ngrok installed + authtoken configured:  ngrok config add-authtoken <token>
#   - backend/.env and voice-agent/.env filled in (Supabase, Twilio, API keys)
#   - deps installed in backend/.venv and voice-agent/.venv
#
# Usage:  ./run-local.sh
#
# If the voice-agent keys (ANTHROPIC/ELEVENLABS) are missing, it runs
# BACKEND-ONLY with Twilio's placeholder voice — enough to test the call +
# WhatsApp pipeline without Rishav's agent.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT=8080
AGENT_PORT=8000

log()  { printf '\033[1;36m▸ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# --- set KEY=VALUE in a .env file (add if missing) --------------------------
set_env() {  # set_env <file> <key> <value>
  local file="$1" key="$2" val="$3"
  if grep -q "^${key}=" "$file"; then
    # use | as sed delimiter since values are URLs
    sed -i "s|^${key}=.*|${key}=${val}|" "$file"
  else
    printf '%s=%s\n' "$key" "$val" >> "$file"
  fi
}

env_val() { grep "^$2=" "$1" 2>/dev/null | cut -d= -f2- | tr -d '"'; }

# --- preflight --------------------------------------------------------------
command -v ngrok >/dev/null || die "ngrok not installed — https://ngrok.com/download"
[ -f "$ROOT/backend/.env" ] || die "backend/.env missing (copy backend/.env.example)"
[ -f "$ROOT/voice-agent/.env" ] || die "voice-agent/.env missing (copy voice-agent/.env.example)"
[ -x "$ROOT/backend/.venv/bin/uvicorn" ] || die "backend deps not installed (python -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt)"

# Decide full vs backend-only based on whether the agent's keys are set.
ANTH=$(env_val "$ROOT/voice-agent/.env" ANTHROPIC_API_KEY)
ELEVEN=$(env_val "$ROOT/voice-agent/.env" ELEVENLABS_API_KEY)
RUN_AGENT=1
if [ -z "$ANTH" ] || [ -z "$ELEVEN" ]; then
  RUN_AGENT=0
  warn "voice-agent keys not set → BACKEND-ONLY mode (Twilio placeholder voice)."
  warn "Add ANTHROPIC_API_KEY + ELEVENLABS_API_KEY to voice-agent/.env for the full agent."
fi

# --- ngrok config (tunnels for both ports) ----------------------------------
NGROK_CFG="$ROOT/.ngrok-piilbuddy.yml"
if [ "$RUN_AGENT" = 1 ]; then
  cat > "$NGROK_CFG" <<YAML
version: "3"
tunnels:
  backend: { addr: $BACKEND_PORT, proto: http }
  agent:   { addr: $AGENT_PORT,   proto: http }
YAML
else
  cat > "$NGROK_CFG" <<YAML
version: "3"
tunnels:
  backend: { addr: $BACKEND_PORT, proto: http }
YAML
fi

PIDS=()
cleanup() {
  log "shutting down…"
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  rm -f "$NGROK_CFG"
}
trap cleanup EXIT INT TERM

# --- start ngrok, then read the public URLs from its local API --------------
log "starting ngrok tunnels…"
ngrok start --all --config "$NGROK_CFG" --log stdout >/tmp/ngrok-pillbuddy.log 2>&1 &
PIDS+=($!)

BACKEND_URL="" ; AGENT_URL=""
for _ in $(seq 1 30); do
  sleep 1
  JSON=$(curl -s localhost:4040/api/tunnels 2>/dev/null || true)
  [ -z "$JSON" ] && continue
  read -r BACKEND_URL AGENT_URL < <(printf '%s' "$JSON" | python3 -c '
import sys, json
try: tuns = json.load(sys.stdin)["tunnels"]
except Exception: sys.exit()
by_port = {}
for t in tuns:
    addr = t.get("config", {}).get("addr", "")
    url = t.get("public_url", "")
    if url.startswith("https"):
        by_port[addr.rsplit(":", 1)[-1]] = url
print(by_port.get("'"$BACKEND_PORT"'", ""), by_port.get("'"$AGENT_PORT"'", ""))
')
  [ -n "$BACKEND_URL" ] && { [ "$RUN_AGENT" = 0 ] || [ -n "$AGENT_URL" ]; } && break
done
[ -n "$BACKEND_URL" ] || die "couldn't read ngrok backend URL (see /tmp/ngrok-pillbuddy.log)"
[ "$RUN_AGENT" = 0 ] || [ -n "$AGENT_URL" ] || die "couldn't read ngrok agent URL"

# --- wire the URLs into both .env files -------------------------------------
log "backend  public URL: $BACKEND_URL"
set_env "$ROOT/backend/.env" PUBLIC_BASE_URL "$BACKEND_URL"
if [ "$RUN_AGENT" = 1 ]; then
  log "agent    public URL: $AGENT_URL"
  set_env "$ROOT/backend/.env"     VOICE_AGENT_TWIML_URL "$AGENT_URL/voice/incoming"
  set_env "$ROOT/voice-agent/.env" BASE_URL              "$AGENT_URL"
  set_env "$ROOT/voice-agent/.env" BACKEND_URL           "http://localhost:$BACKEND_PORT"
else
  set_env "$ROOT/backend/.env" VOICE_AGENT_TWIML_URL ""   # → backend placeholder voice
fi

# --- launch the services ----------------------------------------------------
log "starting backend on :$BACKEND_PORT"
( cd "$ROOT/backend" && exec .venv/bin/uvicorn app.main:app --port "$BACKEND_PORT" ) &
PIDS+=($!)

if [ "$RUN_AGENT" = 1 ]; then
  log "starting voice-agent on :$AGENT_PORT"
  ( cd "$ROOT/voice-agent" && exec .venv/bin/uvicorn main:app --port "$AGENT_PORT" ) &
  PIDS+=($!)
fi

sleep 3
cat <<INFO

┌────────────────────────────────────────────────────────────────┐
  Pill Buddy is up.  $( [ "$RUN_AGENT" = 1 ] && echo "(full: ElevenLabs agent)" || echo "(backend-only: placeholder voice)" )

  Trigger a demo call (Rose):
    curl -s -X POST $BACKEND_URL/calls/trigger \\
      -H 'Content-Type: application/json' \\
      -d '{"senior_id":"a0000000-0000-0000-0000-000000000001"}'

  ngrok inspector:   http://localhost:4040
  Ctrl-C to stop everything.
└────────────────────────────────────────────────────────────────┘
INFO

wait
