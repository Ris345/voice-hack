---
name: tldraw local
description: >
  Draw or edit shapes on a local tldraw design board (bundled app, started on demand).
  Use when the user asks to "draw", "diagram", "sketch", "add to the board",
  "update the diagram", "visualize", or create any of: architecture diagram, data model,
  ERD, flowchart, system design, pipeline, or similar visual artifact on the local board.
allowed-tools: Bash, Read, Write
---

# Local tldraw Skill

Draw on the local tldraw canvas by POSTing JavaScript to `POST /api/design-exec`.
The frontend polls this endpoint every second and executes the code with the `editor`
instance in scope.

## Setup — start the board

The board is a small Vite app bundled in **`app/`** (next to this file). Everything below
assumes it's running and reachable on **port 7777**. Before drawing or reading, check that
it's up — and start it if not:

```bash
# 1. Is the board already running?
curl -sf http://localhost:7777/api/ping            # → {"ok":true,...} when up

# 2. If that fails, start it (run from this skill's folder):
bash scripts/setup.sh                              # installs deps on first run, then launches
```

- Requires **Node.js + npm**. First run does a one-time `npm ci` in `app/` (~1–2 min);
  later runs start instantly.
- `scripts/setup.sh` is **idempotent** — if the board is already up it just confirms and
  exits, so it's safe to run before any session.
- The board UI is at `http://localhost:7777/` (also served as `/design-board.html`).
- Override the port with `PORT` (e.g. `PORT=8000 bash scripts/setup.sh`); the API examples
  below assume 7777 — keep them in sync if you change it.

## Templates — ask first

**When the user is starting a fresh board/diagram, the first thing to do is ask which
template they want** (use `AskUserQuestion`). Skip this only when they're editing or
extending an existing diagram rather than starting from scratch.

| Template | Use for | Definition |
|---|---|---|
| **Blank canvas** | Free-form / ad-hoc drawing | no scaffold — draw directly |
| **High Level Design** | System design: requirements → API → entities → schema → architecture | `templates/high-level-design.md` |

A non-blank template is a board **scaffold**: a set of labeled, empty container regions
the user (or a companion skill) then fills. To apply one, read its file under
`templates/`, run the scaffold exec it defines, then populate each region. Add new
templates by dropping another file in `templates/` and listing it above.

The **High Level Design** template pairs with the `high-level-design` skill, which fills
its regions (requirements → entities → API → schema → architecture) and runs an
interactive deep-dive.

## Read the board

To see what's currently on the canvas, **`GET /api/design-read`** — it flattens the raw
tldraw snapshot into a concise digest (skip the raw `design-snapshot.json`):

```bash
curl -s http://localhost:7777/api/design-read
```

```jsonc
{
  "page": "ABI Hackathon",
  "shapeCount": 37, "arrowCount": 2,
  "shapes": [ { "id": "shape:…", "type": "geo", "geo": "rectangle",
               "x": 668, "y": 1493, "w": 191, "h": 168, "text": "Cronjob" }, … ],
  "arrows": [ { "id": "shape:…", "text": "triggers", "from": "Cronjob", "to": "Sync Service" }, … ]
}
```

Arrows are resolved through their bindings to the **labels** of the shapes they connect,
so you can read the graph directly (`from` → `to`). Rounded coords, only meaningful
props. Use this to learn existing shape IDs before editing, instead of parsing the
snapshot by hand.

The digest is **page-aware**: it details the *current* page and lists all pages under
`pages`. Read a specific page with `?page=`:

```bash
curl -s "http://localhost:7777/api/design-read?page=Twitter"   # by name (or page:id)
```

## Pages

The board supports multiple tldraw pages — handy for one design per page. From an exec:

```js
const pid = "page:hld-twitter";                       // page IDs are plain "page:<id>" strings
if (!editor.getPages().some(p => p.id === pid)) editor.createPage({ id: pid, name: "Twitter" });
editor.setCurrentPage(pid);                            // switch the view to it
// editor.deletePage(pid);                             // remove a page
```

- Use a **deterministic page ID** (`page:<slug>`) so re-runs across tabs don't spawn
  duplicate pages — same reasoning as deterministic shape/arrow IDs.
- **Shape IDs are unique per *document*, not per page** — namespace them per page (e.g.
  `hld-<slug>-fr`) so a second page's scaffold doesn't collide with the first's.
- To create a shape on a non-current page without switching the view, pass
  `parentId: "page:<id>"` in `createShape`.
