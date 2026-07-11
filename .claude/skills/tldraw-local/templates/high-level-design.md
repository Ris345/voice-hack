# Template: High Level Design

A board scaffold for system design. A large central **Architecture** canvas is flanked
by the five requirement/data regions — **FR / NFR / API Design** stacked down the left,
**Entities / Database Schema** down the right. The user (or the `high-level-design`
skill) fills each region.

## Regions

| Region | Shape ID | What goes in it |
|---|---|---|
| Functional Requirements | `tpl-hld-fr` | "Users/Clients should be able to…" — top ~3 core features |
| Non-Functional Requirements | `tpl-hld-nfr` | "The system should…" — quantified, top 3–5 |
| API Design | `tpl-hld-api` | Core endpoints / RPCs: method, path, request → response |
| Entities | `tpl-hld-ent` | Major data entities + key attributes + relationships |
| Database Schema | `tpl-hld-schema` | Tables/collections, columns, types, keys & indexes |
| High-Level Architecture | `tpl-hld-arch` | Large central canvas: components + data flow that satisfy the FRs |
| (architecture title) | `tpl-hld-arch-title` | "High Level Architecture" text label above the arch canvas |

> Note: the architecture region is the centerpiece and is what the deep-dive phase
> hardens. It's an unlabeled canvas (with a separate title text) so there's room for a
> full component diagram.

## Layout

```
                 ┌──────────────────────────────┐
 ┌──────────┐    │                              │    ┌──────────┐
 │   FR     │    │                              │    │ Entities │
 ├──────────┤    │   High-Level Architecture    │    ├──────────┤
 │   NFR    │    │        (large canvas)        │    │  Schema  │
 ├──────────┤    │                              │    └──────────┘
 │   API    │    │                              │
 └──────────┘    └──────────────────────────────┘
```

| Region | x | y | w | h |
|---|---|---|---|---|
| `tpl-hld-fr` | -1100 | -300 | 1000 | 900 |
| `tpl-hld-nfr` | -1100 | 600 | 1000 | 900 |
| `tpl-hld-api` | -1100 | 1500 | 1000 | 900 |
| `tpl-hld-ent` | 2500 | -300 | 1000 | 900 |
| `tpl-hld-schema` | 2500 | 600 | 1000 | 900 |
| `tpl-hld-arch` | -100 | -300 | 2600 | 2700 |
| `tpl-hld-arch-title` | 1000 | -340 | (auto) | text |

Side regions are 1000×900, stacked flush (900px pitch). The architecture canvas
(2600×2700) sits flush between the columns and spans the full height; its title text
floats just above its top edge. Section titles sit top-left so contents fill below.

## Scaffold exec

POST this to `http://localhost:7777/api/design-exec` (as `{ "code": "…" }`) to draw the
empty labeled regions:

```js
// Five side regions — labeled, title top-left
const SECTIONS = [
  ["tpl-hld-fr",     -1100, -300, "Functional Requirements"],
  ["tpl-hld-nfr",    -1100,  600, "Non-Functional Requirements"],
  ["tpl-hld-api",    -1100, 1500, "API Design"],
  ["tpl-hld-ent",     2500, -300, "Entities"],
  ["tpl-hld-schema",  2500,  600, "Database Schema"],
];
for (const [id, x, y, title] of SECTIONS) {
  editor.createShape({
    id: createShapeId(id), type: "geo", x, y,
    props: { geo: "rectangle", w: 1000, h: 900, color: "black", fill: "none",
             dash: "draw", size: "l", font: "draw", richText: toRichText(title),
             labelColor: "black", align: "start", verticalAlign: "start",
             growY: 0, scale: 1, url: "" },
  });
}
// Central architecture canvas (unlabeled) + floating title text
editor.createShape({
  id: createShapeId("tpl-hld-arch"), type: "geo", x: -100, y: -300,
  props: { geo: "rectangle", w: 2600, h: 2700, color: "black", fill: "none",
           dash: "draw", size: "m", font: "draw", richText: toRichText(""),
           labelColor: "black", align: "middle", verticalAlign: "middle",
           growY: 0, scale: 1, url: "" },
});
editor.createShape({
  id: createShapeId("tpl-hld-arch-title"), type: "text", x: 1000, y: -340,
  props: { richText: toRichText("High Level Architecture"), color: "black",
           size: "m", font: "draw", textAlign: "start", autoSize: true, scale: 1 },
});
editor.zoomToFit();
```

