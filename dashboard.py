#!/usr/bin/env python3
"""
NEMO Dashboard — Cosmograph Memory Graph (WebGL / brain-inspired)
Generates a self-contained HTML file visualizing your memory graph.
Nodes = memories, sized by importance, colored by type.
Edges = semantic similarity >= threshold between stored embeddings.

Uses Cosmograph (WebGL) for GPU-accelerated rendering of large graphs.

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

# ── Neuron color palette by memory type ─────────────────────────────────────
# Inspired by neuroscience: excitatory (warm), inhibitory (cool),
# structural (teal), reward/salience (amber), error-signal (red)
TYPE_COLORS = {
    "fact":              "#00b4d8",  # cognitive blue  — declarative memory
    "procedure":         "#06d6a0",  # motor teal      — procedural memory
    "correction":        "#ff4757",  # error red       — prediction-error signal
    "preference":        "#a855f7",  # dopamine purple — reward/preference
    "insight":           "#ff9f1c",  # salience amber  — discovery/aha moment
    "episodic":          "#48cae4",  # hippocampus cyan — episodic memory
    "intent_anchor":     "#f7b731",  # prospective gold — future intentions
    "benchmark_result":  "#546e7a",  # grey-slate
    "benchmark_baseline":"#546e7a",
    "ai_memory":         "#00b4d8",
    "roleplay":          "#f06292",  # pink — narrative
}
DEFAULT_COLOR = "#607d8b"


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
        excerpt = content[:80] + ("…" if len(content) > 80 else "")
        nodes.append({
            "id":         r["memory_id"],
            "mtype":      mtype,
            "importance": imp,
            "color":      TYPE_COLORS.get(mtype, DEFAULT_COLOR),
            "excerpt":    excerpt,
            "tags":       tags,
            "created":    (r["timestamp_created"] or "")[:10],
            "content":    content[:400],
        })

    # Build edges from cosine similarities (Cosmograph uses source/target)
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
        matrix = np.vstack(embeds)   # (M, D)
        sims = matrix @ matrix.T     # (M, M) cosine similarity
        n = len(valid_idx)
        for a in range(n):
            for b in range(a + 1, n):
                s = float(sims[a, b])
                if s >= threshold:
                    edges.append({
                        "source":     rows[valid_idx[a]]["memory_id"],
                        "target":     rows[valid_idx[b]]["memory_id"],
                        "similarity": round(s, 4),
                    })

    return nodes, edges


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>NEMO · Neural Memory Graph</title>
<!-- three.min.js must load FIRST so window.THREE is available for 3d-force-graph (peer dep, not bundled) -->
<script src="https://unpkg.com/three@0.155.0/build/three.min.js"></script>
<!-- Postprocessing passes (attached to THREE.* by these legacy scripts) -->
<script src="https://unpkg.com/three@0.155.0/examples/js/shaders/CopyShader.js"></script>
<script src="https://unpkg.com/three@0.155.0/examples/js/shaders/LuminosityHighPassShader.js"></script>
<script src="https://unpkg.com/three@0.155.0/examples/js/postprocessing/EffectComposer.js"></script>
<script src="https://unpkg.com/three@0.155.0/examples/js/postprocessing/RenderPass.js"></script>
<script src="https://unpkg.com/three@0.155.0/examples/js/postprocessing/ShaderPass.js"></script>
<script src="https://unpkg.com/three@0.155.0/examples/js/postprocessing/UnrealBloomPass.js"></script>
<script src="https://unpkg.com/3d-force-graph@1.73.5/dist/3d-force-graph.min.js"></script>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:        #0c0c14;
    --surface:   rgba(16, 14, 36, 0.68);
    --border:    rgba(255, 255, 255, 0.09);
    --border-hi: rgba(192, 132, 252, 0.4);
    --accent:    #C084FC;
    --accent2:   #67E8F9;
    --text:      #e8e8f4;
    --muted:     #68668a;
    --panel-w:   320px;
  }

  html, body {
    width: 100%; height: 100%;
    background:
      radial-gradient(ellipse 90% 70% at 20% 15%, #1a1a3e 0%, transparent 55%),
      radial-gradient(ellipse 70% 55% at 80% 80%, #0d0d2a 0%, transparent 55%),
      radial-gradient(ellipse 50% 80% at 50% 100%, #110d1e 0%, transparent 60%),
      #0c0c14;
    color: var(--text);
    font-family: 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;
    overflow: hidden;
  }

  #nebula {
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background:
      radial-gradient(ellipse 60% 40% at 25% 30%, rgba(192,132,252,0.06) 0%, transparent 60%),
      radial-gradient(ellipse 50% 35% at 70% 65%, rgba(103,232,249,0.04) 0%, transparent 55%);
  }
  #starfield { position: fixed; inset: 0; z-index: 0; pointer-events: none; }
  #graph-root { position: fixed; inset: 0; z-index: 1; }
  #graph-root canvas { display: block; }

  /* ── Top HUD ── */
  #hud {
    position: fixed; top: 0; left: 0; right: 0; z-index: 10;
    display: flex; align-items: center; gap: 18px;
    padding: 12px 22px;
    background: rgba(12,12,20,0.60);
    backdrop-filter: blur(28px) saturate(180%);
    -webkit-backdrop-filter: blur(28px) saturate(180%);
    border-bottom: 0.5px solid rgba(255,255,255,0.08);
    box-shadow: 0 1px 0 rgba(192,132,252,0.08);
    animation: slideDown 0.5s ease;
  }
  @keyframes slideDown { from { transform: translateY(-100%); opacity:0; } to { transform: none; opacity:1; } }
  #hud-title {
    font-size: 17px; font-weight: 700; letter-spacing: 2.5px;
    background: linear-gradient(90deg, #C084FC 0%, #a78bfa 40%, #67E8F9 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    text-transform: uppercase;
  }
  #hud-stats { font-size: 12px; color: var(--muted); letter-spacing: 0.5px; }
  #hud-pulse {
    width: 8px; height: 8px; border-radius: 50%; background: #C084FC; flex-shrink: 0;
    animation: pulse 2.5s ease-in-out infinite;
  }
  @keyframes pulse {
    0%,100% { box-shadow: 0 0 0 0 rgba(192,132,252,0.8); }
    50%      { box-shadow: 0 0 0 8px rgba(192,132,252,0); }
  }
  #hud-spacer { flex: 1; }

  /* ── Side Panel ── */
  #panel {
    position: fixed; top: 56px; right: 0; bottom: 0; width: var(--panel-w);
    z-index: 10;
    background: rgba(12,10,24,0.62);
    backdrop-filter: blur(28px) saturate(160%);
    -webkit-backdrop-filter: blur(28px) saturate(160%);
    border-left: 0.5px solid rgba(255,255,255,0.10);
    box-shadow: -1px 0 0 rgba(192,132,252,0.06), inset 1px 0 0 rgba(255,255,255,0.04);
    display: flex; flex-direction: column;
    transition: transform 0.45s cubic-bezier(0.4,0,0.2,1);
  }
  #panel.collapsed { transform: translateX(var(--panel-w)); }
  #panel-inner { transition: filter 0.25s ease; }
  #panel-toggle {
    position: absolute; left: -34px; top: 50%; transform: translateY(-50%);
    width: 34px; height: 56px;
    background: rgba(12,10,24,0.62);
    backdrop-filter: blur(28px);
    -webkit-backdrop-filter: blur(28px);
    border: 0.5px solid rgba(255,255,255,0.10); border-right: none;
    border-radius: 8px 0 0 8px; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    color: var(--accent); font-size: 14px;
  }
  #panel-inner { padding: 18px; overflow-y: auto; flex: 1; }
  .panel-section { margin-bottom: 20px; }
  .panel-section h3 {
    font-size: 10px; font-weight: 700; letter-spacing: 2px;
    text-transform: uppercase; color: var(--muted);
    margin-bottom: 10px; padding-bottom: 6px;
    border-bottom: 1px solid var(--border);
  }

  /* Legend */
  .leg-row {
    display: flex; align-items: center; gap: 8px;
    padding: 5px 6px; font-size: 12px; cursor: pointer;
    border-radius: 4px; transition: background 0.15s;
  }
  .leg-row:hover { background: rgba(0,180,216,0.08); }
  .leg-row.inactive { opacity: 0.35; }
  .leg-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; box-shadow: 0 0 6px currentColor, 0 0 12px currentColor; opacity: 0.85; }
  .leg-count { margin-left: auto; font-size: 10px; color: var(--muted); }

  /* Controls */
  .ctrl-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; font-size: 12px; }
  .ctrl-row label { color: var(--muted); min-width: 100px; }
  .ctrl-row input[type=range] {
    flex: 1; -webkit-appearance: none; height: 3px; border-radius: 2px; outline: none;
    background: linear-gradient(to right, var(--accent) 0%, var(--accent) var(--pct, 0%), rgba(0,180,216,0.2) var(--pct,0%));
  }
  .ctrl-row input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none; width: 12px; height: 12px; border-radius: 50%;
    background: var(--accent); box-shadow: 0 0 8px var(--accent), 0 0 16px rgba(192,132,252,0.4); cursor: pointer;
  }
  .ctrl-val { min-width: 26px; text-align: right; color: var(--accent); font-weight: 600; }
  select {
    background: rgba(0,0,0,0.4); color: var(--text); border: 1px solid var(--border);
    border-radius: 5px; padding: 4px 8px; font-size: 12px; width: 100%;
  }
  select option { background: #0d1117; }

  /* Info card */
  #info-card {
    position: fixed; bottom: 24px; left: 24px;
    width: 360px; max-height: 260px; z-index: 20;
    background: rgba(14,12,28,0.72);
    backdrop-filter: blur(32px) saturate(160%);
    -webkit-backdrop-filter: blur(32px) saturate(160%);
    border: 0.5px solid rgba(255,255,255,0.12);
    box-shadow: 0 8px 32px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.06), 0 0 0 0.5px rgba(192,132,252,0.1);
    border-radius: 16px;
    padding: 16px 18px; overflow-y: auto; display: none;
    animation: cardIn 0.3s cubic-bezier(0.34,1.56,0.64,1);
  }
  @keyframes cardIn { from { opacity:0; transform: translateY(14px) scale(0.97); } to { opacity:1; transform: none; } }
  @keyframes cardIn { from { opacity:0; transform: translateY(12px); } to { opacity:1; transform: none; } }
  #info-card .card-type { font-size: 10px; letter-spacing: 2px; text-transform: uppercase; font-weight: 700; margin-bottom: 6px; }
  #info-card .card-imp  { font-size: 11px; color: var(--muted); margin-bottom: 8px; }
  #info-card .card-tags { display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 10px; }
  #info-card .tag { font-size: 10px; padding: 2px 8px; border-radius: 20px; background: rgba(192,132,252,0.08); border: 0.5px solid rgba(192,132,252,0.30); color: var(--accent); letter-spacing: 0.3px; }
  #info-card .card-content { font-size: 12px; line-height: 1.65; }
  #info-close { position: absolute; top: 10px; right: 12px; font-size: 16px; cursor: pointer; color: var(--muted); }
  #info-close:hover { color: var(--text); }
  .imp-stars { color: var(--accent2); letter-spacing: 1px; }

  /* Search */
  #search {
    background: rgba(255,255,255,0.05); color: var(--text);
    border: 0.5px solid rgba(255,255,255,0.12); border-radius: 20px;
    padding: 5px 14px; font-size: 12px; width: 220px; outline: none;
    backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
    transition: border-color 0.3s, box-shadow 0.3s;
  }
  #search:focus { border-color: rgba(192,132,252,0.6); box-shadow: 0 0 0 3px rgba(192,132,252,0.12); }
  #search::placeholder { color: var(--muted); }

  /* Hover tooltip */
  #tooltip {
    position: fixed; z-index: 30; pointer-events: none; display: none;
    background: rgba(3,5,13,0.92); backdrop-filter: blur(10px);
    border: 1px solid var(--border); border-radius: 8px;
    padding: 8px 12px; font-size: 11px; line-height: 1.55;
    max-width: 260px; color: var(--text);
    box-shadow: 0 4px 20px rgba(0,0,0,0.6);
  }
</style>
</head>
<body>

<div id="nebula"></div>
<canvas id="starfield"></canvas>
<div id="graph-root"></div>

<div id="hud">
  <div id="hud-pulse"></div>
  <span id="hud-title">NEMO &middot; Neural Memory</span>
  <span id="hud-stats">loading&hellip;</span>
  <div id="hud-spacer"></div>
  <input id="search" type="text" placeholder="&#x1F50D; Search memories…" autocomplete="off" spellcheck="false">
</div>

<div id="panel">
  <button id="panel-toggle" title="Toggle panel">&#9664;</button>
  <div id="panel-inner">
    <div class="panel-section">
      <h3>Memory Types</h3>
      <div id="legend"></div>
    </div>
    <div class="panel-section">
      <h3>Filters</h3>
      <div class="ctrl-row">
        <label>Min importance</label>
        <input type="range" id="impSlider" min="1" max="10" value="1">
        <span class="ctrl-val" id="impVal">1</span>
      </div>
      <div class="ctrl-row">
        <label>Min similarity</label>
        <input type="range" id="simSlider" min="0.60" max="0.99" step="0.01" value="0.70">
        <span class="ctrl-val" id="simVal">0.70</span>
      </div>
      <div class="ctrl-row" style="margin-top:4px;"><label>Type</label></div>
      <select id="typeFilter"><option value="">All types</option></select>
    </div>
    <div class="panel-section">
      <h3>Simulation</h3>
      <div class="ctrl-row">
        <label>Repulsion</label>
        <input type="range" id="repSlider" min="0.2" max="4" step="0.1" value="1.5">
        <span class="ctrl-val" id="repVal">1.5</span>
      </div>
      <div class="ctrl-row">
        <label>Link spring</label>
        <input type="range" id="springSlider" min="0.05" max="2" step="0.05" value="0.3">
        <span class="ctrl-val" id="springVal">0.3</span>
      </div>
    </div>
  </div>
</div>

<div id="tooltip"></div>

<div id="info-card">
  <span id="info-close" title="Close">&#x2715;</span>
  <div class="card-type" id="card-type"></div>
  <div class="card-imp"  id="card-imp"></div>
  <div class="card-tags" id="card-tags"></div>
  <div class="card-content" id="card-content"></div>
</div>

<script>
const RAW_NODES = __NODES_JSON__;
const RAW_EDGES = __EDGES_JSON__;
const TYPE_COLORS = __TYPE_COLORS_JSON__;

// Starfield + nebula dust
(function() {
  const cv = document.getElementById('starfield');
  const ctx = cv.getContext('2d');
  const stars = [];
  const dust = [];
  function resize() { cv.width = innerWidth; cv.height = innerHeight; }
  resize(); window.addEventListener('resize', resize);
  // Tiny twinkling stars
  for (let i = 0; i < 160; i++) stars.push({
    x: Math.random(), y: Math.random(),
    r: Math.random() * 0.8 + 0.15,
    a: Math.random(), da: (Math.random() - 0.5) * 0.003
  });
  // Slow nebula dust blobs — lavanda and glacier
  for (let i = 0; i < 22; i++) dust.push({
    x: Math.random(), y: Math.random(),
    r: Math.random() * 80 + 25,
    a: Math.random() * 0.035 + 0.005,
    da: (Math.random()-0.5)*0.00025,
    vx: (Math.random()-0.5)*0.000055,
    vy: (Math.random()-0.5)*0.000055,
    hue: Math.random() > 0.55 ? '192,132,252' : '103,232,249'
  });
  (function draw() {
    ctx.clearRect(0, 0, cv.width, cv.height);
    // Draw dust first (back)
    for (const d of dust) {
      d.x = ((d.x + d.vx) % 1 + 1) % 1;
      d.y = ((d.y + d.vy) % 1 + 1) % 1;
      d.a = Math.max(0.004, Math.min(0.05, d.a + d.da));
      if (d.a <= 0.004 || d.a >= 0.05) d.da *= -1;
      const g = ctx.createRadialGradient(d.x*cv.width, d.y*cv.height, 0, d.x*cv.width, d.y*cv.height, d.r);
      g.addColorStop(0, 'rgba('+d.hue+','+d.a+')');
      g.addColorStop(1, 'rgba('+d.hue+',0)');
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(d.x*cv.width, d.y*cv.height, d.r, 0, 2*Math.PI); ctx.fill();
    }
    // Stars
    for (const s of stars) {
      s.a = Math.max(0.04, Math.min(0.85, s.a + s.da));
      if (s.a <= 0.04 || s.a >= 0.85) s.da *= -1;
      ctx.beginPath();
      ctx.arc(s.x * cv.width, s.y * cv.height, s.r, 0, 2 * Math.PI);
      ctx.fillStyle = 'rgba(210,210,255,' + s.a + ')';
      ctx.fill();
    }
    requestAnimationFrame(draw);
  })();
})();

const nodeMap = new Map(RAW_NODES.map(n => [n.id, n]));
let activeTypes = new Set(RAW_NODES.map(n => n.mtype));
let minImp = 1;
let minSimilarity = 0.70;
let searchHighlight = null; // Set of node ids matching current search

function buildGraphData() {
  const ns = RAW_NODES.filter(n => activeTypes.has(n.mtype) && n.importance >= minImp);
  const ids = new Set(ns.map(n => n.id));
  const es = RAW_EDGES.filter(e => ids.has(e.source) && ids.has(e.target) && e.similarity >= minSimilarity);
  return { nodes: ns.map(n => Object.assign({}, n)), links: es.map(e => Object.assign({}, e)) };
}

const Graph = ForceGraph3D({ rendererConfig: { antialias: true, alpha: true } })(document.getElementById('graph-root'))
  .backgroundColor('#0c0c14')
  .nodeId('id')
  .nodeLabel(() => '')
  .nodeColor(n => n.color)
  .nodeVal(n => 0.5 + n.importance * 0.8)
  .nodeOpacity(0.92)
  .nodeResolution(24)
  .nodeThreeObject(n => {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 128;
    const ctx = canvas.getContext('2d');
    const col = n.color || '#C084FC';
    // Parse hex→rgb for glass tints
    const r = parseInt(col.slice(1,3),16), g = parseInt(col.slice(3,5),16), b = parseInt(col.slice(5,7),16);
    // 1 — wide soft ambient halo
    const halo = ctx.createRadialGradient(64,64,18,64,64,64);
    halo.addColorStop(0, 'rgba('+r+','+g+','+b+',0.10)');
    halo.addColorStop(1, 'rgba('+r+','+g+','+b+',0)');
    ctx.fillStyle = halo; ctx.fillRect(0,0,128,128);
    // 2 — glass body (very translucent fill offset radial)
    const body = ctx.createRadialGradient(50,46,4,64,64,46);
    body.addColorStop(0,   'rgba(255,255,255,0.18)');
    body.addColorStop(0.45,'rgba('+r+','+g+','+b+',0.10)');
    body.addColorStop(1,   'rgba('+r+','+g+','+b+',0.02)');
    ctx.beginPath(); ctx.arc(64,64,46,0,2*Math.PI);
    ctx.fillStyle = body; ctx.fill();
    // 3 — colored rim ring
    ctx.beginPath(); ctx.arc(64,64,46,0,2*Math.PI);
    ctx.strokeStyle = 'rgba('+r+','+g+','+b+',0.55)';
    ctx.lineWidth = 1.2; ctx.stroke();
    // 4 — outer glow ring (faint, wider)
    ctx.beginPath(); ctx.arc(64,64,55,0,2*Math.PI);
    ctx.strokeStyle = 'rgba('+r+','+g+','+b+',0.12)';
    ctx.lineWidth = 2.5; ctx.stroke();
    // 5 — top-left specular blotch
    const spec = ctx.createRadialGradient(44,41,0,44,41,16);
    spec.addColorStop(0,'rgba(255,255,255,0.60)');
    spec.addColorStop(1,'rgba(255,255,255,0)');
    ctx.beginPath(); ctx.arc(44,41,16,0,2*Math.PI);
    ctx.fillStyle = spec; ctx.fill();
    // 6 — tiny hard specular dot
    ctx.beginPath(); ctx.arc(40,38,3.5,0,2*Math.PI);
    ctx.fillStyle = 'rgba(255,255,255,0.88)'; ctx.fill();
    const tex = new THREE.CanvasTexture(canvas);
    const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false });
    const sp  = new THREE.Sprite(mat);
    const s = 3.5 + n.importance * 1.5;
    sp.scale.set(s, s, 1);
    n.__sprite = sp;   // store ref for direct material manipulation
    return sp;
  })
  .nodeThreeObjectExtend(false)
  .linkSource('source').linkTarget('target')
  .linkColor(l => {
    const t = Math.min(1, Math.max(0, (l.similarity - 0.70) / 0.25));
    // gradient: glacier (#67E8F9) at low sim, lavanda (#C084FC) at high sim
    const ri = Math.round(103 + t * (192-103));
    const gi = Math.round(232 + t * (132-232));
    const bi = Math.round(249 + t * (252-249));
    return 'rgba('+ri+','+gi+','+bi+','+(0.08+t*0.45).toFixed(2)+')';
  })
  .linkWidth(l => 0.25 + (l.similarity - 0.70) * 4)
  .linkOpacity(0.55)
  .linkDirectionalParticles(l => l.similarity > 0.84 ? 2 : 0)
  .linkDirectionalParticleWidth(1.0)
  .linkDirectionalParticleColor(() => '#C084FC')
  .linkDirectionalParticleSpeed(0.003)
  .onNodeClick(node => {
    if (!node) return;
    const x = node.x||0, y = node.y||0, z = node.z||0, d = 60;
    Graph.cameraPosition({ x: x+d, y: y+d/2, z: z+d }, { x, y, z }, 800);
    showCard(node);
  })
  .onBackgroundClick(() => { document.getElementById('info-card').style.display = 'none'; })
  .onNodeHover(node => {
    const tip = document.getElementById('tooltip');
    if (!node) { tip.style.display = 'none'; return; }
    const d = nodeMap.get(node.id) || node;
    const preview = (d.content || '').slice(0, 90) + ((d.content||'').length > 90 ? '\u2026' : '');
    tip.innerHTML = '<strong style="color:' + (d.color||'#00b4d8') + '">' + (d.mtype||'') + '</strong>' +
      '  <span style="color:#6a80a7;font-size:10px">imp ' + (d.importance||0) + '/10</span>' +
      (preview ? '<br><span style="color:#ccd6f6">' + preview + '</span>' : '');
    tip.style.display = 'block';
  });

document.addEventListener('mousemove', e => {
  const tip = document.getElementById('tooltip');
  if (tip.style.display !== 'none') {
    tip.style.left = Math.min(e.clientX + 16, innerWidth - 280) + 'px';
    tip.style.top  = (e.clientY - 10) + 'px';
  }
});

function refresh() {
  const data = buildGraphData();
  Graph.graphData(data);
  document.getElementById('hud-stats').textContent =
    data.nodes.length.toLocaleString() + ' neurons  \u00b7  ' + data.links.length.toLocaleString() + ' synapses';
}
refresh();

// Bloom post-processing
setTimeout(() => {
  try {
    const renderer = Graph.renderer();
    const scene    = Graph.scene();
    const composer = new THREE.EffectComposer(renderer);
    composer.addPass(new THREE.RenderPass(scene, Graph.camera()));
    const bloom = new THREE.UnrealBloomPass(
      new THREE.Vector2(innerWidth, innerHeight),
      1.1,   // strength — softer for glass look
      0.75,  // radius — wider spread
      0.08   // threshold
    );
    composer.addPass(bloom);
    window._bloomPass = bloom;  // expose for SSE animations
    // Intercept 3d-force-graph's per-frame render call
    const _orig = renderer.render.bind(renderer);
    function _intercept(s, c) {
      if (s === scene) {
        renderer.render = _orig;
        composer.render();
        renderer.render = _intercept;
      } else { _orig(s, c); }
    }
    renderer.render = _intercept;
    window.addEventListener('resize', () => composer.setSize(innerWidth, innerHeight));
  } catch(e) { console.warn('Bloom init failed:', e); }
}, 400);

// Idle orbit
let lastInteraction = Date.now(), angle = 0;
Graph.controls().addEventListener('start', () => { lastInteraction = Date.now(); });
setInterval(() => {
  if (Date.now() - lastInteraction > 6000) {
    angle += 0.003;
    const r = Graph.camera().position.length() || 400;
    Graph.cameraPosition({ x: r*Math.sin(angle), y: 0, z: r*Math.cos(angle) }, { x:0,y:0,z:0 }, 50);
  }
}, 50);

function showCard(node) {
  const d = nodeMap.get(node.id) || node;
  const imp = d.importance || 0;
  document.getElementById('card-type').textContent = d.mtype || '';
  document.getElementById('card-type').style.color  = d.color || '#00b4d8';
  document.getElementById('card-imp').innerHTML =
    '<span class="imp-stars">' + '\u2605'.repeat(imp) + '\u2606'.repeat(Math.max(0,10-imp)) + '</span>  importance ' + imp + '/10  \u00b7  ' + (d.created||'');
  document.getElementById('card-tags').innerHTML = (d.tags||[]).map(t => '<span class="tag">'+t+'</span>').join('');
  document.getElementById('card-content').textContent = d.content || '';
  document.getElementById('info-card').style.display = 'block';
}
document.getElementById('info-close').addEventListener('click', () => {
  document.getElementById('info-card').style.display = 'none';
});

// Panel toggle with slide+blur effect
const panel = document.getElementById('panel');
document.getElementById('panel-toggle').addEventListener('click', () => {
  const inner = document.getElementById('panel-inner');
  inner.style.filter = 'blur(5px)';
  panel.classList.toggle('collapsed');
  document.getElementById('panel-toggle').textContent = panel.classList.contains('collapsed') ? '\u25b6' : '\u25c4';
  setTimeout(() => { inner.style.filter = ''; }, 400);
});

// Legend
const legendEl = document.getElementById('legend');
const typeCounts = {};
RAW_NODES.forEach(n => { typeCounts[n.mtype] = (typeCounts[n.mtype]||0)+1; });
const seenTypes = Object.keys(typeCounts).sort((a,b) => typeCounts[b]-typeCounts[a]);
seenTypes.forEach(t => {
  const col = TYPE_COLORS[t] || '#607d8b';
  const row = document.createElement('div');
  row.className = 'leg-row'; row.dataset.type = t;
  row.innerHTML = '<span class="leg-dot" style="background:'+col+'"></span><span>'+t+'</span><span class="leg-count">'+typeCounts[t]+'</span>';
  row.addEventListener('click', () => {
    if (activeTypes.has(t)) activeTypes.delete(t); else activeTypes.add(t);
    row.classList.toggle('inactive', !activeTypes.has(t));
    refresh();
  });
  legendEl.appendChild(row);
});

const typeFilter = document.getElementById('typeFilter');
seenTypes.forEach(t => {
  const opt = document.createElement('option'); opt.value = t; opt.textContent = t;
  typeFilter.appendChild(opt);
});
typeFilter.addEventListener('change', () => {
  const v = typeFilter.value;
  if (!v) { activeTypes = new Set(seenTypes); legendEl.querySelectorAll('.leg-row').forEach(r => r.classList.remove('inactive')); }
  else { activeTypes = new Set([v]); legendEl.querySelectorAll('.leg-row').forEach(r => r.classList.toggle('inactive', r.dataset.type !== v)); }
  refresh();
});

// Sliders
const impSlider = document.getElementById('impSlider');
impSlider.addEventListener('input', () => {
  minImp = parseInt(impSlider.value);
  document.getElementById('impVal').textContent = minImp;
  impSlider.style.setProperty('--pct', ((minImp-1)/9*100)+'%');
  refresh();
});
// Search
document.getElementById('search').addEventListener('input', function() {
  const q = this.value.trim().toLowerCase();
  if (!q) {
    searchHighlight = null;
    Graph.nodeColor(n => n.color);
    return;
  }
  searchHighlight = new Set(
    RAW_NODES
      .filter(n =>
        (n.content||'').toLowerCase().includes(q) ||
        (n.tags||[]).some(t => t.toLowerCase().includes(q)) ||
        (n.mtype||'').toLowerCase().includes(q)
      )
      .map(n => n.id)
  );
  Graph.nodeColor(n => searchHighlight.has(n.id) ? '#ffffff' : (n.color + '22'));
  // Fly to highest-importance match visible in current graph
  const visIds = new Set(Graph.graphData().nodes.map(n => n.id));
  const hit = Graph.graphData().nodes.find(n => searchHighlight.has(n.id) && n.x != null);
  if (hit) {
    const d = 70;
    Graph.cameraPosition({ x: hit.x+d, y: hit.y+d/2, z: hit.z+d }, { x: hit.x, y: hit.y, z: hit.z }, 900);
  }
  document.getElementById('hud-stats').textContent =
    searchHighlight.size + ' match' + (searchHighlight.size !== 1 ? 'es' : '') + ' for \u201c' + q + '\u201d';
});

// Similarity threshold
document.getElementById('simSlider').addEventListener('input', function() {
  const v = parseFloat(this.value);
  document.getElementById('simVal').textContent = v.toFixed(2);
  this.style.setProperty('--pct', ((v - +this.min) / (+this.max - +this.min) * 100) + '%');
  minSimilarity = v;
  refresh();
});

document.getElementById('repSlider').addEventListener('input', function() {
  const v = parseFloat(this.value);
  document.getElementById('repVal').textContent = v.toFixed(1);
  this.style.setProperty('--pct', ((v-+this.min)/(+this.max-+this.min)*100)+'%');
  Graph.d3Force('charge') && Graph.d3Force('charge').strength(-v*60);
  Graph.d3ReheatSimulation();
});
document.getElementById('springSlider').addEventListener('input', function() {
  const v = parseFloat(this.value);
  document.getElementById('springVal').textContent = v.toFixed(2);
  this.style.setProperty('--pct', ((v-+this.min)/(+this.max-+this.min)*100)+'%');
  Graph.d3Force('link') && Graph.d3Force('link').strength(v);
  Graph.d3ReheatSimulation();
});

// ── Real-time SSE feed ────────────────────────────────────────────────────
(function initSSE() {
  const SSE_URL = 'http://127.0.0.1:11434/events';
  const LIVE_DOT = document.getElementById('hud-pulse');

  // Toast container
  const toast = document.createElement('div');
  toast.style.cssText = 'position:fixed;bottom:22px;left:50%;transform:translateX(-50%);z-index:999;' +
    'display:flex;flex-direction:column;align-items:center;gap:8px;pointer-events:none';
  document.body.appendChild(toast);

  function showToast(msg, color, icon) {
    const el = document.createElement('div');
    el.textContent = (icon ? icon + ' ' : '') + msg;
    el.style.cssText = 'background:rgba(3,5,13,.92);border:1px solid '+color+';color:'+color+
      ';font-size:12px;padding:6px 16px;border-radius:20px;letter-spacing:.4px;opacity:1;' +
      'transition:opacity 1.5s ease;backdrop-filter:blur(8px)';
    toast.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 1500); }, 2500);
  }

  // ── Roleplay persistent glow state ────────────────────────────────────
  let _roleplayGlowFrame = null;
  const _rpCol1 = new THREE.Color('#f06292');
  const _rpCol2 = new THREE.Color('#ce93d8');
  const _rpWhite = new THREE.Color('#ffffff');

  function startRoleplayGlow() {
    if (_roleplayGlowFrame) return;
    function loop() {
      const t = (Math.sin(Date.now() * 0.0025) + 1) / 2;
      const col = _rpCol1.clone().lerp(_rpCol2, t);
      try {
        Graph.graphData().nodes.forEach(n => {
          if (n.mtype === 'roleplay' && n.__sprite) n.__sprite.material.color.copy(col);
        });
      } catch(e) {}
      _roleplayGlowFrame = requestAnimationFrame(loop);
    }
    _roleplayGlowFrame = requestAnimationFrame(loop);
  }

  function stopRoleplayGlow() {
    if (_roleplayGlowFrame) { cancelAnimationFrame(_roleplayGlowFrame); _roleplayGlowFrame = null; }
    try {
      Graph.graphData().nodes.forEach(n => {
        if (n.mtype === 'roleplay' && n.__sprite) n.__sprite.material.color.copy(_rpWhite);
      });
    } catch(e) {}
  }

  // ── Insight supernova animation ────────────────────────────────────────
  function supernovaFlash(node) {
    if (!node) return;
    const scene = Graph.scene();
    const ox = node.x || 0, oy = node.y || 0, oz = node.z || 0;

    // Flash sprite to gold, then restore
    if (node.__sprite) {
      node.__sprite.material.color.set('#ffd166');
      setTimeout(() => {
        if (node.__sprite) node.__sprite.material.color.set('#ffffff');
      }, 1400);
    }

    // 3 expanding light-ring waves with staggered delays
    const ringColors = [0xffd166, 0xffb703, 0xff9f1c];
    for (let i = 0; i < 3; i++) {
      setTimeout(() => {
        const ring = new THREE.Mesh(
          new THREE.RingGeometry(0.1, 0.6, 48),
          new THREE.MeshBasicMaterial({
            color: ringColors[i], transparent: true, opacity: 0.75,
            side: THREE.DoubleSide, depthWrite: false
          })
        );
        ring.position.set(ox, oy, oz);
        // Tilt each ring slightly differently for a 3D burst feel
        ring.rotation.x = Math.PI / 2 + i * 0.4;
        ring.rotation.z = i * Math.PI / 3;
        scene.add(ring);
        const start = Date.now();
        const maxScale = 14 + i * 7;
        const dur = 1100 + i * 150;
        (function expand() {
          const t = (Date.now() - start) / dur;
          if (t >= 1) {
            scene.remove(ring);
            ring.geometry.dispose(); ring.material.dispose();
            return;
          }
          const eased = 1 - Math.pow(1 - t, 2);
          ring.scale.setScalar(1 + eased * maxScale);
          ring.material.opacity = 0.75 * (1 - t);
          requestAnimationFrame(expand);
        })();
      }, i * 180);
    }

    // Radial particle burst — 12 small glowing dots shot outward
    const particleCount = 12;
    for (let p = 0; p < particleCount; p++) {
      const angle  = (p / particleCount) * Math.PI * 2;
      const phi    = (Math.random() - 0.5) * Math.PI;
      const dir    = new THREE.Vector3(
        Math.cos(angle) * Math.cos(phi),
        Math.sin(phi),
        Math.sin(angle) * Math.cos(phi)
      );
      const geo = new THREE.SphereGeometry(0.35, 6, 6);
      const mat = new THREE.MeshBasicMaterial({
        color: p % 2 === 0 ? 0xffd166 : 0xffffff,
        transparent: true, opacity: 0.9
      });
      const dot = new THREE.Mesh(geo, mat);
      dot.position.set(ox, oy, oz);
      scene.add(dot);
      const start = Date.now();
      const speed = 18 + Math.random() * 10;
      (function fly() {
        const t = (Date.now() - start) / 900;
        if (t >= 1) {
          scene.remove(dot); geo.dispose(); mat.dispose(); return;
        }
        const eased = 1 - Math.pow(1 - t, 3);
        dot.position.set(ox + dir.x * eased * speed, oy + dir.y * eased * speed, oz + dir.z * eased * speed);
        mat.opacity = 0.9 * (1 - t * t);
        requestAnimationFrame(fly);
      })();
    }

    // Bloom strength spike
    if (window._bloomPass) {
      window._bloomPass.strength = 2.8;
      const step = () => {
        window._bloomPass.strength = Math.max(1.4, window._bloomPass.strength - 0.07);
        if (window._bloomPass.strength > 1.4) requestAnimationFrame(step);
      };
      setTimeout(() => requestAnimationFrame(step), 300);
    }
  }

  // ── Standard flash (non-insight) ──────────────────────────────────────
  function flashNode(nodeId, flashColor) {
    if (!nodeId) return;
    const node = Graph.graphData().nodes.find(n => n.id === nodeId);
    if (!node) return;
    if (node.__sprite) {
      node.__sprite.material.color.set(flashColor);
      setTimeout(() => { if (node.__sprite) node.__sprite.material.color.set('#ffffff'); }, 1800);
    }
  }

  function highlightNodes(ids, flashColor) {
    if (!ids || !ids.length) return;
    const idSet = new Set(ids);
    const col = new THREE.Color(flashColor);
    const white = new THREE.Color('#ffffff');
    Graph.graphData().nodes.forEach(n => {
      if (idSet.has(n.id) && n.__sprite) n.__sprite.material.color.copy(col);
    });
    setTimeout(() => {
      Graph.graphData().nodes.forEach(n => {
        if (idSet.has(n.id) && n.__sprite) n.__sprite.material.color.copy(white);
      });
    }, 2000);
  }

  function addNodeLive(evt) {
    const typeColors = __TYPE_COLORS_JSON__;
    const color = typeColors[evt.memory_type] || '#607d8b';
    const newNode = {
      id:         evt.id || ('live-' + Date.now()),
      mtype:      evt.memory_type || 'fact',
      importance: evt.importance || 5,
      color:      color,
      label:      (evt.content || '').substring(0, 60) + (evt.content && evt.content.length > 60 ? '\u2026' : ''),
      tags:       evt.tags || [],
    };
    const { nodes, links } = Graph.graphData();
    nodes.push(newNode);
    Graph.graphData({ nodes, links });

    // Glass materialize from depth: scale 0 → targetScale over 900ms with spring easing
    setTimeout(() => {
      const live = Graph.graphData().nodes.find(n => n.id === newNode.id);
      if (!live || !live.__sprite) return;
      const targetS = 3.5 + (live.importance || 5) * 1.5;
      live.__sprite.scale.set(0.01, 0.01, 1);
      const start = Date.now();
      const dur = 900;
      (function anim() {
        const t = Math.min(1, (Date.now()-start)/dur);
        // spring-like ease: bounces slightly at the end
        const freq = 2.8, decay = 4;
        const ease = 1 - Math.exp(-decay*t) * Math.cos(freq*Math.PI*t);
        const s = Math.max(0.01, targetS * ease);
        live.__sprite.scale.set(s, s, 1);
        if (t < 1) requestAnimationFrame(anim);
      })();
    }, 80);
  }

  // Spotlight from above — for memories_searched in Glass style
  function spotlightNodes(ids) {
    const scene = Graph.scene();
    const idSet = new Set(ids);
    Graph.graphData().nodes.forEach(n => {
      if (!idSet.has(n.id)) return;
      const x = n.x||0, y = n.y||0, z = n.z||0;
      const light = new THREE.PointLight(0x67E8F9, 0, 120);
      light.position.set(x, y + 55, z + 8);
      scene.add(light);
      const start = Date.now();
      (function fade() {
        const t = (Date.now()-start)/2800;
        if (t >= 1) { scene.remove(light); return; }
        // fade curve: quick in, slow out
        light.intensity = (t < 0.25 ? t/0.25 : 1 - (t-0.25)/0.75) * 3.5;
        requestAnimationFrame(fade);
      })();
    });
  }

  // Synaptic luminous trace along an edge: source → target glowing dot with trail
  function synapticTrace(sourceId, relatedIds) {
    if (!relatedIds || !relatedIds.length) return;
    const scene = Graph.scene();
    const source = Graph.graphData().nodes.find(n => n.id === sourceId);
    if (!source) return;
    relatedIds.slice(0, 6).forEach((targetId, idx) => {
      setTimeout(() => {
        const target = Graph.graphData().nodes.find(n => n.id === targetId);
        if (!target) return;
        const sx = source.x||0, sy = source.y||0, sz = source.z||0;
        const tx = target.x||0, ty = target.y||0, tz = target.z||0;
        // Glowing tracer sphere
        const geo = new THREE.SphereGeometry(0.7, 8, 8);
        const mat = new THREE.MeshBasicMaterial({ color: 0xC084FC, transparent: true, opacity: 0.9 });
        const dot = new THREE.Mesh(geo, mat);
        scene.add(dot);
        // Trail: a few fading ghost copies
        const trailCount = 5;
        const trail = Array.from({length: trailCount}, () => {
          const tg = new THREE.SphereGeometry(0.5, 6, 6);
          const tm = new THREE.MeshBasicMaterial({ color: 0xa855f7, transparent: true, opacity: 0 });
          const td = new THREE.Mesh(tg, tm);
          scene.add(td);
          return td;
        });
        const start = Date.now();
        const dur = 700 + idx * 60;
        (function travel() {
          const t = Math.min(1, (Date.now()-start)/dur);
          const ease = t < 0.5 ? 2*t*t : 1-Math.pow(-2*t+2,2)/2;  // ease-in-out quad
          dot.position.set(sx+(tx-sx)*ease, sy+(ty-sy)*ease, sz+(tz-sz)*ease);
          // trail lags behind
          for (let i = 0; i < trailCount; i++) {
            const tb = Math.max(0, ease - (i+1)*0.08);
            trail[i].position.set(sx+(tx-sx)*tb, sy+(ty-sy)*tb, sz+(tz-sz)*tb);
            trail[i].material.opacity = (1 - i/trailCount) * 0.35 * (1-t);
          }
          mat.opacity = 0.9 * (1-t*0.5);
          if (t < 1) { requestAnimationFrame(travel); }
          else {
            scene.remove(dot); geo.dispose(); mat.dispose();
            trail.forEach(td => { scene.remove(td); td.geometry.dispose(); td.material.dispose(); });
          }
        })();
      }, idx * 120);
    });
  }

  function connectSSE() {
    const es = new EventSource(SSE_URL);

    es.addEventListener('open', () => {
      LIVE_DOT.style.background = '#06d6a0';
      LIVE_DOT.title = 'Live \u2014 NEMO connected';
    });

    es.addEventListener('message', e => {
      let evt;
      try { evt = JSON.parse(e.data); } catch { return; }
      if (evt.type === 'connected') return;

      if (evt.type === 'memory_created') {
        addNodeLive(evt);
        const isInsight = evt.memory_type === 'insight';
        if (isInsight) {
          showToast('Insight: ' + (evt.content || '').substring(0, 40), '#ffd166', '\u2605');
          setTimeout(() => {
            const node = Graph.graphData().nodes.find(n => n.id === evt.id);
            if (node) supernovaFlash(node);
          }, 120);
        } else {
          showToast('Memory: ' + (evt.content || '').substring(0, 40), '#C084FC', '\u2736');
          // Note: materialize animation is inside addNodeLive now
        }

      } else if (evt.type === 'memories_searched') {
        // Glass: spotlight from above instead of color flash
        spotlightNodes(evt.hit_ids);
        highlightNodes(evt.hit_ids, '#67E8F9');
        showToast('Search: "' + (evt.query || '').substring(0, 40) + '" \u2192 ' + evt.count + ' hits', '#67E8F9', '\u2315');

      } else if (evt.type === 'context_primed') {
        highlightNodes(evt.memory_ids, '#C084FC');
        showToast('Context primed \u2014 ' + evt.count + ' memories activated', '#C084FC', '\u25ce');

      } else if (evt.type === 'synaptic_tagged') {
        flashNode(evt.memory_id, '#a855f7');
        // Glass: luminous trace along edges to related nodes
        if (evt.related_ids && evt.related_ids.length) {
          synapticTrace(evt.memory_id, evt.related_ids);
        }
        showToast('Synaptic tagging \u2014 ' + evt.related_count + ' connections', '#a855f7', '\u29d7');

      } else if (evt.type === 'conversation_stored') {
        showToast('Conversation stored: ' + (evt.title || ''), '#67E8F9', '\u25d1');

      } else if (evt.type === 'character_active') {
        startRoleplayGlow();
        showToast('Character active: ' + (evt.character_name || ''), '#f06292', '\ud83c\udfad');
        if (evt.memory_ids && evt.memory_ids.length) highlightNodes(evt.memory_ids, '#f06292');

      } else if (evt.type === 'roleplay_stored') {
        addNodeLive(evt);
        showToast('Roleplay stored: ' + (evt.character_name || ''), '#ce93d8', '\ud83c\udfad');
        setTimeout(() => { flashNode(evt.id, '#f06292'); }, 120);

      } else if (evt.type === 'character_session_ended') {
        stopRoleplayGlow();
        showToast('Character session ended', '#9e9e9e', '\ud83c\udfad');
      }
    });

    es.addEventListener('error', () => {
      LIVE_DOT.style.background = '#ff4757';
      LIVE_DOT.title = 'Offline \u2014 reconnecting\u2026';
      es.close();
      setTimeout(connectSSE, 5000);
    });
  }

  connectSSE();
})();
// ── end SSE ───────────────────────────────────────────────────────────────
</script>
</body>
</html>"""