- `createPageId` is **not** exposed (and not exported by tldraw) — build the
  `"page:<id>"` string directly.

See `templates/high-level-design.md` for a full "scaffold on a new page" exec.

## How to draw

POST to `http://localhost:7777/api/design-exec` with `{ "code": "<js string>" }`:

```bash
curl -s -X POST http://localhost:7777/api/design-exec \
  -H "Content-Type: application/json" \
  -d '{"code": "..."}'
```

The code runs inside `editor.run(() => { ... }, { history: "ignore" })` with these
globals available:

| Global | Description |
|---|---|
| `editor` | Live tldraw Editor instance |
| `createShapeId(str)` | Create a deterministic shape ID from a string |
| `toRichText(str)` | Convert plain text (with `\n`) to tldraw richText |
| `createArrowBetweenShapes(fromId, toId, opts?)` | Draw an arrow between two shapes |
| `boxShapes(ids[], opts?)` | Draw a bounding rectangle around a set of shapes |

## Shape creation

```js
// All shapes via editor.createShape({ id, type, x, y, props })
// Use createShapeId("my-id") for the id — deterministic, referenceable later

editor.createShape({
  id: createShapeId("box1"), type: "geo", x: 100, y: 100,
  props: { geo: "rectangle", w: 220, h: 80, text: "Hello",
           color: "blue", fill: "semi", size: "m", font: "draw",
           dash: "draw", richText: toRichText("Hello"),
           labelColor: "black", align: "middle", verticalAlign: "middle",
           growY: 0, scale: 1, url: "" }
})
```

**Geo types:** rectangle, ellipse, oval, diamond, triangle, hexagon, pentagon,
              octagon, trapezoid, rhombus, rhombus-2, cloud, star, heart,
              arrow-right, arrow-left, arrow-up, arrow-down, x-box, check-box

| Geo | Use for |
|---|---|
| rectangle | services, modules, components |
| ellipse / oval | databases; oval = pill start/end terminators |
| diamond | decision points |
| hexagon | event hubs, message buses |
| triangle | gateways, load balancers |
| cloud | external services |
| trapezoid | manual ops / transforms |
| rhombus / rhombus-2 | I/O steps (parallelogram, left/right slant) |
| arrow-right/left/up/down | directional flow blocks |
| x-box | failed / rejected / invalid state (box with ✕) |
| check-box | passed / validated / done state (box with ✓) |
| pentagon / octagon | stages; octagon = stop / terminal |

**Colors:** black, blue, green, yellow, orange, red, violet, grey, white,
            light-blue, light-green, light-red, light-violet

**Fill:** none, semi, solid, pattern

**Size:** s, m, l, xl

## Arrows

```js
// Preferred — binds to shapes by ID
createArrowBetweenShapes("box1", "box2")
createArrowBetweenShapes("box1", "box2", { text: "API call", bend: 0, color: "black" })
createArrowBetweenShapes("box1", "box2", { bend: 50 })  // curved
createArrowBetweenShapes("box1", "box2", { bidirectional: true })  // arrows on both ends
createArrowBetweenShapes("box1", "box2", { dash: "dashed" })  // async / optional link
```

**Full `opts`:** `text`, `bend`, `color`, `bidirectional`, `dash`
(`draw`|`solid`|`dashed`|`dotted`), `arrowheadStart`, `arrowheadEnd`,
`fromAnchor` / `toAnchor` (`{x,y}` in 0–1, where the arrow attaches on each shape),
`key`.

Arrow IDs are **deterministic** (`arr-<fromId>-<toId>`), so re-running the same exec —
e.g. when the board is open in several tabs that each poll `/api/design-exec` — overwrites
the arrow instead of creating duplicates. To draw **multiple distinct arrows between the
same pair**, pass a unique `key`:

```js
createArrowBetweenShapes("a", "b", { key: "req", text: "request", bend: -30 })
createArrowBetweenShapes("b", "a", { key: "resp", text: "response", bend: -30 })
```

> Note: any shape you create with `createShapeId("stable-name")` is similarly idempotent
> across tabs; only random/`Date.now()` IDs pile up. Prefer stable IDs.

### Arrowheads

`arrowheadStart` / `arrowheadEnd` each accept: `none`, `arrow` (default end),
`triangle` (UML inheritance — point at parent), `diamond` (UML composition — on
owner end), `dot`, `square`, `bar`, `pipe`, `inverted`.

