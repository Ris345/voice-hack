import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "fs";
import path from "path";

const DATA = path.resolve(__dirname, "data");

// ---------------------------------------------------------------------------
// Board reader — flattens the raw tldraw snapshot into a concise, readable digest
// ---------------------------------------------------------------------------

function richText(rt: any): string {
  if (!rt || !rt.content) return "";
  return rt.content
    .map((blk: any) => (blk.content || []).map((c: any) => c.text || "").join(""))
    .join("\n")
    .trim();
}

// Walk a shape's parent chain up to the page it lives on.
function pageOfShape(store: Record<string, any>, shape: any): string | null {
  let cur = shape;
  const seen = new Set<string>();
  while (cur && cur.parentId && !seen.has(cur.id)) {
    seen.add(cur.id);
    if (typeof cur.parentId === "string" && cur.parentId.startsWith("page:")) return cur.parentId;
    cur = store[cur.parentId];
  }
  return null;
}

function summarizeBoard(pageQuery?: string) {
  const f = path.join(DATA, "design-snapshot.json");
  if (!fs.existsSync(f)) return { pages: [], shapes: [], arrows: [] };
  const snap = JSON.parse(fs.readFileSync(f, "utf8"));
  const store: Record<string, any> = snap?.document?.store || {};
  const records = Object.values(store) as any[];
  const bindings = records.filter((r) => r.typeName === "binding");
  const labelOf = (id: string) => richText(store[id]?.props?.richText) || id;

  const pages = records
    .filter((r) => r.typeName === "page")
    .sort((a, b) => String(a.index).localeCompare(String(b.index)));
  const currentPageId: string = snap?.session?.currentPageId || pages[0]?.id;

  // Resolve which page to detail: query (by id or name) else current.
  let targetId = currentPageId;
  if (pageQuery) {
    const m = pages.find(
      (p) => p.id === pageQuery || (p.name || "").toLowerCase() === pageQuery.toLowerCase()
    );
    if (m) targetId = m.id;
  }

  const shapes: any[] = [];
  const arrows: any[] = [];
  for (const s of records) {
    if (s.typeName !== "shape") continue;
    if (pageOfShape(store, s) !== targetId) continue;
    if (s.type === "arrow") {
      const sb = bindings.find((b) => b.fromId === s.id && b.props.terminal === "start");
      const eb = bindings.find((b) => b.fromId === s.id && b.props.terminal === "end");
      arrows.push({
        id: s.id,
        text: richText(s.props?.richText) || undefined,
        from: sb ? labelOf(sb.toId) : null,
        to: eb ? labelOf(eb.toId) : null,
      });
      continue;
    }
    const e: any = { id: s.id, type: s.type, x: Math.round(s.x), y: Math.round(s.y) };
    if (s.props?.w != null) e.w = Math.round(s.props.w);
    if (s.props?.h != null) e.h = Math.round(s.props.h);
    if (s.props?.geo) e.geo = s.props.geo;
    const t = richText(s.props?.richText);
    if (t) e.text = t;
    shapes.push(e);
  }

  const pageList = pages.map((p) => ({ id: p.id, name: p.name, current: p.id === currentPageId }));
  const targetName = pages.find((p) => p.id === targetId)?.name;
  return {
    page: targetName,
    pages: pageList,
    shapeCount: shapes.length,
    arrowCount: arrows.length,
    shapes,
    arrows,
  };
}

function apiMiddleware() {
  return {
    name: "tldraw-api",
    configureServer(server: any) {
      function readFile(name: string, fallback: object) {
        const f = path.join(DATA, name);
        return fs.existsSync(f) ? fs.readFileSync(f, "utf8") : JSON.stringify(fallback);
      }
      function writeFile(name: string, data: object) {
        fs.mkdirSync(DATA, { recursive: true });
        fs.writeFileSync(path.join(DATA, name), JSON.stringify(data, null, 2));
      }
      function handle(name: string, fallback: object) {
        return (req: any, res: any, next: any) => {
          if (!req.url.startsWith(`/api/${name}`)) return next();
          res.setHeader("Content-Type", "application/json");
          res.setHeader("Access-Control-Allow-Origin", "*");
          if (req.method === "GET") {
            res.end(readFile(`${name}.json`, fallback));
          } else if (req.method === "POST") {
            let body = "";
            req.on("data", (c: any) => (body += c));
            req.on("end", () => {
              const data = JSON.parse(body);
              data.version = data.version || Date.now();
              writeFile(`${name}.json`, data);
              res.end(JSON.stringify({ status: "saved", version: data.version }));
            });
          } else {
            res.statusCode = 405;
            res.end("{}");
          }
        };
      }
      server.middlewares.use((req: any, res: any, next: any) => {
        if (!req.url.startsWith("/api/ping")) return next();
        res.setHeader("Content-Type", "application/json");
        res.setHeader("Access-Control-Allow-Origin", "*");
        res.end(JSON.stringify({ ok: true, name: "tldraw-local", board: "/design-board.html" }));
      });
      server.middlewares.use((req: any, res: any, next: any) => {
        if (!req.url.startsWith("/api/design-read")) return next();
        const query = new URLSearchParams(req.url.split("?")[1] || "").get("page") || undefined;
        res.setHeader("Content-Type", "application/json");
        res.setHeader("Access-Control-Allow-Origin", "*");
        res.end(JSON.stringify(summarizeBoard(query), null, 2));
      });
      server.middlewares.use(handle("design-exec",     { version: 0, code: "" }));
      server.middlewares.use(handle("design-patch",    { version: 0, put: [], remove: [] }));
      server.middlewares.use(handle("design-snapshot", {}));
    },
  };
}

const PORT = Number(process.env.TLDRAW_LOCAL_PORT || process.env.PORT || 7777);

export default defineConfig({
  server: { port: PORT },
  plugins: [react(), apiMiddleware()],
});
