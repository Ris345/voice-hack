# tldraw-local

A Claude Code skill that lets the agent **draw on and read from a live [tldraw](https://tldraw.dev) board** running on your machine. Ask Claude to "draw an architecture diagram," "sketch a flowchart," or "load the high level design template," and shapes appear on a real canvas you can edit alongside it.

It ships with the board app, so the only prerequisite is Node.js.

---

## What's in here

```
SKILL.md                     Agent-facing instructions (how to draw/read/use templates)
README.md                    This file
LICENSE                      MIT
scripts/setup.sh             Installs deps + starts the board, idempotent
templates/                   Board scaffolds (e.g. high-level-design.md)
app/                         The bundled Vite + React tldraw board
  src/board.tsx
  vite.config.ts             Dev server + the /api/* endpoints
  index.html, package.json, package-lock.json
```

## Requirements

- **Node.js + npm** (Node 18+ recommended)

## Quick start

From this folder:

```bash
bash scripts/setup.sh
```

That installs dependencies on first run (one-time `npm ci`, ~1–2 min) and launches the
board. When it's ready it prints the URL — open **http://localhost:7777/** in a browser.
Re-running `setup.sh` is safe: if the board is already up it just confirms and exits.

Check it's alive at any time:

```bash
curl -s http://localhost:7777/api/ping     # → {"ok":true,...}
```

## How it works

The board polls the dev server once a second for commands, so the agent drives it over a
small HTTP API:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/ping` | GET | Health check |
| `/api/design-exec` | POST | Run JS against the live board (`{ "code": "…" }`) — this is how it draws |
| `/api/design-read` | GET | Concise, readable digest of the board (page-aware via `?page=`) |
| `/api/design-snapshot` | GET/POST | Full raw tldraw snapshot (auto-saved) |
| `/api/design-patch` | GET/POST | Low-level store patches |

Drawing example:

```bash
curl -s -X POST http://localhost:7777/api/design-exec \
  -H "Content-Type: application/json" \
  -d '{"code": "editor.createShape({id:createShapeId(\"a\"),type:\"geo\",x:0,y:0,props:{geo:\"rectangle\",w:200,h:80,richText:toRichText(\"Hello\"),color:\"blue\",fill:\"semi\",size:\"m\",font:\"draw\",dash:\"draw\",labelColor:\"black\",align:\"middle\",verticalAlign:\"middle\",growY:0,scale:1,url:\"\"}}); editor.zoomToFit();"}'
```

Full drawing/reading reference (shapes, arrows, pages, templates) lives in **`SKILL.md`**.

## Templates

When starting a fresh board the skill asks which template to use. Templates are board
scaffolds under `templates/`:

- **Blank canvas** — free-form
- **High Level Design** — a system-design layout (functional/non-functional requirements,
  API design, entities, DB schema, and a large architecture canvas). Pairs with the
  companion `high-level-design` skill, which fills the regions and runs an NFR deep-dive.

Add your own by dropping a new file in `templates/`.

## Configuration

- **Port** — defaults to `7777`. Override with `PORT` or `TLDRAW_LOCAL_PORT`:

  ```bash
  PORT=8000 bash scripts/setup.sh
  ```

  If you change it, update the `7777` references in `SKILL.md` so the agent uses the same port.

## Troubleshooting

- **`curl: connection refused`** — the board isn't running; `bash scripts/setup.sh`.
- **Shapes appear duplicated** — the board is open in multiple browser tabs; each tab runs
  posted commands. Close extras. (Deterministic IDs guard against most of this.)
- **Port already in use** — start on another port with `PORT=…`, or stop the process on 7777.
- **First run is slow** — that's the one-time dependency install; later runs are instant.

## License

[MIT](./LICENSE).