```js
createArrowBetweenShapes("child", "parent", { arrowheadEnd: "triangle" })  // is-a
createArrowBetweenShapes("part", "whole", { arrowheadStart: "diamond", arrowheadEnd: "none" })  // composition
```

### Distributing arrows so they don't stack

When several arrows hit the **same shape** from different sources, give each a
distinct anchor instead of the default center so they don't overlap:

```js
createArrowBetweenShapes("a", "hub", { toAnchor: { x: 0.25, y: 0 } })  // top-left
createArrowBetweenShapes("b", "hub", { toAnchor: { x: 0.5,  y: 0 } })  // top-center
createArrowBetweenShapes("c", "hub", { toAnchor: { x: 0.75, y: 0 } })  // top-right
```

Anchors: top `{x,0}`, bottom `{x,1}`, left `{0,y}`, right `{1,y}`. Space N
connections on one side evenly (3 → x = 0.25, 0.5, 0.75).

### Multiple arrows between the *same two* nodes

Anchors can't separate these — fan the `bend` values symmetrically instead:

```js
// request / response pair — one straight, one curved reads cleanest
createArrowBetweenShapes("client", "server", { bend: 0,  text: "request" })
createArrowBetweenShapes("server", "client", { bend: 40, text: "response" })
```

For N arrows, space bends evenly from `-amount` to `+amount` (amount ≈ 30–60):
2 → `-amt, +amt`; 3 → `-amt, 0, +amt`.

## Group with bounding box

```js
boxShapes(["box1", "box2", "box3"], { text: "Service Layer", color: "blue" })
boxShapes(["a", "b"], { text: "Auth Flow", color: "violet", fill: "semi", padding: 40 })
```

## Read canvas state

```js
const shapes = editor.getCurrentPageShapes()
const bounds = editor.getShapePageBounds(createShapeId("box1"))  // { x, y, w, h, minX, minY, maxX, maxY }
editor.zoomToFit()
```

## Clear the canvas

```js
const ids = editor.getCurrentPageShapes().map(s => s.id);
if (ids.length) editor.deleteShapes(ids);
```

## Dynamic positioning (avoid overlaps)

```js
editor.createShape({ id: createShapeId("a"), type: "geo", x: 100, y: 100,
  props: { geo: "rectangle", w: 300, h: 100, richText: toRichText("Box A"),
           color: "blue", fill: "semi", size: "m", font: "draw", dash: "draw",
           labelColor: "black", align: "middle", verticalAlign: "middle",
           growY: 0, scale: 1, url: "" } })
const aB = editor.getShapePageBounds(createShapeId("a"))
editor.createShape({ id: createShapeId("b"), type: "geo", x: 100, y: aB.maxY + 20,
  props: { geo: "rectangle", w: 300, h: 100, richText: toRichText("Box B"),
           color: "green", fill: "semi", size: "m", font: "draw", dash: "draw",
           labelColor: "black", align: "middle", verticalAlign: "middle",
           growY: 0, scale: 1, url: "" } })
```

## Sticky note (annotation / callout)

For TODOs and comments *about* the diagram (not primary nodes — use `geo` for those):

```js
editor.createShape({ id: createShapeId("n1"), type: "note", x: 480, y: 80,
  props: { color: "yellow", size: "m", richText: toRichText("TODO: add retry\nlogic here"),
           font: "draw", align: "middle", verticalAlign: "middle",
           growY: 0, fontSizeAdjustment: 0, url: "", scale: 1, labelColor: "black" } })
```

A note has **no `w`/`h`** — it's a fixed ~200px square that auto-grows for longer text.

## Sizing boxes to fit labels

The `draw` font is wide. **Size `w`/`h` from the label up front** — if a box is too
small for its text, tldraw silently grows it taller (sets `growY`), so it ends up
bigger than the `h` you wrote and collides with whatever's below. This is the #1 cause
of "the diagram looks cramped / boxes overlap."

| `size` | char width (px) | line height (px) |
|---|---|---|
| s | 11 | 18 |
| m (default) | 15 | 28 |
| l | 22 | 40 |
| xl | 32 | 56 |

With `padding = 16` per side:
- `w = ceil(longest_line_chars * char_width + 32)`, rounded up to a multiple of 10
- `h = ceil(num_lines * line_height + 32)`, rounded up to a multiple of 10

