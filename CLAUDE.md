# CLAUDE.md

## Project: Grandma's Pill Buddy

AI voice agent that calls elderly patients to check medication adherence and wellbeing. Twilio handles telephony, Claude drives conversation, ElevenLabs synthesizes speech, Supabase stores data.

## Repo layout

```
voice-agent/   FastAPI :8000 — Twilio webhook handler, Claude agent, ElevenLabs TTS
backend/       FastAPI :8080 — call scheduler, Supabase persistence, caregiver SMS alerts
judge-agent/   FastAPI :8001 — LLM-as-judge, evaluates transcripts, feeds learnings back
dashboard/     Caregiver web portal (static, served by backend)
db/            Supabase schema / migrations
```

## Key files

| File | Purpose |
|---|---|
| `voice-agent/main.py` | Twilio webhook routes (`/voice/incoming`, `/voice/gather`, `/voice/status`), audio serving |
| `voice-agent/agent.py` | Claude conversation engine — stage machine (greeting→med_check→wellness→closing) |
| `voice-agent/tts.py` | ElevenLabs TTS — synthesizes text to MP3, returns file_id for `/audio/<id>` |
| `voice-agent/sessions.py` | In-memory session store keyed by Twilio CallSid |
| `voice-agent/patients.py` | Supabase patient lookup with hardcoded fallback |
| `voice-agent/judge_client.py` | Posts transcripts to judge agent, fetches learnings |
| `voice-agent/backend_client.py` | Posts call results and alerts to backend |
| `judge-agent/main.py` | `/evaluate` (async background) + `/learnings` endpoints |
| `judge-agent/judge.py` | Claude evaluates on 5 dimensions, returns actionable lessons |
| `backend/app/main.py` | `/calls/trigger`, `/calls/invoke`, `/calls/{id}/result`, `/alerts` |
| `backend/app/config.py` | Pydantic settings — all env vars documented here |

## Running locally

Each service runs in Docker. See README.md for full setup.

```bash
# Quick rebuild + restart (voice agent example)
docker build -t pill-buddy-voice voice-agent/
docker stop pill-buddy-voice && docker rm pill-buddy-voice
docker run -d --name pill-buddy-voice --env-file voice-agent/.env -p 8000:8000 pill-buddy-voice

# Trigger a demo call
curl -X POST http://localhost:8080/calls/trigger \
  -H "Content-Type: application/json" \
  -d '{"senior_id": "a0000000-0000-0000-0000-000000000001"}'

# Or by phone number
curl -X POST http://localhost:8080/calls/invoke \
  -H "Content-Type: application/json" \
  -d '{"phone": "+19176559764", "name": "Rose"}'
```

## Environment variables

Secrets live in `.env` files (gitignored). Never commit them. Pass at runtime via `--env-file`.

**`voice-agent/.env`** needs: `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `BASE_URL` (ngrok/deployed URL), `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `BACKEND_URL`, `JUDGE_URL`

**`backend/.env`** needs: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `PUBLIC_BASE_URL`, `VOICE_AGENT_TWIML_URL`

**`judge-agent/.env`** needs: `ANTHROPIC_API_KEY`

## Twilio webhook flow

```
Twilio POST /voice/incoming  →  greet patient (ElevenLabs audio + <Gather>)
Twilio POST /voice/gather    →  patient speaks → Claude responds → loop
Twilio POST /voice/status    →  call ended → report result to backend + judge
```

Point Twilio's voice webhook at: `{BASE_URL}/voice/incoming`

## ElevenLabs

- Voice: **Sarah** (`EXAVITQu4vr4xnSDxMaL`) — premade voice, works on free tier
- Do NOT use community library voices (e.g. Grace `oWAxZDx7w5VEj9dCyTzz`) — they return 402 on the free tier
- Model: `eleven_turbo_v2_5` (lowest latency)
- Audio served via `GET /audio/{file_id}` then deleted after Twilio fetches it

## Claude agent

- Model: `claude-sonnet-4-6`
- Returns structured JSON: `{ speech, next_stage, med_status, should_close }`
- Stages: `greeting → med_check → wellness → closing`
- Learnings from the judge agent are injected into the system prompt at the start of each call
- `should_close` triggers `<Hangup>` — only set after a proper goodbye exchange
- Do NOT add "take care" to the goodbye signal list — it caused premature hangups

## Supabase

- URL: `https://svvmarfbnrabmtcyjufm.supabase.co`
- Key tables: `seniors`, `medications`, `call_logs`, `alerts`, `caregivers`, `care_relationships`, `reminders`, `action_items`
- Demo senior: `id = a0000000-0000-0000-0000-000000000001` (phone patched to test number)
- Use `SUPABASE_ANON_KEY` in voice-agent, `SUPABASE_SERVICE_ROLE_KEY` in backend

## Docker networking

On Mac, containers reach host services via `host.docker.internal` (e.g. judge agent at `http://host.docker.internal:8001`).

## Self-improvement loop

1. Call ends → voice agent POSTs transcript to `judge-agent/evaluate`
2. Judge evaluates asynchronously (returns 200 immediately, runs in background)
3. Learnings saved to `judge-agent/learnings.json` (last 20 calls, deduplicated)
4. Next call starts → voice agent fetches `/learnings` → injects into Claude system prompt
