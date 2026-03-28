#!/usr/bin/env python3
"""
NEMO Dashboard — Interactive Memory Graph
Generates a self-contained HTML file visualizing your memory graph.
Nodes = memories, sized by importance, colored by type.
Edges = semantic similarity >= threshold between stored embeddings.

Usage:
    python dashboard.py [--db PATH] [--limit 300] [--threshold 0.70] [--out dashboard.html]

No extra dependencies beyond what NEMO already uses.
Opens the generated HTML automatically in your default browser.
"""
import argparse
import json
import os
import sqlite3
import sys
import webbrowser
from pathlib import Path

import numpy as np

# ── Color palette by memory type ────────────────────────────────────────────
TYPE_COLORS = {
    "fact":             "#4e9af1",   # blue
    "procedure":        "#43d17a",   # green
    "correction":       "#f15353",   # red
    "preference":       "#c77dff",   # purple
    "insight":          "#ffb347",   # orange
    "episodic":         "#80deea",   # teal
    "intent_anchor":    "#ffd54f",   # amber
    "benchmark_result": "#78909c",   # grey-blue
    "benchmark_baseline":"#78909c",
    "ai_memory":        "#4e9af1",
    "roleplay":         "#f48fb1",   # pink
}
DEFAULT_COLOR = "#90a4ae"


def load_memories(db_path: str, limit: int) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT memory_id, content, memory_type, importance_level, tags, "
        "timestamp_created, embedding "
        "FROM curated_memories "
        "WHERE (importance_level IS NULL OR importance_level > 0) "
        "ORDER BY importance_level DESC, timestamp_created DESC "
        f"LIMIT {limit}"
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def build_graph(rows: list[dict], threshold: float) -> tuple[list, list]:
    nodes = []
    for r in rows:
        tags = []
        try:
            tags = json.loads(r["tags"] or "[]")
        except Exception:
            pass
        try:
            imp = int(r["importance_level"] or 5)
        except (ValueError, TypeError):
            imp = 5
        mtype = r["memory_type"] or "fact"
        content = r["content"] or ""
        nodes.append({
            "id":    r["memory_id"],
            "label": content[:45] + ("…" if len(content) > 45 else ""),
            "title": (
                f"<b>{mtype}</b> | imp={imp}<br>"
                f"tags: {', '.join(tags)}<br>"
                f"created: {(r['timestamp_created'] or '')[:10]}<br><br>"
                f"{content[:300]}"
            ),
            "value": imp,          # controls node size via vis-network
            "color": TYPE_COLORS.get(mtype, DEFAULT_COLOR),
            "font":  {"size": 11},
        })

    # Build edges from cosine similarities
    edges = []
    embeds = []
    valid_idx = []
    for i, r in enumerate(rows):
        blob = r.get("embedding")
        if blob and len(blob) >= 4:
            try:
                vec = np.frombuffer(blob, dtype=np.float32).copy()
                norm = np.linalg.norm(vec)
                if norm > 0:
                    embeds.append(vec / norm)
                    valid_idx.append(i)
            except Exception:
                pass

    if len(embeds) >= 2:
        matrix = np.vstack(embeds)          # (M, D)
        sims = matrix @ matrix.T             # (M, M) cosine
        n = len(valid_idx)
        edge_id = 0
        for a in range(n):
            for b in range(a + 1, n):
                s = float(sims[a, b])
                if s >= threshold:
                    edges.append({
                        "id":    edge_id,
                        "from":  rows[valid_idx[a]]["memory_id"],
                        "to":    rows[valid_idx[b]]["memory_id"],
                        "value": round(s, 3),   # controls edge width
                        "title": f"similarity: {s:.3f}",
                        "color": {"opacity": min(1.0, (s - threshold) / (1.0 - threshold) + 0.3)},
                    })
                    edge_id += 1

    return nodes, edges


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>NEMO Memory Graph</title>
<script src="https://unpkg.com/vis-network@9.1.9/dist/vis-network.min.js"></script>
<link  href="https://unpkg.com/vis-network@9.1.9/dist/vis-network.min.css" rel="stylesheet"/>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0d1117; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  #header { padding: 14px 20px; background: #161b22; border-bottom: 1px solid #30363d; display:flex; align-items:center; gap:16px; }
  #header h1 { font-size: 18px; font-weight: 600; }
  #stats { font-size: 13px; color: #8b949e; }
  #controls { padding: 10px 20px; background: #161b22; border-bottom: 1px solid #30363d; display:flex; gap:16px; align-items:center; flex-wrap:wrap; }
  #controls label { font-size: 12px; color: #8b949e; }
  #controls input[type=range] { width: 120px; }
  #controls select { background:#21262d; color:#e6edf3; border:1px solid #30363d; border-radius:4px; padding:3px 6px; font-size:12px; }
  #legend { display:flex; gap:10px; flex-wrap:wrap; }
  .leg-dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:4px; }
  .leg-item { font-size:11px; display:flex; align-items:center; }
  #container { width:100%; height: calc(100vh - 110px); }
  #tooltip-box { position:fixed; bottom:20px; right:20px; background:#161b22; border:1px solid #30363d;
    border-radius:8px; padding:12px 16px; max-width:340px; font-size:12px; line-height:1.6;
    display:none; color:#e6edf3; z-index:99; max-height:300px; overflow-y:auto; }