def generate_html(nodes: list, edges: list, out_path: str):
    html = HTML_TEMPLATE
    html = html.replace("__NODES_JSON__", __import__("json").dumps(nodes, ensure_ascii=False))
    html = html.replace("__EDGES_JSON__", __import__("json").dumps(edges, ensure_ascii=False))
    html = html.replace("__TYPE_COLORS_JSON__", __import__("json").dumps(TYPE_COLORS, ensure_ascii=False))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


def find_db() -> str:
    import os
    from pathlib import Path
    data_dir = os.environ.get("AI_MEMORY_DATA_DIR")
    if data_dir:
        candidates = list(Path(data_dir).glob("*.db"))
        if candidates:
            return str(candidates[0])
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
    import argparse, webbrowser
    parser = argparse.ArgumentParser(description="Generate NEMO memory graph dashboard")
    parser.add_argument("--db",        default=None)
    parser.add_argument("--limit",     type=int,   default=300)
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--out",       default="dashboard.html")
    parser.add_argument("--no-open",   action="store_true")
    args = parser.parse_args()

    db_path = args.db or find_db()
    print(f"[NEMO Dashboard] DB: {db_path}")

    rows = load_memories(db_path, args.limit)
    print(f"[NEMO Dashboard] Loaded {len(rows)} memories")

    nodes, edges = build_graph(rows, args.threshold)
    print(f"[NEMO Dashboard] Graph: {len(nodes)} nodes, {len(edges)} edges (threshold={args.threshold})")

    out = args.out
    generate_html(nodes, edges, out)
    print(f"[NEMO Dashboard] Generated: {__import__('os').path.abspath(out)}")

    if not args.no_open:
        webbrowser.open(f"file:///{__import__('os').path.abspath(out).replace(chr(92), '/')}")
        print("[NEMO Dashboard] Opened in browser")


if __name__ == "__main__":
    main()
