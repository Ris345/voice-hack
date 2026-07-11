import React from "react";
import { createRoot } from "react-dom/client";
import { Tldraw, createShapeId, createBindingId, toRichText } from "tldraw";
import "tldraw/tldraw.css";
import type { Editor } from "tldraw";

// ---------------------------------------------------------------------------
// Exec helpers — same API as the tldraw skill
// ---------------------------------------------------------------------------

function makeExecContext(editor: Editor) {
  function createArrowBetweenShapes(
    fromId: string,
    toId: string,
    opts: {
      text?: string; bend?: number; color?: string; bidirectional?: boolean;
      arrowheadStart?: string; arrowheadEnd?: string; dash?: string;
      fromAnchor?: { x: number; y: number }; toAnchor?: { x: number; y: number };
      key?: string;
    } = {}
  ) {
    // Deterministic id so re-running the same exec (e.g. across multiple open
    // board tabs) overwrites rather than piling up duplicates. Pass `key` to
    // draw multiple distinct arrows between the same pair.
    const arrowId = createShapeId(`arr-${fromId}-${toId}${opts.key ? `-${opts.key}` : ""}`);
    editor.createShape({
      id: arrowId,
      type: "arrow",
      x: 0, y: 0,
      props: {
        kind: "arc",
        bend: opts.bend ?? 0,
        color: (opts.color ?? "black") as any,
        size: "m",
        arrowheadStart: (opts.arrowheadStart ?? (opts.bidirectional ? "arrow" : "none")) as any,
        arrowheadEnd: (opts.arrowheadEnd ?? "arrow") as any,
        fill: "none",
        dash: (opts.dash ?? "draw") as any,
        font: "draw",
        richText: toRichText(opts.text ?? ""),
        labelPosition: 0.5,
        scale: 1,
        elbowMidPoint: 0.5,
        start: { x: 0, y: 0 },
        end: { x: 100, y: 0 },
      },
    });
    editor.createBinding({
      id: createBindingId(`${arrowId}-s`),
      type: "arrow",
      fromId: arrowId,
      toId: createShapeId(fromId),
      props: { terminal: "start", normalizedAnchor: opts.fromAnchor ?? { x: 0.5, y: 0.5 }, isExact: false, isPrecise: false, snap: "none" },
    });
    editor.createBinding({
      id: createBindingId(`${arrowId}-e`),
      type: "arrow",
      fromId: arrowId,
      toId: createShapeId(toId),
      props: { terminal: "end", normalizedAnchor: opts.toAnchor ?? { x: 0.5, y: 0.5 }, isExact: false, isPrecise: false, snap: "none" },
    });
    return arrowId;
  }

  function boxShapes(ids: string[], opts: { text?: string; color?: string; fill?: string; padding?: number } = {}) {
    const padding = opts.padding ?? 40;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const id of ids) {
      const b = editor.getShapePageBounds(createShapeId(id));
      if (!b) continue;
      minX = Math.min(minX, b.minX); minY = Math.min(minY, b.minY);
      maxX = Math.max(maxX, b.maxX); maxY = Math.max(maxY, b.maxY);
    }
    const frameId = createShapeId(`box-${Date.now()}`);
    editor.createShape({
      id: frameId, type: "geo",
      x: minX - padding, y: minY - padding,
      props: {
        w: maxX - minX + padding * 2, h: maxY - minY + padding * 2,
        geo: "rectangle", color: (opts.color ?? "black") as any,
        fill: (opts.fill ?? "none") as any, size: "m", dash: "draw", font: "draw",
        richText: toRichText(opts.text ?? ""), align: "start", verticalAlign: "start",
        labelColor: "black", growY: 0, scale: 1, url: "",
      },
    });
    return frameId;
  }

  return { editor, createArrowBetweenShapes, boxShapes };
}

// ---------------------------------------------------------------------------
// Sync indicator
// ---------------------------------------------------------------------------

type SyncStatus = "idle" | "saving" | "saved" | "error";

function SyncIndicator({ status }: { status: SyncStatus }) {
  if (status === "idle") return null;
  const label = { saving: "Saving…", saved: "Synced", error: "Sync error" }[status];
  const bg = { saving: "#868e96", saved: "#2f9e44", error: "#e03131" }[status];
  return (
    <div style={{
      position: "fixed", bottom: 16, right: 16, zIndex: 9999,
      padding: "6px 14px", borderRadius: 6, background: bg,
      color: "#fff", fontSize: 13, fontWeight: 600,
      boxShadow: "0 2px 8px rgba(0,0,0,0.2)", pointerEvents: "none",
    }}>
      {label}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Board
// ---------------------------------------------------------------------------

function Board() {
  const [status, setStatus] = React.useState<SyncStatus>("idle");
  const editorRef = React.useRef<Editor | null>(null);
  const timerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const debounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const patchVersionRef = React.useRef(0);
  const execVersionRef = React.useRef(0);

  // Auto-save snapshot on user changes
  function onMount(editor: Editor) {
    editorRef.current = editor;
    editor.store.listen(() => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(async () => {
        setStatus("saving");
        try {
          const res = await fetch("/api/design-snapshot", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(editor.getSnapshot()),
          });
          setStatus(res.ok ? "saved" : "error");
        } catch { setStatus("error"); }
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => setStatus("idle"), 2000);
      }, 500);
    }, { scope: "document", source: "user" });
  }

  // Poll for raw store patches
  React.useEffect(() => {
    const iv = setInterval(async () => {
      try {
        const patch = await fetch("/api/design-patch").then(r => r.json());
        if (!patch.version || patch.version === patchVersionRef.current) return;
        patchVersionRef.current = patch.version;
        const editor = editorRef.current;
        if (!editor) return;
        editor.store.mergeRemoteChanges(() => {
          if (patch.put?.length)    editor.store.put(patch.put);
          if (patch.remove?.length) editor.store.remove(patch.remove);
        });
      } catch {}
    }, 1000);
    return () => clearInterval(iv);
  }, []);

  // Poll for JS exec commands
  React.useEffect(() => {
    const iv = setInterval(async () => {
      try {
        const payload = await fetch("/api/design-exec").then(r => r.json());
        if (!payload.version || payload.version === execVersionRef.current) return;
        execVersionRef.current = payload.version;
        const editor = editorRef.current;
        if (!editor || !payload.code) return;
        const { createArrowBetweenShapes, boxShapes } = makeExecContext(editor);
        editor.run(() => {
          // eslint-disable-next-line no-new-func
          new Function("editor", "createShapeId", "createArrowBetweenShapes", "boxShapes", "toRichText", payload.code)(
            editor, createShapeId, createArrowBetweenShapes, boxShapes, toRichText
          );
        }, { history: "ignore" });
      } catch (e) { console.error("design-exec error", e); }
    }, 1000);
    return () => clearInterval(iv);
  }, []);

  return (
    <div style={{ position: "fixed", inset: 0 }}>
      <Tldraw persistenceKey="tldraw-local" onMount={onMount} />
      <SyncIndicator status={status} />
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Board />
  </React.StrictMode>
);