</style>
</head>
<body>
<div id="header">
  <h1>🧠 NEMO Memory Graph</h1>
  <span id="stats"></span>
</div>
<div id="controls">
  <div id="legend"></div>
  <label>Physics <input type="checkbox" id="physicsToggle" checked></label>
  <label>Filter type:
    <select id="typeFilter"><option value="">All types</option></select>
  </label>
  <label>Min importance:
    <input type="range" id="impSlider" min="1" max="10" value="1">
    <span id="impVal">1</span>
  </label>
</div>
<div id="container"></div>
<div id="tooltip-box" id="tooltip-box"></div>

<script>
const RAW_NODES = __NODES_JSON__;
const RAW_EDGES = __EDGES_JSON__;
const TYPE_COLORS = __TYPE_COLORS_JSON__;

const container = document.getElementById("container");
const statsEl   = document.getElementById("stats");
const legendEl  = document.getElementById("legend");
const tooltip   = document.getElementById("tooltip-box");

// Build legend
const seenTypes = [...new Set(RAW_NODES.map(n => {
  // recover type from color
  return Object.entries(TYPE_COLORS).find(([, c]) => c === n.color)?.[0] || "other";
}))];
seenTypes.forEach(t => {
  const col = TYPE_COLORS[t] || "#90a4ae";
  legendEl.innerHTML += `<span class="leg-item"><span class="leg-dot" style="background:${col}"></span>${t}</span>`;
});

// Populate type filter
const typeFilter = document.getElementById("typeFilter");
seenTypes.forEach(t => {
  typeFilter.innerHTML += `<option value="${t}">${t}</option>`;
});

// vis datasets
const nodesDS = new vis.DataSet(RAW_NODES);
const edgesDS = new vis.DataSet(RAW_EDGES);

statsEl.textContent = `${RAW_NODES.length} memories · ${RAW_EDGES.length} edges`;

const options = {
  nodes: { shape: "dot", scaling: { min:8, max:36, label:{enabled:true,min:10,max:22} }, borderWidth:1.5 },
  edges: { smooth:{type:"continuous"}, scaling:{min:0.5, max:4} },
  physics: { forceAtlas2Based:{gravitationalConstant:-60, springLength:150, springConstant:0.05}, solver:"forceAtlas2Based", stabilization:{iterations:200} },
  interaction: { hover:true, tooltipDelay:200, navigationButtons:false, keyboard:true },
};