## Scaffold on a new page

To put a design on its **own tldraw page** (e.g. one page per system), create the page
and scaffold it in one exec. Both the page ID and the region IDs are **deterministic**
(derived from a slug of the name) so re-running — including across multiple open tabs —
overwrites instead of duplicating.

- Page ID: `page:hld-<slug>` · Region IDs: `hld-<slug>-{fr,nfr,api,ent,schema,arch}`
- `<slug>` = the name lower-cased, non-alphanumerics → `-`.

```js
const NAME = "Twitter";                                   // design / page name
const slug = NAME.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
const pid  = "page:hld-" + slug;
if (!editor.getPages().some(p => p.id === pid)) editor.createPage({ id: pid, name: NAME });

const SECTIONS = [
  ["fr",     -1100, -300, "Functional Requirements"],
  ["nfr",    -1100,  600, "Non-Functional Requirements"],
  ["api",    -1100, 1500, "API Design"],
  ["ent",     2500, -300, "Entities"],
  ["schema",  2500,  600, "Database Schema"],
];
for (const [key, x, y, title] of SECTIONS) {
  editor.createShape({
    id: createShapeId(`hld-${slug}-${key}`), type: "geo", x, y, parentId: pid,
    props: { geo: "rectangle", w: 1000, h: 900, color: "black", fill: "none",
             dash: "draw", size: "l", font: "draw", richText: toRichText(title),
             labelColor: "black", align: "start", verticalAlign: "start",
             growY: 0, scale: 1, url: "" },
  });
}
editor.createShape({
  id: createShapeId(`hld-${slug}-arch`), type: "geo", x: -100, y: -300, parentId: pid,
  props: { geo: "rectangle", w: 2600, h: 2700, color: "black", fill: "none",
           dash: "draw", size: "m", font: "draw", richText: toRichText(""),
           labelColor: "black", align: "middle", verticalAlign: "middle",
           growY: 0, scale: 1, url: "" },
});
editor.createShape({
  id: createShapeId(`hld-${slug}-arch-title`), type: "text", x: 1000, y: -340, parentId: pid,
  props: { richText: toRichText("High Level Architecture"), color: "black",
           size: "m", font: "draw", textAlign: "start", autoSize: true, scale: 1 },
});
editor.setCurrentPage(pid);   // switch the view to the new page; omit to scaffold in the background
editor.zoomToFit();
```

> Passing `parentId: pid` on each shape places it on the new page regardless of which
> page is currently shown — so the scaffold lands correctly even without switching. Read
> a specific page back with `GET /api/design-read?page=<name or page-id>`.

## Filling the regions

- Inset contents ~28px inside each container.
- **FR / NFR** — stacked `size: "s"` rows; light-blue for FR, light-green for NFR
  (see the tldraw-local box-sizing notes).
- **API Design** — one row per endpoint, mono-ish text like
  `POST /tweet  →  {id}` / `GET /feed?cursor  →  [tweet]`.
- **Entities** — a box per entity with a multi-line label (name + key attributes);
  connect related entities with arrows labeled by cardinality (`1:N`, `N:M`).
- **Database Schema** — a box per table: title line then `column : type` rows; mark PK
  with `*`, FK with `>` (right column, lower).
- **Architecture** — the large central canvas: component boxes + directional arrows
  labeled with the operation; use tldraw-local's color conventions. It has the most room
  by design. Deep-dive additions go in **orange** to stand out from the baseline.