Example: size-`m` `"API Gateway"` (11 chars, 1 line) → `w ≈ 11*15 + 32 = 197 → 200`,
`h ≈ 28 + 32 = 60`. Multi-line (`\n`) labels: count the **longest** line for `w`, the
line count for `h`. Err slightly large. Snap all `x/y/w/h` to multiples of 10.

## Layout guidelines

| Diagram type | Strategy |
|---|---|
| Pipeline / flow | Horizontal chain, 60–80px gaps, arrows left→right |
| Architecture | Swim lanes with `boxShapes`; service boxes inside |
| ERD / data model | Cluster entities; `boxShapes` for domain groups |
| State machine | Vertical top-down; branch left/right for decisions |

- Standard box: w=220–280, h=60–100 (but prefer the sizing formula above)
- Gap between boxes: 60–80px horizontal, 100–140px vertical
- Use `color: 'blue'` for infra/pipeline, `'green'` for outputs,
  `'red'` for errors, `'yellow'` for review, `'orange'` for processing,
  `'violet'` for data/schema, `'grey'` for external systems

## Diagram type presets

When the user names a diagram type, apply the matching shape/color/layout conventions.

### Architecture
| Element | geo | color |
|---|---|---|
| Client (web/mobile) | rectangle | blue |
| Service / module | rectangle | blue |
| Database | ellipse | green |
| Cache | ellipse | yellow |
| Queue / event bus | hexagon | orange |
| Gateway / load balancer | triangle | violet |
| External API | cloud | red (dashed arrows in) |
| Auth / security | rectangle | violet |

Layout: lanes by tier (≥4 tiers → top-down). Put hub nodes (event bus) in the
**center of the service row** so services reach it with short horizontal arrows.

### Flowchart
| Element | geo | color |
|---|---|---|
| Start / End | ellipse (or oval) | green |
| Process step | rectangle | blue |
| Decision | diamond | yellow |
| I/O | rectangle, `dash: "dashed"` | orange |
| Subprocess | rectangle | violet |

Top-down, ~200px vertical gap. **Label decision branches** (Yes/No) via the arrow's
`text`. Decisions branch left/right then merge back to center.

### Sequence (no native lifelines — approximate)
- Actor header: rectangle blue at top of each column.
- Lifeline: thin rectangle (`w: 2`, `fill: "solid"`, color grey) under each header.
- Sync msg: solid arrow; async msg: `dash: "dashed"`; return: grey dashed.

Actors left→right (200–280px apart); time flows top→down (each message at increasing y).

### ML / Deep Learning
| Element | geo | color |
|---|---|---|
| Input / Output | rectangle | green |
| Conv / Pooling | rectangle | blue |
| Attention / Transformer | rectangle | violet |
| RNN / LSTM / GRU | rectangle | yellow |
| FC / Linear | rectangle | orange |
| Loss / Activation | rectangle | red |
| Skip connection | arrow `{ bend: 30, dash: "dashed", color: "grey" }` | — |

Top-down. Annotate tensor shapes on a second line: `toRichText("Conv2D\n(B,64,32,32)")`.

### ERD (no native tables — approximate)
- Entity: tall rectangle, `fill: "solid"`, color light-blue; title + columns as one
  multi-line label (`*` prefix = PK, `>` = FK).
- Relationship: `createArrowBetweenShapes(a, b, { bidirectional: true })` for many-to-many;
  label cardinality (`1..*`, `0..1`) via `text`. Optional FK → `dash: "dashed"`, grey.
- Space entities ≥300px apart for the column lists.

### UML class
- Class: rectangle, `fill: "solid"`, light-blue; title + attributes + methods in one
  multi-line label.
- Inheritance → `{ arrowheadEnd: "triangle" }` pointing at the parent.
- Composition → `{ arrowheadStart: "diamond", arrowheadEnd: "none" }` on the owner end.
- Association → default arrow.

Note: tldraw's `triangle`/`diamond` heads are **filled** (strict UML uses hollow) —
fine for sketches/explainers, not publication-grade UML.

## Always

1. Call `editor.zoomToFit()` at the end of every exec.
2. Use `createShapeId("meaningful-name")` — never random IDs — so shapes can be updated later.
3. Read the board first (`GET /api/design-read`) if you need to know existing shape IDs before adding arrows. (The raw snapshot, if ever needed, is at `app/data/design-snapshot.json` relative to this skill.)
4. Send one focused `exec` per logical section — easier to debug if something goes wrong.