const network = new vis.Network(container, { nodes: nodesDS, edges: edgesDS }, options);

network.on("selectNode", params => {
  if (!params.nodes.length) return;
  const node = RAW_NODES.find(n => n.id === params.nodes[0]);
  if (node) { tooltip.innerHTML = node.title; tooltip.style.display = "block"; }
});
network.on("deselectNode", () => { tooltip.style.display = "none"; });

document.getElementById("physicsToggle").addEventListener("change", e => {
  network.setOptions({ physics: { enabled: e.target.checked } });
});

function applyFilters() {
  const minImp  = parseInt(document.getElementById("impSlider").value);
  const selType = typeFilter.value;
  document.getElementById("impVal").textContent = minImp;
  const filtered = RAW_NODES.filter(n => {
    if (n.value < minImp) return false;
    if (selType && TYPE_COLORS[selType] !== n.color) return false;
    return true;
  });
  const filteredIds = new Set(filtered.map(n => n.id));
  nodesDS.clear(); nodesDS.add(filtered);
  edgesDS.clear();
  edgesDS.add(RAW_EDGES.filter(e => filteredIds.has(e.from) && filteredIds.has(e.to)));
  statsEl.textContent = `${filtered.length} memories · ${edgesDS.length} edges (filtered)`;
}
document.getElementById("impSlider").addEventListener("input", applyFilters);
typeFilter.addEventListener("change", applyFilters);
</script>
</body>
</html>"""


def generate_html(nodes: list, edges: list, out_path: str):
    html = HTML_TEMPLATE
    html = html.replace("__NODES_JSON__", json.dumps(nodes, ensure_ascii=False))
    html = html.replace("__EDGES_JSON__", json.dumps(edges, ensure_ascii=False))
    html = html.replace("__TYPE_COLORS_JSON__", json.dumps(TYPE_COLORS, ensure_ascii=False))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


def find_db() -> str:
    """Auto-detect NEMO database path."""
    data_dir = os.environ.get("AI_MEMORY_DATA_DIR")
    if data_dir:
        candidates = list(Path(data_dir).glob("*.db"))
        if candidates:
            return str(candidates[0])
    # default locations
    home = Path.home()
    for candidate in [
        home / ".ai_memory" / "ai_memories.db",
        home / ".ai_memory" / "memories.db",
        Path("ai_memories.db"),
    ]:
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError(
        "Could not auto-detect NEMO database. "
        "Set AI_MEMORY_DATA_DIR or pass --db PATH"
    )


def main():
    parser = argparse.ArgumentParser(description="Generate NEMO memory graph dashboard")
    parser.add_argument("--db",        default=None,             help="Path to ai_memories.db")
    parser.add_argument("--limit",     type=int, default=300,    help="Max memories to load (default: 300)")
    parser.add_argument("--threshold", type=float, default=0.70, help="Cosine similarity edge threshold (default: 0.70)")
    parser.add_argument("--out",       default="dashboard.html", help="Output HTML file (default: dashboard.html)")
    parser.add_argument("--no-open",   action="store_true",      help="Do not open browser automatically")
    args = parser.parse_args()

    db_path = args.db or find_db()
    print(f"[NEMO Dashboard] DB: {db_path}")

    rows = load_memories(db_path, args.limit)
    print(f"[NEMO Dashboard] Loaded {len(rows)} memories")

    nodes, edges = build_graph(rows, args.threshold)
    print(f"[NEMO Dashboard] Graph: {len(nodes)} nodes, {len(edges)} edges (threshold={args.threshold})")

    out = Path(args.out)
    generate_html(nodes, edges, str(out))
    print(f"[NEMO Dashboard] Generated: {out.resolve()}")

    if not args.no_open:
        webbrowser.open(out.resolve().as_uri())
        print("[NEMO Dashboard] Opened in browser")


if __name__ == "__main__":
    main()