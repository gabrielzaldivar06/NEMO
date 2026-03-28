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
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NEMO · Neural Memory Graph</title>
<!-- Real premium fonts from Google Fonts CDN -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300&display=swap" rel="stylesheet">
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
    /* Premium font stack */
    --font-ui:   'Space Grotesk', 'SF Pro Display', system-ui, sans-serif;
    --font-mono: 'DM Mono', 'SF Mono', 'Fira Code', monospace;
  }

  /* SVG grain noise — gives frosted-glass texture to panels */
  @keyframes grain {
    0%,100%  { transform: translate(0,0); }
    10%      { transform: translate(-2%,-3%); }
    20%      { transform: translate(3%, 1%); }
    30%      { transform: translate(-1%, 4%); }
    40%      { transform: translate(2%,-2%); }
    50%      { transform: translate(-3%, 3%); }
    60%      { transform: translate(1%,-4%); }
    70%      { transform: translate(-2%, 2%); }
    80%      { transform: translate(4%,-1%); }
    90%      { transform: translate(-1%,-2%); }
  }
  #grain {
    position: fixed; inset: -50%; z-index: 100; width: 200%; height: 200%;
    pointer-events: none;
    opacity: 0.032;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 512 512' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
    animation: grain 0.4s steps(1) infinite;
    mix-blend-mode: overlay;
  }

  html, body {
    width: 100%; height: 100%;
    background:
      radial-gradient(ellipse 90% 70% at 20% 15%, #1a1a3e 0%, transparent 55%),
      radial-gradient(ellipse 70% 55% at 80% 80%, #0d0d2a 0%, transparent 55%),
      radial-gradient(ellipse 50% 80% at 50% 100%, #110d1e 0%, transparent 60%),
      #0c0c14;
    color: var(--text);
    font-family: var(--font-ui);
    overflow: hidden;
    /* Custom crosshair cursor */
    cursor: none;
  }

  /* Custom minimal cursor */
  #cursor-dot {
    position: fixed; z-index: 9999; pointer-events: none;
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--accent);
    transform: translate(-50%,-50%);
    transition: width 0.15s, height 0.15s, opacity 0.15s;
    box-shadow: 0 0 10px var(--accent), 0 0 24px rgba(192,132,252,0.5);
    mix-blend-mode: screen;
  }
  #cursor-ring {
    position: fixed; z-index: 9998; pointer-events: none;
    width: 28px; height: 28px; border-radius: 50%;
    border: 0.5px solid rgba(192,132,252,0.5);
    transform: translate(-50%,-50%);
    transition: width 0.35s cubic-bezier(0.34,1.56,0.64,1), height 0.35s cubic-bezier(0.34,1.56,0.64,1), opacity 0.2s;
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
    padding: 10px 22px;
    background: rgba(12,12,20,0.60);
    backdrop-filter: blur(28px) saturate(180%);
    -webkit-backdrop-filter: blur(28px) saturate(180%);
    border-bottom: 0.5px solid rgba(255,255,255,0.08);
    box-shadow: 0 1px 0 rgba(192,132,252,0.08);
    animation: slideDown 0.5s ease;
  }
  /* Scanline shimmer effect on HUD */
  #hud::after {
    content: ''; position: absolute; left: 0; right: 0; top: 0; bottom: 0;
    background: repeating-linear-gradient(
      0deg,
      transparent,
      transparent 3px,
      rgba(255,255,255,0.012) 3px,
      rgba(255,255,255,0.012) 4px
    );
    pointer-events: none; z-index: 1;
  }
  @keyframes slideDown { from { transform: translateY(-100%); opacity:0; } to { transform: none; opacity:1; } }
  #hud-title {
    font-size: 15px; font-weight: 600; letter-spacing: 3px;
    font-family: var(--font-ui);
    background: linear-gradient(90deg, #C084FC 0%, #a78bfa 40%, #67E8F9 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    text-transform: uppercase;
  }
  /* Version badge */
  #hud-badge {
    font-family: var(--font-mono); font-size: 9px; letter-spacing: 1px;
    padding: 2px 8px; border-radius: 20px;
    border: 0.5px solid rgba(192,132,252,0.35);
    color: rgba(192,132,252,0.7);
    background: rgba(192,132,252,0.06);
    text-transform: uppercase; flex-shrink: 0;
    box-shadow: 0 0 10px rgba(192,132,252,0.15), inset 0 0 0 0.5px rgba(192,132,252,0.12);
  }
  #hud-stats { font-size: 11px; color: var(--muted); letter-spacing: 0.5px; font-family: var(--font-mono); }
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

  /* Legend */
  .leg-row {
    display: flex; align-items: center; gap: 8px;
    padding: 5px 6px; font-size: 12px; cursor: pointer;
    border-radius: 4px; transition: background 0.15s;
  }
  .leg-row:hover { background: rgba(192,132,252,0.06); }
  .leg-row:hover .leg-dot { opacity: 1; filter: brightness(1.3); }
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
  .ctrl-val { min-width: 26px; text-align: right; color: var(--accent); font-weight: 500; font-family: var(--font-mono); font-size: 11px; }
  select {
    background: rgba(0,0,0,0.4); color: var(--text); border: 1px solid var(--border);
    border-radius: 5px; padding: 4px 8px; font-size: 12px; width: 100%;
  }
  select option { background: #0d1117; }

  /* Info card */
  /* Info card with animated gradient border */
  #info-card {
    position: fixed; bottom: 24px; left: 24px;
    width: 360px; max-height: 260px; z-index: 20;
    background: rgba(14,12,28,0.82);
    backdrop-filter: blur(32px) saturate(160%);
    -webkit-backdrop-filter: blur(32px) saturate(160%);
    /* multi-layer box-shadow for depth */
    box-shadow:
      0 2px 4px rgba(0,0,0,0.4),
      0 8px 24px rgba(0,0,0,0.5),
      0 24px 64px rgba(0,0,0,0.3),
      inset 0 1px 0 rgba(255,255,255,0.07),
      0 0 0 0.5px rgba(192,132,252,0.15);
    border-radius: 16px;
    padding: 16px 18px; overflow-y: auto; display: none;
    animation: cardIn 0.3s cubic-bezier(0.34,1.56,0.64,1);
    /* Corner bracket decoration via outline gradient */
    outline: none;
  }
  /* Animated gradient border on info card */
  @keyframes borderSpin {
    from { --border-angle: 0turn; }
    to   { --border-angle: 1turn; }
  }
  /* Corner brackets for premium feel — using ::before/::after on wrapper */
  #info-card-wrap {
    position: fixed; bottom: 24px; left: 24px;
    width: 360px; z-index: 20;
    pointer-events: none;
  }
  @keyframes cardIn { from { opacity:0; transform: translateY(14px) scale(0.97); } to { opacity:1; transform: none; } }
  @keyframes cardIn { from { opacity:0; transform: translateY(12px); } to { opacity:1; transform: none; } }
  #info-card .card-type { font-size: 9px; letter-spacing: 3px; text-transform: uppercase; font-weight: 600; font-family: var(--font-mono); margin-bottom: 6px; }
  #info-card .card-imp  { font-size: 11px; color: var(--muted); margin-bottom: 8px; font-family: var(--font-mono); }
  #info-card .card-tags { display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 10px; }
  #info-card .tag { font-size: 10px; padding: 2px 8px; border-radius: 20px; background: rgba(192,132,252,0.08); border: 0.5px solid rgba(192,132,252,0.30); color: var(--accent); letter-spacing: 0.3px; }
  #info-card .card-content { font-size: 12px; line-height: 1.65; }
  #info-close { position: absolute; top: 10px; right: 12px; font-size: 16px; cursor: pointer; color: var(--muted); }
  #info-close:hover { color: var(--text); }
  .imp-stars { color: var(--accent2); letter-spacing: 1px; }

  /* Premium scrollbar */
  ::-webkit-scrollbar { width: 3px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(192,132,252,0.25); border-radius: 2px; }
  ::-webkit-scrollbar-thumb:hover { background: rgba(192,132,252,0.5); }

  /* Panel section heading uppercase mono */
  .panel-section h3 {
    font-size: 9px; font-weight: 500; letter-spacing: 2.5px;
    text-transform: uppercase; color: var(--muted);
    font-family: var(--font-mono);
    margin-bottom: 10px; padding-bottom: 6px;
    border-bottom: 0.5px solid var(--border);
  }

  /* Legend micro-glow on hover */
  .leg-row:hover { background: rgba(192,132,252,0.06); }
  .leg-row:hover .leg-dot { opacity: 1; filter: brightness(1.3); }

  /* Corner brackets on panel using CSS */
  #panel::before {
    content: '';
    position: absolute; top: 12px; left: 12px;
    width: 14px; height: 14px;
    border-top: 0.5px solid rgba(192,132,252,0.35);
    border-left: 0.5px solid rgba(192,132,252,0.35);
    pointer-events: none;
  }
  #panel::after {
    content: '';
    position: absolute; bottom: 12px; left: 12px;
    width: 14px; height: 14px;
    border-bottom: 0.5px solid rgba(192,132,252,0.35);
    border-left: 0.5px solid rgba(192,132,252,0.35);
    pointer-events: none;
  }
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

<div id="grain"></div>
<div id="cursor-dot"></div>
<div id="cursor-ring"></div>
<div id="nebula"></div>
<canvas id="starfield"></canvas>
<div id="graph-root"></div>

<div id="hud">
  <div id="hud-pulse"></div>
  <span id="hud-sse" style="font-size:9px;letter-spacing:.5px;opacity:.65;text-transform:uppercase;font-family:var(--font-mono)"></span>
  <span id="hud-title">&#11044;&nbsp; NEMO</span>
  <span id="hud-badge">v2.0 · live</span>
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

// ── Custom cursor ────────────────────────────────────────────────
(function() {
  const dot  = document.getElementById('cursor-dot');
  const ring = document.getElementById('cursor-ring');
  let mx = -100, my = -100, rx = -100, ry = -100;
  document.addEventListener('mousemove', e => { mx = e.clientX; my = e.clientY; });
  document.addEventListener('mousedown', () => { dot.style.transform = 'translate(-50%,-50%) scale(1.8)'; ring.style.transform = 'translate(-50%,-50%) scale(0.8)'; });
  document.addEventListener('mouseup',   () => { dot.style.transform = 'translate(-50%,-50%) scale(1)';   ring.style.transform = 'translate(-50%,-50%) scale(1)'; });
  function loop() {
    rx += (mx - rx) * 0.14; ry += (my - ry) * 0.14;
    dot.style.left  = mx + 'px'; dot.style.top  = my + 'px';
    ring.style.left = rx + 'px'; ring.style.top = ry + 'px';
    requestAnimationFrame(loop);
  }
  loop();
})();

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

// ── Game-icons.net SVG assets (base64, fill="FILL" placeholder) ──────────────
const ICON_B64 = {
  fact:       'PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA1MTIgNTEyIiBmaWxsPSJGSUxMIj48cGF0aCBkPSJNMTk2LjczIDM1LjIzYy04LjEzMi44NzgtMTYuMyAxLjkzNi0yNC41MTUgMy4xNzJDMTkyLjk2OCA1MC4yMSAyMTIuMDQ1IDY2Ljc5NSAyMjQgOTZjLTI0Ljg5Ni0yMi41MTItNDQuMjMyLTM5LjUtNzUuNzk1LTUzLjUxMmE2ODYuMjgzIDY4Ni4yODMgMCAwIDAtMjYuNjU2IDUuNjRjMjIuNjkgMTAuNzQ1IDQ5LjAyNiAyNi4wOTQgNzUuMTE0IDUxLjMwNi01Ny40NTYtMjUuNDU0LTgxLjc5Mi0zMS4wNjYtMTIwLjIzLTM5LjRBOTY1LjU2NCA5NjUuNTY0IDAgMCAwIDM5LjUgNzEuNzQzYzU0LjgxMyAzLjUzMiAxMDMuMTI3IDE5LjY0NCAxODcuMzQ2IDQ3LjcxN2wyLjAxNS42NzMgMS41MDMgMS41MDRjNS43OTQgNS43OTMgMTUuMzU2IDkuMjU0IDI1LjIwMyA5LjM1My0yLjcyNS0zOS40My0xOC43ODctNjcuODAyLTU4LjgzNi05NS43NnptMTE4LjU0IDBjLTQwLjA1IDI3Ljk1OC01Ni4xMSA1Ni4zMy01OC44MzYgOTUuNzYgOS44NDctLjEgMTkuNDEtMy41NiAyNS4yMDMtOS4zNTNsMS41MDItMS41MDQgMi4wMTQtLjY3MkMzNjkuMzc0IDkxLjM5IDQxNy42ODcgNzUuMjc3IDQ3Mi41IDcxLjc0NWE5NjYuODYgOTY2Ljg2IDAgMCAwLTM2LjkzNC0xMS43MWMtMzguNDM4IDguMzM0LTYyLjc3NCAxMy45NDYtMTIwLjIzIDM5LjQgMjYuMDg4LTI1LjIxMiA1Mi40MjQtNDAuNTYgNzUuMTE1LTUxLjMwN2E2ODkuMTg2IDY4OS4xODYgMCAwIDAtMjYuNjU1LTUuNjRjLTMxLjU2MyAxNC4wMTQtNTAuOSAzMS03NS43OTUgNTMuNTEzIDExLjk1NC0yOS4yMDUgMzEuMDMyLTQ1Ljc5IDUxLjc4NS01Ny41OThhNTkxLjcwNSA1OTEuNzA1IDAgMCAwLTI0LjUxNS0zLjE3MnpNMjUgODkuMjg3djMwMS43NThjNDQuNjguMTkgMTA2LjAxIDE2LjgxMyAxOTAgNDQuNDk4di0zMDEuMDRDMTI4LjAzNCAxMDUuNTM0IDgxLjY3IDkwLjcxIDI1IDg5LjI4OHptNDYyIDBjLTU2LjY3IDEuNDIzLTEwMy4wMzQgMTYuMjQ2LTE5MCA0NS4yMTd2MzAxLjA1Yzg0LjMxNy0yNy42OTggMTQzLjQxMy00Mi41IDE5MC00NC4yVjg5LjI4N3ptLTI1NCA1NS4xOTV2MjAwLjMyNWMxNS40NyAzLjEgMzAuNzEgMy4yOTIgNDYgLjA5N1YxNDQuNDgyYy03LjIyNyAzLjA1OC0xNS4xNCA0LjUxOC0yMyA0LjUxOC03Ljg2IDAtMTUuNzczLTEuNDYtMjMtNC41MTh6bTAgMjE4LjYyN3YxMy45MzNjMTUuMjk2IDMuNDg4IDMwLjUxMiAzLjI4NCA0Ni0uMVYzNjMuMjJjLTE1LjM3IDIuNzI4LTMwLjc2NCAyLjU0My00Ni0uMTF6bTQ2IDMyLjE4NWMtMTUuMjI2IDIuODU2LTMwLjYzMyAzLjA1OC00NiAuMTI1djQ4LjgzOGMzLjIyMiAzLjI0IDUuNzc1IDUuODc2IDguMzY1IDcuNTYgMy4yODMgMi4xMzYgNi43NyAzLjQ5IDE0LjI3NCAzLjE5bC4xOC0uMDA4aC4xOGMxMS42MSAwIDE1Ljk1NC00LjA0IDIzLTEwLjgzNnYtNDguODd6Ii8+PC9zdmc+',
  insight:    'PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA1MTIgNTEyIiBmaWxsPSJGSUxMIj48cGF0aCBkPSJNMjU0LjU2MyAyMC43NWMtNDIuOTYgMC04NS45MTggMTYuMzg3LTExOC42ODggNDkuMTU2LTY1LjU0IDY1LjU0LTY1Ljg1MiAxNzIuMTUtLjMxMyAyMzcuNjg4IDY1LjU0IDY1LjU0IDE3Mi4xNSA2NS4yMjYgMjM3LjY4OC0uMzEzIDY1LjU0LTY1LjUzOCA2NS41NC0xNzEuODM1IDAtMjM3LjM3NC0zMi43Ny0zMi43Ny03NS43MjgtNDkuMTU2LTExOC42ODgtNDkuMTU2em0tLjE1NyAxOC40N2ExNDkuMjg0IDE0OS4yODQgMCAwIDEgNzQuMzEzIDE5Ljk2OGMtMTMuNTczLTMuOTg0LTI2LjI2Ni0yLjQ1NS0zNC4yMiA1LjUtMTQuNDM3IDE0LjQzNy03Ljc5NiA0NC40ODUgMTQuODEzIDY3LjA5MyAyMi42MDggMjIuNjEgNTIuNjI1IDI5LjIyIDY3LjA2MiAxNC43ODIgOC41MjMtOC41MjIgOS43MDYtMjIuNDY4IDQuNTk0LTM3LjEyNSAzNi4zNTIgNTcuNjg0IDI5LjU4NiAxMzQuNi0yMC42OSAxODQuODc1LTI5LjE1OCAyOS4xNi02Ny4zNTMgNDMuNzczLTEwNS41NiA0My44MTMgOS40MzYtMi4zIDE3Ljc2Mi02LjczMiAyNC40MzYtMTMuNDA2IDI4Ljg4NS0yOC44ODYgMTUuNjQtODguOTU0LTI5LjU5NC0xMzQuMTktNDUuMjM0LTQ1LjIzMy0xMDUuMzAyLTU4LjUxLTEzNC4xODctMjkuNjI0LTQuMDUyIDQuMDUyLTcuMjY2IDguNzIzLTkuNjg4IDEzLjg3NSAzLjA5Mi0zMy41MzcgMTcuNDczLTY2LjIyMiA0My4xNTctOTEuOTA1IDI5LjE5OC0yOS4yIDY3LjM4NC00My43MzcgMTA1LjU2Mi00My42NTZ6TTM4Ni45NyAzMTkuMjhjLS4yMDUuMjA2LS4zOS40MjItLjU5NS42MjYtNzIuNzggNzIuNzgtMTkxLjI1MiA3My4xNTUtMjY0LjAzLjM3NS0uMjc4LS4yNzUtLjU0LS41NjUtLjgxNC0uODQyLTExLjk4NyA5LjQ4My0xOC44MSAyMC4zODQtMTguODEgMzIgMCAzNi41MjMgNjcuMzE1IDY2LjEyNSAxNTEuMzQzIDY2LjEyNSA4NC4wMjcgMCAxNTIuMDkzLTI5LjYgMTUyLjA5My02Ni4xMjUgMC0xMS42OC02Ljk3LTIyLjYzNy0xOS4xODctMzIuMTU3em0zOS43MTcgNTQuNTY0Yy0yMi4yMjUgMzIuMjktOTEuMTkyIDU1LjkwNi0xNzIuNjI1IDU1LjkwNi04MS4xNzIgMC0xNDkuOTU0LTIzLjQ2LTE3Mi40MDYtNTUuNTk0LTEyLjYzOCAxMS4zLTE5LjcyIDI0LjA1Mi0xOS43MiAzNy41NjMuMDAyIDQ2LjkyOCA4NS41NDYgODUuMDMgMTkyLjA2NCA4NS4wMyAxMDYuNTE4IDAgMTkyLjk3LTM4LjEgMTkyLjk3LTg1LjAzIDAtMTMuNjM3LTcuMzEzLTI2LjQ5OC0yMC4yODMtMzcuODc2eiIvPjwvc3ZnPg==',
  correction: 'PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA1MTIgNTEyIiBmaWxsPSJGSUxMIj48cGF0aCBkPSJNMjU1Ljg3NSAxOS43NWMtMTUuNTQuMzM2LTMwLjQ0NCA0LjE5My00NC45NyAxMC41bDIyLjQ3IDQyYzcuNDItMi42NTIgMTUuMDIzLTQuNDQyIDIyLjUtNC41IDI1LjYzMyAwIDUyLjc1NCAxMy42NTggNzMuNDcgNDkuNDdsMTYuNjI0IDI4Ljg3NCAyMC4yMTctMTEuNjU2IDQzLjQwNyA3NS4xODctNTMuNSAzMC44NDQgMTA3LjgxMiA2Mi4xODZWMTc4LjMxMmwtMzMuMDYyIDE5LjA2My01OS41LTEwNC4xNTZjLTI3LjQ3Ni00Ny41MDYtNzEuMDctNzMuODQ4LTExNS40Ny03My40N3ptLTc1LjIyIDU3Ljg0NEw3Mi44MTMgMTM5Ljc4bDMyLjI4MiAxOC41OTUtNTYuMTU2IDk4LjMxM2MtMjUuMTUzIDQzLjUwOC0yNi45MzQgOTIuODI3LTYgMTMxLjk2OCA4LjY3NSAxNi4yMiAyMS44MzggMjkuNTA4IDM3LjUgNDAuNDdsMjQtNDAuNDdjLTguMDQyLTYuMzYtMTQuOS0xMy45MTItMTkuNS0yMi41LTEyLjUxLTIzLjQwMi0xMy4zMjItNTQuNjQgNC41LTg1LjQ3bDEzLjYyNC0yMy40MzYtMTkuNjg3LTExLjM3NSA0My4zMTMtNzUuMDMgNTMuOTY4IDMxLjA5M1Y3Ny41OTR6bTI1NS4xNTcgMjY3LjU2MmMtMS41NjQgNy42ODctMy44MzUgMTQuMzYyLTcuNSAyMS0xMi44MyAyMy4yMDYtMzggNDAuNS03Ny45NjggNDAuNWgtMjQuNDM4djIyLjkwNmgtODYuNzhWMzY3LjVMMTMxLjMxIDQyOS42NTZsMTA3LjgxMyA2Mi4xODh2LTM3LjIyaDExMS4yMmM1NC41MiAwIDk4LjUwNi0yNS42NDggMTE5Ljk2Ny02NC40NjggNy41NjYtMTMuNjk1IDExLjczOC0yOS4yNDIgMTMuNS00NWgtNDh6Ii8+PC9zdmc+',
  preference: 'PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA1MTIgNTEyIiBmaWxsPSJGSUxMIj48cGF0aCBkPSJNMjkuMDE4IDE4Ljg3NWMtMi42MyAxMC4yOTcuMDQ3IDIxLjcyIDguMDQ0IDI5LjcyIDEwLjAzNSAxMC4wMzQgMjUuNDYgMTEuNjk2IDM3LjI5IDVhNjA0LjYyOCA2MDQuNjI4IDAgMCAwIDE3LjM1NyAxNS4xMiAzMC41ODYgMzAuNTg2IDAgMCAwLS41MjIgNS41OTdjMCAxNy4wMjQgMTQuMDA4IDMxIDMxLjAzIDMxIDQuOTE3IDAgOS41NzYtMS4xNyAxMy43Mi0zLjI0YTY4OC41MjggNjg4LjUyOCAwIDAgMCAxNy40ODIgMTEuNDggMzAuNjY4IDMwLjY2OCAwIDAgMC0uNzMyIDYuNjM1YzAgMTcuMDI0IDE0LjAwOCAzMSAzMS4wMyAzMSA3LjU3NyAwIDE0LjU1LTIuNzcyIDE5Ljk2NC03LjM0NWwxMy44NzMgOC4xMjVhMjcuOTc0IDI3Ljk3NCAwIDAgMC0uNDE0IDQuNzMydjM4LjkwNEwxMTQuMDcgMjU1LjI3djE2MC4wNjRsMTM4LjI4NCA4MC4wNTMgMTM4LjI4My04MC4wNTNWMjU1LjI3TDI4Ni41OSAxOTUuMDM3VjE1Ni43YzAtLjk4My0uMDY3LTEuOTQ2LS4xNzItMi44OTcgNS4zOTMtMy4wNyAxMC42NTUtNi4wOCAxNS42OTctOC45OTQgNS4yMjYgMy45OTIgMTEuNzM2IDYuMzc3IDE4Ljc2MiA2LjM3NyAxNy4wMjMgMCAzMS0xMy45NzYgMzEtMzEgMC0xLjg2Ny0uMTc2LTMuNjk1LS40OTgtNS40NzZhNjIxLjMzNSA2MjEuMzM1IDAgMCAwIDE3Ljk3OC0xMi4yOThjMy45NyAxLjg1NSA4LjM4IDIuOSAxMy4wMiAyLjkgMTcuMDIzIDAgMzEuMDMtMTMuOTc2IDMxLjAzLTMxYTMwLjczIDMwLjczIDAgMCAwLS41NTMtNS43OCA5MTEuNzIgOTExLjcyIDAgMCAwIDE2LjMxOC0xNC4xMTZjMTEuNiA1LjcxNCAyNi4xMzUgMy43NzggMzUuNzM2LTUuODIyIDcuOTk4LTcuOTk4IDEwLjY3NS0xOS40MiA4LjA0NS0yOS43Mkg0NTIuNTRjNC4wMTggNC44ODggMy43MzYgMTEuOTE2LS44NSAxNi41LTQuODg3IDQuODg4LTEyLjU1IDQuODktMTcuNDM3IDAtNC41ODUtNC41ODUtNC44NjctMTEuNjE0LS44NS0xNi41aC0yMC40MTRjLTEuOTE1IDcuNS0xIDE1LjU5MiAyLjcyIDIyLjUyOGE4ODkuNTI0IDg4OS41MjQgMCAwIDEtMTIuMDM0IDEwLjQzNGMtNS41NzUtNS4yODgtMTMuMDgzLTguNTU1LTIxLjI5Ny04LjU1NS0xNy4wMjQgMC0zMS4wMyAxNC4wMS0zMS4wMyAzMS4wMzIgMCA1LjQ1IDEuNDM4IDEwLjU4MyAzLjk0OCAxNS4wNWE2MDAuNTcgNjAwLjU3IDAgMCAxLTEyLjc5NyA4LjY3M2MtNS42LTUuNDgtMTMuMjQtOC44OC0yMS42Mi04Ljg4LTE3LjAyNSAwLTMxLjAzMiAxNC4wMS0zMS4wMzIgMzEuMDMyIDAgMy4xNjYuNDg0IDYuMjI1IDEuMzgzIDkuMTEtNC4yMyAyLjQ0NS04Ljc0NCA1LjAyOC0xMy4yNDcgNy42MDVhMjguMTc2IDI4LjE3NiAwIDAgMC0zLjI0Ni0yLjcxNmMtNi42OTItNC43NjgtMTQuNzItNi44ODItMjIuNzE0LTcuMDE0LTcuOTk2LS4xMzItMTYuMTUgMS43MTgtMjIuOTcgNi41MDRhMjYuMzcyIDI2LjM3MiAwIDAgMC0yLjMzNyAxLjg1Yy00LjM2Ny0yLjU3My04Ljc2NC01LjE2NC0xMi45NDctNy42MjIuNjQyLTIuNDcuOTg0LTUuMDU2Ljk4NC03LjcxNiAwLTE3LjAyNC0xNC4wMDctMzEuMDMyLTMxLjAzLTMxLjAzMi03Ljk3NyAwLTE1LjI5IDMuMDc1LTIwLjgxMiA4LjA5NGE2OTEuNzM1IDY5MS43MzUgMCAwIDEtMTMuMjQ4LTguNTk2IDMwLjY1NyAzMC42NTcgMCAwIDAgMy41Ni0xNC4zNGMwLTE3LjAyNS0xMy45NzctMzEuMDMzLTMxLTMxLjAzMy04LjI2IDAtMTUuODA0IDMuMzA0LTIxLjM4OCA4LjY0MmE1ODUuNzI5IDU4NS43MjkgMCAwIDEtMTMuNzktMTIuMDY3YzMuMDYzLTYuNTc1IDMuNzE1LTE0LjAzIDEuOTQtMjAuOThINjguNTY4YzQuMDE4IDQuODg3IDMuNzM2IDExLjkxNS0uODUgMTYuNS00Ljg4NyA0Ljg4Ny0xMi41NSA0Ljg4OC0xNy40MzcgMC00LjU4NC00LjU4Ni00Ljg2NS0xMS42MTUtLjg0OC0xNi41SDI5LjAxOHptOTMuMiA0My4wOTRjNi45MjQgMCAxMi4zMTMgNS40MiAxMi4zMTMgMTIuMzQzcy01LjM4NyAxMi4zMTItMTIuMzEgMTIuMzEyYy02LjkyNiAwLTEyLjM0NS01LjM5LTEyLjM0NS0xMi4zMTMgMC02LjkyMyA1LjQyLTEyLjM0MyAxMi4zNDQtMTIuMzQzem0yNjAuMTU3IDBjNi45MjQgMCAxMi4zNDQgNS40MiAxMi4zNDQgMTIuMzQzcy01LjQyIDEyLjMxMi0xMi4zNDUgMTIuMzEyYy02LjkyNCAwLTEyLjM0NC01LjM5LTEyLjM0NC0xMi4zMTMgMC02LjkyMyA1LjQyLTEyLjM0MyAxMi4zNDUtMTIuMzQzek0xODMuNzIgMTA3Ljg0M2M2LjkyMiAwIDEyLjM0MyA1LjQyIDEyLjM0MyAxMi4zNDQgMCA2LjkyMy01LjQyIDEyLjMxMi0xMi4zNDQgMTIuMzEyLTYuOTI2IDAtMTIuMzQ1LTUuMzktMTIuMzQ1LTEyLjMxMyAwLTYuOTIzIDUuNDItMTIuMzQzIDEyLjM0NC0xMi4zNDN6bTEzNy4xNTUgMGM2LjkyNCAwIDEyLjMxMyA1LjQyIDEyLjMxMyAxMi4zNDQgMCA2LjkyMy01LjM5IDEyLjMxMi0xMi4zMTMgMTIuMzEyLTYuOTI0IDAtMTIuMzQ0LTUuMzktMTIuMzQ0LTEyLjMxMyAwLTYuOTIzIDUuNDItMTIuMzQzIDEyLjM0NS0xMi4zNDN6bS02OS4xNjQgMzguMDEzYzQuNjk1LjA3OCA5LjM1NSAxLjUzNiAxMi4xOCAzLjU1IDIuODI2IDIuMDEyIDQuMDEgMy44MDUgNC4wMSA3LjI5MnYyNy41MmwtMTUuNTQ2LTktMTYuNTI2IDkuNTY1VjE1Ni43YzAtNC4wOSAxLjI1OC01LjgzNSAzLjk1My03LjcyNSAyLjY5Ni0xLjg5IDcuMjM3LTMuMTk1IDExLjkzLTMuMTE4em0tOC4xMjIgNTYuMDN2MzIuNzI4bC03NC4xODIgNDMuMjEtMjguNTU4LTE2LjQ2MiAxMDIuNzQtNTkuNDc2em0xOC42ODcuNjcgMTAyLjE2IDU5LjEzOC0yOC42MjQgMTYuNTAyLTczLjUzMy00Mi44My0uMDAyLTMyLjgxem0tOS45ODggNDguNjIgNzIuMjU2IDQyLjA4NS0uMDAyIDg0LjMxNi03Mi4yNTMgNDIuMDg2LTcyLjI1Ni00Mi4wODYuMDAzLTg0LjMxNCA3Mi4yNTQtNDIuMDg4em0uNDY1IDE4LjMzLTU2Ljg4MyA5OC4xNXYuNzI0bDU2LjU2NiAzMi45NzdMMzA5IDM2OC4zOHYtNjYuMDg1bC01Ni4yNDgtMzIuNzl6bS0xMTkuOTk0IDguNzY0IDI4LjU4NiAxNi40OHY4NC4wMjdsLTI4LjU4NiAxNi40OFYyNzguMjcyem0yMzkuMTkuNjY4LS4wMDMgMTE1LjY0OC0yOC43MTUtMTYuNTUzdi04Mi41NGwyOC43MTctMTYuNTU1ek0zMzMuNDkzIDM5My45OWwyOC40MTQgMTYuMzgtOTkuNjMgNTcuNjc3di0zMi41NzRsNzEuMjE2LTQxLjQ4M3ptLTE2MS43Ny4zNzUgNzEuODY0IDQxLjg2djMyLjQ5NGwtMTAwLjIxLTU4LjAxMyAyOC4zNDUtMTYuMzQyeiIvPjwvc3ZnPg==',
  episodic:   'PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA1MTIgNTEyIiBmaWxsPSJGSUxMIj48cGF0aCBkPSJNMjU1LjY1NiAyMi43NWMtMTMxLjE3MyAwLTIzNy43MiAzMy4zMjYtMjM3LjcyIDc0LjM0NC4wMDIgMjIuMzkgMzIuNDEgNDIuNTkgODIuNTY0IDU2LjIyLTE3LjQwNy04LjkxLTI3LjUzLTE5LjIxNi0yNy41My0zMC40NyAwLTMyLjEyOCA4MS43NS01OC41MyAxODIuNjg2LTU4LjUzIDEwMC45MzcgMCAxODMuMjUgMjYuNCAxODMuMjUgNTguNTMgMCAxMS4xOTQtMTAuMyAyMS41OS0yNy41MyAzMC40NyA0OS44NDMtMTMuNjI3IDgxLjk2OC0zMy45MSA4MS45NjgtNTYuMjIgMC00MS4wMTgtMTA2LjUxNC03NC4zNDQtMjM3LjY4OC03NC4zNDR6TTE0Ny40NyAxMDMuMDk0djMwLjA5NGgyMTYuMjh2LTMwLjA5NEgxNDcuNDd6bTQuMzc0IDQ4Ljc4VjM2MS45NGgxOC42ODdWMTUxLjg3NWgtMTguNjg2em0zOS4xMjUgMGMuNjk4IDYxLjgxMiAyNS4zMjUgOTYuNDM1IDUyLjgxIDEwMy44MTQtMjcuODQ3IDcuNDc1LTUyLjc3NiA0Mi45LTUyLjg0MyAxMDYuMjVoMTI4LjE4OGMtLjA2Ni02My4zNTMtMjQuOTUyLTk4Ljc2Ni01Mi43OC0xMDYuMjUgMjcuNDY4LTcuMzg2IDUyLjA1LTQxLjk5OCA1Mi43NS0xMDMuODEzSDE5MC45Njh6bTE0Ny45MzYgMFYzNjEuOTRoMTguNjg4VjE1MS44NzVoLTE4LjY4OHpNMTAwLjUgMzYwLjcyYy01MC4xNTMgMTMuNjI2LTgyLjU2MyAzMy44MjctODIuNTYzIDU2LjIxNyAwIDQxLjAxOCAxMDYuNTQ2IDc0LjM0NCAyMzcuNzIgNzQuMzQ0IDEzMS4xNzMgMCAyMzcuNjg3LTMzLjMyNSAyMzcuNjg3LTc0LjM0MiAwLTIyLjMxLTMyLjEyNS00Mi41OTMtODEuOTctNTYuMjIgMTcuMjMyIDguODggMjcuNTMyIDE5LjI0NCAyNy41MzIgMzAuNDM4IDAgMzIuMTMtODIuMzEzIDU4LjU2My0xODMuMjUgNTguNTYzUzcyLjk3IDQyMy4yODMgNzIuOTcgMzkxLjE1NWMwLTExLjI1NCAxMC4xMjMtMjEuNTI4IDI3LjUzLTMwLjQzN3ptNDYuOTcgMTkuOTA1djMwLjA2M2gyMTYuMjh2LTMwLjA2M0gxNDcuNDd6Ii8+PC9zdmc+',
  procedure:  'PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA1MTIgNTEyIiBmaWxsPSJGSUxMIj48cGF0aCBkPSJNMTM3LjcxIDE4LjMyNiAxNy44NjYgMTM4LjE2NmwyOS41ODIgMjkuNTgyYzIzLjA0LTUzLjY5OCA2Ni4xNC05Ni44MDIgMTE5Ljg0LTExOS44NDJsLTI5LjU4LTI5LjU4em0yMzguMjg2LjA0TDM0Ni40NCA0Ny45MmM1My42OTMgMjMuMDQ4IDk2Ljc5IDY2LjE1NSAxMTkuODIyIDExOS44NTdsMjkuNTc2LTI5LjU3NS0xMTkuODQyLTExOS44NHptLTEzMy4yNyAzNy4wNEMxMzcuNDA1IDYyLjY0IDU0LjQ0OCAxNTAuMTI2IDU0LjQ0OCAyNTcuMzFjMCAxMTEuOTMgOTAuNDY2IDIwMi4zOTcgMjAyLjM5OCAyMDIuMzk3IDMyLjc1IDAgNjMuNjYtNy43NTcgOTEuMDA3LTIxLjUybC0yMi4yNi0xNS43OGMtMjEuMTczIDguODQtNDQuMzk0IDEzLjczNC02OC43NDUgMTMuNzM0LTk4LjY1MiAwLTE3OC44MjctODAuMTcyLTE3OC44MjctMTc4LjgyNCAwLTkwLjk0MiA2OC4xMzMtMTY2LjE3OCAxNTYuMDY1LTE3Ny4zODJsOC42MzctMjQuNTI4em0yOS40MzIuMDc2IDguNTU1IDI0LjYwNGM4Ny4zOTcgMTEuNjkgMTU0Ljk2IDg2LjY3IDE1NC45NiAxNzcuMjMgMCA0OC4yMzQtMTkuMTcgOTIuMDQzLTUwLjI5IDEyNC4yM2w4LjYzMyAyNC42ODZjNDAuMTItMzYuOTYzIDY1LjIzLTg5Ljk2IDY1LjIzLTE0OC45MjMgMC0xMDYuNzgyLTgyLjMzMi0xOTQuMDIzLTE4Ny4wODgtMjAxLjgyOHptLTE0Ljc1IDE0LjQ5LTMyLjMgOTEuNzA2aDE4LjkyNXY0NS4wNjhhNTEuOTAzIDUxLjkwMyAwIDAgMSAyNi4yOC0uMjZ2LTQ0LjgwOGgxOC45OEwyNTcuNDA4IDY5Ljk3em03MS44MiA0NC40Mi0xNy4xOTcgMjkuNzlhMTI0LjQyNyAxMjQuNDI3IDAgMCAwLTEwLjU5Ni00LjVsMTQuMTQ0IDQwLjY4M2gtMjYuNTc2djM1LjA1N2MxMi43MDIgOS41NjIgMjAuOTUgMjQuNzU2IDIwLjk1IDQxLjc5MyAwIDguNjk3LTIuMTYgMTYuOTEtNS45NTYgMjQuMTQybDQwLjcwNSA1NC4xODYgMTkuNDY2LTE0LjY2MiA0LjkyNCAxNC4wOCAyMC42MDMgMTEuODk3YTE1OS43NDQgMTU5Ljc0NCAwIDAgMCA5LjUyNi0xNi4wOGwtMjkuMzUtMTYuOTQ1YTEyNC44MzggMTI0LjgzOCAwIDAgMCAxMi44Ni00NS4zNDhoMzMuODYyYy4yNTMtMy42OS4zOTItNy40MTIuMzkyLTExLjE2OCAwLTIuNTItLjA2Ni01LjAyNi0uMTgtNy41MmgtMzMuODJjLS45OC0xNi40MjMtNS4xMS0zMS45OTMtMTEuNzk2LTQ2LjExMmwyOS40NS0xNy4wMDJhMTU5Ljk4NiAxNTkuOTg2IDAgMCAwLTkuMjA4LTE2LjI2NmwtMjkuNDggMTcuMDJhMTI2LjA4OSAxMjYuMDg5IDAgMCAwLTMzLjczLTMzLjkyMmwxNy4xNTMtMjkuNzFhMTU5LjM1MyAxNTkuMzUzIDAgMCAwLTE2LjE0NC05LjQxem0tMTQ1LjM4LjMxM2ExNTkuNTkxIDE1OS41OTEgMCAwIDAtMTYuMTA0IDkuNDgzbDE3LjYyIDMwLjUyM2ExMjYuMjA1IDEyNi4yMDUgMCAwIDAtMzIuNjcgMzMuNzM3bC0zMC42NDUtMTcuNjk1YTE1OS4zNjkgMTU5LjM2OSAwIDAgMC05LjE2NyAxNi4yOWwzMC43MyAxNy43NGMtNi4zODUgMTMuODI4LTEwLjMzIDI5LjAxNi0xMS4yODUgNDUuMDE1SDk2Ljg5NWExNjMuMDg0IDE2My4wODQgMCAwIDAtLjE4MiA3LjUyYzAgMy43NTUuMTQgNy40NzcuMzkyIDExLjE2N2gzNS40NzdhMTI0Ljg0NSAxMjQuODQ1IDAgMCAwIDEyLjMyNCA0NC4yNjRsLTMwLjYxMyAxNy42NzRhMTU5Ljc5NCAxNTkuNzk0IDAgMCAwIDkuNDkyIDE2LjFsMzAuNTkyLTE3LjY2M2ExMjYuMTQzIDEyNi4xNDMgMCAwIDAgMzIuNDE4IDMyLjIzNmwtMTcuNTI3IDMwLjM1M2ExNTkuNjkgMTU5LjY5IDAgMCAwIDE2LjIxNiA5LjI5MmwxNy40NzMtMzAuMjY1YTEyNC44NTcgMTI0Ljg1NyAwIDAgMCA0NC4xNDcgMTIuMDUydjM0LjYyYzMuMjI0LjE5MyA2LjQ3Mi4zMDMgOS43NDYuMzAzIDMgMCA1Ljk4LS4wOSA4Ljk0LS4yNTJ2LTM0LjQ5N2ExMjUuNTU5IDEyNS41NTkgMCAwIDAgMTkuMzI1LTIuNzU2bDEwLjY4Mi04LjA0Ny00Ny41Mi02My4yNTdjLTI0LjMyNi00LjQ1NC00Mi45MDgtMjUuODYyLTQyLjkwOC01MS40MjggMC0xNi41OTMgNy44MzMtMzEuNDMgMTkuOTc2LTQxLjAyNnYtMzUuODI1aC0yNi42M2wxNC4xOTYtNDAuMzFhMTI1LjA4NSAxMjUuMDg1IDAgMCAwLTExLjUxIDUuMDU2bC0xNy41NTQtMzAuNDA1em03My44MTQgMTA4LjkwNmMtMTguNjcgMC0zMy42MDUgMTQuOTM1LTMzLjYwNSAzMy42MDUgMCAxOC42NyAxNC45MzYgMzMuNjAzIDMzLjYwNSAzMy42MDMgMTguNjcgMCAzMy42MDQtMTQuOTM0IDMzLjYwNC0zMy42MDMgMC0xOC42Ny0xNC45MzQtMzMuNjA0LTMzLjYwNC0zMy42MDR6bTM0LjM2MyA3Mi45MjdjLTUuOTc4IDUuMjM0LTEzLjE0MiA5LjE0LTIxLjAzIDExLjIzM2w1MC45NTIgNjcuODI4LTE0LjU3OCAxMC45ODQgNzkuNzQgNTYuNTI1LTMyLjEzNy05MS45MDItMTMuOTc1IDEwLjUyNS00OC45NzMtNjUuMTkzem0xNzQuMjIzIDUwLjMzYy0xNC4yMDMgMzMuMTAyLTM2LjAzNyA2Mi4xNjctNjMuMjcgODQuOTk4bDkuNyAyNy43MzMgODMuMTUtODMuMTUtMjkuNTgtMjkuNTh6TTQ3LjQ2IDM0Ni45bC0yOS41ODUgMjkuNTg2IDExOS44NCAxMTkuODQgMjkuNjAzLTI5LjYwM0MxMTMuNjE2IDQ0My42OSA3MC41MDggNDAwLjU5MyA0Ny40NiAzNDYuOXptMzIzLjM0MyAxMDcuNTUzYTIyNi44MTggMjI2LjgxOCAwIDAgMS0yNC4zOTUgMTIuMjU0bDI5LjU4IDI5LjU4IDIyLjMzLTIyLjMzLTI3LjUxNS0xOS41MDR6Ii8+PC9zdmc+',
  skill:      'PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA1MTIgNTEyIiBmaWxsPSJGSUxMIj48cGF0aCBkPSJNMTQzLjYyNyAzNi4zNjFjLTIuMTggMC0xNi40OTUgMzguMzAzLTE4LjI1OCAzOS41ODQtMS43NjMgMS4yODEtNDIuNjE1IDMuMDYtNDMuMjg5IDUuMTMzLS42NzMgMi4wNzMgMzEuMzMgMjcuNTIzIDMyLjAwNCAyOS41OTYuNjc0IDIuMDczLTEwLjI2IDQxLjQ3NS04LjQ5NiA0Mi43NTYgMS43NjMgMS4yOCAzNS44Ni0yMS4yOTEgMzguMDM5LTIxLjI5MSAyLjE4IDAgMzYuMjc2IDIyLjU3MiAzOC4wMzkgMjEuMjkgMS43NjMtMS4yOC05LjE3LTQwLjY4Mi04LjQ5Ni00Mi43NTUuNjczLTIuMDczIDMyLjY3Ny0yNy41MjMgMzIuMDA0LTI5LjU5Ni0uNjc0LTIuMDczLTQxLjUyNi0zLjg1Mi00My4yOS01LjEzMy0xLjc2My0xLjI4LTE2LjA3Ny0zOS41ODQtMTguMjU3LTM5LjU4NHptMjI0Ljc0NiAwYy0yLjE4IDAtMTYuNDk0IDM4LjMwMy0xOC4yNTggMzkuNTg0LTEuNzYzIDEuMjgxLTQyLjYxNSAzLjA2LTQzLjI4OSA1LjEzMy0uNjczIDIuMDczIDMxLjMzIDI3LjUyMyAzMi4wMDQgMjkuNTk2LjY3NCAyLjA3My0xMC4yNiA0MS40NzUtOC40OTYgNDIuNzU2IDEuNzYzIDEuMjggMzUuODYtMjEuMjkxIDM4LjAzOS0yMS4yOTEgMi4xOCAwIDM2LjI3NiAyMi41NzIgMzguMDQgMjEuMjkgMS43NjItMS4yOC05LjE3LTQwLjY4Mi04LjQ5Ny00Mi43NTUuNjc0LTIuMDczIDMyLjY3Ny0yNy41MjMgMzIuMDA0LTI5LjU5Ni0uNjc0LTIuMDczLTQxLjUyNi0zLjg1Mi00My4yOS01LjEzMy0xLjc2Mi0xLjI4LTE2LjA3Ny0zOS41ODQtMTguMjU3LTM5LjU4NHpNMjU2IDM5Ljg4M2MtNy4xMiAwLTUzLjg4NCAxMjUuMTIzLTU5LjY0NSAxMjkuMzA4LTUuNzYgNC4xODUtMTM5LjIxMSA5Ljk5Ni0xNDEuNDEyIDE2Ljc2OC0yLjIgNi43NzIgMTAyLjM0OSA4OS45MTIgMTA0LjU1IDk2LjY4NCAyLjIgNi43NzEtMzMuNTEzIDEzNS40ODYtMjcuNzUzIDEzOS42NzFDMTM3LjUgNDI2LjUgMjQ4Ljg4IDM1Mi43NiAyNTYgMzUyLjc2YzcuMTIgMCAxMTguNSA3My43NCAxMjQuMjYgNjkuNTU0IDUuNzYtNC4xODUtMjkuOTUyLTEzMi45LTI3Ljc1Mi0xMzkuNjcxIDIuMi02Ljc3MiAxMDYuNzQ5LTg5LjkxMiAxMDQuNTQ5LTk2LjY4NC0yLjItNi43NzItMTM1LjY1Mi0xMi41ODMtMTQxLjQxMi0xNi43NjgtNS43Ni00LjE4NS01Mi41MjUtMTI5LjMwOC01OS42NDUtMTI5LjMwOHpNNzcuOTczIDI0My4xMDJjLTIuMTggMC0xNi40OTUgMzguMzAyLTE4LjI1OCAzOS41ODQtMS43NjMgMS4yOC00Mi42MTYgMy4wNi00My4yOSA1LjEzMi0uNjczIDIuMDczIDMxLjMzMyAyNy41MjMgMzIuMDA3IDI5LjU5Ni42NzMgMi4wNzMtMTAuMjYgNDEuNDc1LTguNDk2IDQyLjc1NiAxLjc2MyAxLjI4MSAzNS44NTctMjEuMjkxIDM4LjAzNy0yMS4yOTEgMi4xOCAwIDM2LjI3NSAyMi41NzIgMzguMDM5IDIxLjI5IDEuNzYzLTEuMjgtOS4xNy00MC42ODItOC40OTYtNDIuNzU1LjY3My0yLjA3MyAzMi42NzktMjcuNTIzIDMyLjAwNS0yOS41OTYtLjY3My0yLjA3My00MS41MjUtMy44NTEtNDMuMjg5LTUuMTMyLTEuNzYzLTEuMjgyLTE2LjA4LTM5LjU4NC0xOC4yNi0zOS41ODR6bTM1Ni4wNTQgMGMtMi4xOCAwLTE2LjQ5NiAzOC4zMDItMTguMjYgMzkuNTg0LTEuNzYzIDEuMjgtNDIuNjE1IDMuMDYtNDMuMjg4IDUuMTMyLS42NzQgMi4wNzMgMzEuMzMyIDI3LjUyMyAzMi4wMDUgMjkuNTk2LjY3NCAyLjA3My0xMC4yNiA0MS40NzUtOC40OTYgNDIuNzU2IDEuNzY0IDEuMjgxIDM1Ljg2LTIxLjI5MSAzOC4wNC0yMS4yOTEgMi4xNzkgMCAzNi4yNzMgMjIuNTcyIDM4LjAzNiAyMS4yOSAxLjc2NC0xLjI4LTkuMTctNDAuNjgyLTguNDk2LTQyLjc1NS42NzQtMi4wNzMgMzIuNjgtMjcuNTIzIDMyLjAwNi0yOS41OTYtLjY3My0yLjA3My00MS41MjYtMy44NTEtNDMuMjg5LTUuMTMyLTEuNzYzLTEuMjgyLTE2LjA3OC0zOS41ODQtMTguMjU4LTM5LjU4NHpNMjU2IDM2OS45MzJjLTIuMTggMC0xNi40OTQgMzguMzAyLTE4LjI1OCAzOS41ODQtMS43NjMgMS4yOC00Mi42MTUgMy4wNi00My4yODkgNS4xMzItLjY3MyAyLjA3MyAzMS4zMyAyNy41MjUgMzIuMDA0IDI5LjU5OC42NzQgMi4wNzMtMTAuMjYgNDEuNDc1LTguNDk2IDQyLjc1NiAxLjc2MyAxLjI4MSAzNS44Ni0yMS4yOTMgMzguMDM5LTIxLjI5MyAyLjE4IDAgMzYuMjc2IDIyLjU3NCAzOC4wNCAyMS4yOTMgMS43NjItMS4yODEtOS4xNy00MC42ODMtOC40OTctNDIuNzU2LjY3My0yLjA3MyAzMi42NzctMjcuNTI1IDMyLjAwNC0yOS41OTgtLjY3NC0yLjA3Mi00MS41MjYtMy44NTEtNDMuMjktNS4xMzItMS43NjMtMS4yODItMTYuMDc3LTM5LjU4NC0xOC4yNTctMzkuNTg0eiIvPjwvc3ZnPg==',
  ai_memory:  'PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA1MTIgNTEyIiBmaWxsPSJGSUxMIj48cGF0aCBkPSJNMjA5LjUgMjEuMDk0Yy0uNTUuMDA4LTEuMTE1LjAzMy0xLjY4OC4wNjJoLS40NjdjLTEwLjQyMiAwLTE5LjIzOCAzLjQwMi0yMy4xMjUgNy45MzgtMy42NDYgNC4yNTItNS40NzIgMTAuMS0uMDk1IDIyLjE1NiA1Ljc0OCA4LjgwMyAxMC4zNTIgMjAuODQ4IDE0LjM0NCAzNi4zNzVsLTE4LjEyNiA0LjY1NmMtNi43NTUtMjYuMjctMTUuMTctMzYuODMtMjAuODc1LTM5LjM0My0yLjg1NC0xLjI1NS01LjY1NS0xLjM2Ny05Ljg0NS0uMDkzcy05LjQzOCA0LjE4NS0xNS4xNTYgOC40MDZjLTguODE3IDYuNTA2LTE0LjMyNyAxNC45MTUtMTQgMjIuMDMuMjUgNS40NzcgMy42MSAxMi41NjUgMTUuMjUgMjAuMzQ1IDEuMDk2LjYxIDIuMTg3IDEuMjA1IDMuMzEgMS44NDRsLS4wOTMuMTg2YTEwOS40OTEgMTA5LjQ5MSAwIDAgMCA5LjU5NCA1LjEyNWwtOC4wMyAxNi44NzZjLTUuMDc1LTIuNDA4LTkuNjI4LTQuOTQ0LTEzLjY4OC03LjU5NC0xNC43MTUtOC4wNDctMjUuNTQtMTEuNTc3LTMxLjMxMi0xMS4wOTMtMy4wNzguMjU3LTQuOTMgMS4wNjctNy4yNSAzLjM3NC0yLjMyIDIuMzA2LTQuOTE0IDYuNDktNy4yOCAxMy4wOTQtMy45NCAxMC45OS00LjYwMiAxOS45OC0xLjU5NSAyNC44NzQgMi4zOTIgMy44OTUgOC40NjQgOC4wODcgMjIuODQ0IDkuNTMyIDMuNTkuMDc0IDcuNDEyLjIyIDExLjU5My40MDZ2LjEyNWMuNCAwIC43NzYuMDA0IDEuMTg3IDBsLjE1NiAxOC42ODhjLTQuMjkyLjA0LTguMzAyLS4xMS0xMi4wOTQtLjQwNy0xMS45NjYtLjA3My0xOS4yMjMuODk0LTIyLjIxOCAyLjQwNi0xLjg3Ni45NDctMi41ODYgMS42NjUtMy42MjUgMy43ODItMS4wNCAyLjExNi0yLjAyMiA1LjgxLTIuNjkgMTEuMjUtLjYxNSA1LjAzMy0uMjA0IDguNzMzLjg0NSAxMS4yOCAxLjA1IDIuNTUgMi41NjIgNC40MiA2LjI4IDYuNDA3IDcuNDQgMy45NzUgMjQuMzIyIDYuNSA1Mi41NjQgNC4wOTVsMS41OTMgMTguNjI1Yy0yMS42MjcgMS44NC0zNy44MTQgMS41MzQtNTAuMzEzLTEuNTYzLS44NTMgMy43MzctLjY3MiA2LjY1OC4wMyA5LjEyNS4xMi40MTIuMjU3LjgyLjQwNyAxLjIyLjAxMi4wMy4wMi4wNjIuMDMyLjA5M2EyOC4xMzUgMjguMTM1IDAgMCAwIDYuODc0IDguNDM4Yy4wMTguMDEzLjA0NC4wMTcuMDYyLjAzIDcuMDUgNS4yMiAxOC42MjIgOC4xODggMjUuNDcgOC4xODhoMTAzLjgxYzEyLjExIDAgMjIuNjItOC45MTYgMjYuNjktMjUuMDkybDguMDYtMzIuMDYzIDkuOTQgMzEuNTYzYzUuMjE2IDE2LjYwMiAxNi4wODcgMjUuNTkzIDI2Ljg0MyAyNS41OTNoMTAzLjgxYzYuMjYgMCAxOC4zNy0zLjk0NiAyNS41OTUtMTAuMjVhMzAuMzE1IDMwLjMxNSAwIDAgMCAyLjUtMi40MzZjLjE0Mi0uMTU3LjI3LS4zMS40MDYtLjQ3LjAyLS4wMjIuMDQ2LS4wMzguMDY0LS4wNiAxLjUtMS45MTUgMi43MTYtNCAzLjc1LTYuMjUuMTI2LS4zNDYuMjc0LS42ODYuMzc1LTEuMDMzLjYxMi0yLjEwNy44NC00LjMxNC40MzYtNi44NzQtMTIuNjQ2IDMuMzY1LTI5LjE2IDMuNzQtNTEuNDM3IDEuODQ0bDEuNTkyLTE4LjYyNWMyOC4yNDMgMi40MDQgNDUuMDkzLS4xMiA1Mi41MzItNC4wOTQgMy43Mi0xLjk4NiA1LjIzMi0zLjg1NyA2LjI4LTYuNDA1IDEuMDUtMi41NDggMS40OTItNi4yNDguODc2LTExLjI4LS42NjctNS40NDItMS42OC05LjEzNS0yLjcyLTExLjI1LTEuMDM4LTIuMTE4LTEuNzQ4LTIuODM1LTMuNjI0LTMuNzgyLTIuOTk1LTEuNTEzLTEwLjI1Mi0yLjQ4LTIyLjIyLTIuNDA3LTMuNzkuMjk2LTcuOC40NDctMTIuMDkyLjQwNmwuMTg3LTE4LjY4N2MuNDEyLjAwNC43ODcgMCAxLjE5IDB2LS4xMjVjNC4xOC0uMTg1IDgtLjMzMiAxMS41OTItLjQwNiAxNC4zOC0xLjQ0NSAyMC40NTItNS42MzcgMjIuODQ0LTkuNTMgMy4wMDctNC44OTcgMi4zNDUtMTMuODg1LTEuNTk0LTI0Ljg3Ni0yLjM2Ni02LjYwNS00Ljk5Mi0xMC43ODgtNy4zMTItMTMuMDk0LTIuMzItMi4zMDctNC4xNzItMy4xMTctNy4yNS0zLjM3NS01Ljc3Mi0uNDg1LTE2LjU3IDMuMDQ1LTMxLjI4IDExLjA5My00LjA2NiAyLjY1NC04LjYzNiA1LjE4LTEzLjcyIDcuNTkzbC04LTE2Ljg3NWExMDkuMjMzIDEwOS4yMzMgMCAwIDAgOS41OTQtNS4xMjRsLS4xMjUtLjE4N2MxLjE4NS0uNjc2IDIuMzQzLTEuMjk3IDMuNS0xLjk0IDExLjUyLTcuNzQgMTQuODQzLTE0Ljc5NiAxNS4wOTItMjAuMjUuMzI2LTcuMTE1LTUuMTg1LTE1LjUyNC0xNC0yMi4wMy01LjcxOC00LjIyLTEwLjk2Ni03LjEzMi0xNS4xNTYtOC40MDYtNC4xOS0xLjI3NC02Ljk5LTEuMTYyLTkuODQ0LjA5My0xLjk4Ljg3Mi00LjI5NCAyLjc0NS02Ljc1IDUuODc2YTY3LjU5MyA2Ny41OTMgMCAwIDEtMS40NjggMy4xODdsLS41OTQtLjI4Yy00LjA0MiA2LjIxLTguMzM2IDE1Ljk0NC0xMi4wOTQgMzAuNTZsLTE4LjA5NC00LjY1NWM0LjQ1Ni0xNy4zMyA5LjY1My0zMC4zMjQgMTYuMzc1LTM5LjMxMyAzLjgzNC0xMC4wODMgMi4wODMtMTUuMzMtMS4yNS0xOS4yMTgtMy44ODctNC41MzYtMTIuNzAzLTcuOTM4LTIzLjEyNS03LjkzOGgtLjQ2Yy05LjE2LS40Ni0xNS4zMTUgMS43NDYtMjAuNDA2IDUuNTYzLTUuMDkyIDMuODE2LTkuMTg0IDkuNjI4LTEyLjI4MiAxNi45MDUtNi4xOTUgMTQuNTU0LTcuOTM3IDM0LjM4LTcuOTM3IDQ4LjkwNnYuMDY0bC0uMTkgMzQuMDN2LjA5NWgtMTguNjg2di0uMDk1bC0uMTg4LTM0LjAzdi0uMDY0YzAtMTQuNTI1LTEuNzEtMzQuMzUtNy45MDYtNDguOTA1LTMuMDk4LTcuMjc3LTcuMTktMTMuMDktMTIuMjgtMTYuOTA2LTQuNzc1LTMuNTgtMTAuNDc3LTUuNzUtMTguNzItNS42MjZ6bTQ4Ljc4IDIzOS40N2MtOC40ODYgMTIuMjA3LTIxLjI4OCAyMC4xODYtMzYuMDkyIDIwLjE4NkgxODEuNTNsOTguMTI2IDgwLjYyNS04Mi4yMiAxLjI4IDIxNy40MDggMTMzLjQ0TDM0Mi4yOCAzODcuNzhsNTUuMTI2IDQuNzUtNzYuMDMtMTExLjc4aC0yNy42NTdjLTE0LjM5MyAwLTI2Ljc4OC04LjAyLTM1LjQ0LTIwLjE4OHoiLz48L3N2Zz4=',
};
// ── Image cache: keyed by "type+color" to reuse loaded Images ────────────────
if (!window._iconCache) window._iconCache = new Map();

const Graph = ForceGraph3D({ rendererConfig: { antialias: true, alpha: true } })(document.getElementById('graph-root'))
  .backgroundColor('#0c0c14')
  .nodeId('id')
  .nodeLabel(() => '')
  .nodeColor(n => n.color)
  .nodeVal(n => 0.5 + n.importance * 0.8)
  .nodeOpacity(0.92)
  .nodeResolution(24)
  .nodeThreeObject(n => {
    // ── Game-icon sprite (game-icons.net SVGs) ────────────────────────
    const SZ = 128;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = SZ;
    const ctx = canvas.getContext('2d');
    const col = n.color || '#C084FC';
    const r = parseInt(col.slice(1,3),16), g = parseInt(col.slice(3,5),16), b = parseInt(col.slice(5,7),16);
    const imp  = Math.max(1, Math.min(10, n.importance || 5));

    // Get or create cached Image for this type+color combo
    const cacheKey = (n.mtype || 'ai_memory') + col;
    let iconImg = window._iconCache.get(cacheKey);
    if (!iconImg) {
      const icoB64 = ICON_B64[n.mtype] || ICON_B64.ai_memory;
      const svgStr = atob(icoB64).replace('FILL', col);
      iconImg = new Image();
      iconImg.src = 'data:image/svg+xml;base64,' + btoa(svgStr);
      window._iconCache.set(cacheKey, iconImg);
    }
    n.__iconImg = iconImg;
    // Unique phase per node — no two nodes ever pulse/rotate in sync
    n.__phase = (r * 0.031 + g * 0.019 + b * 0.013 + imp * 0.17) % (Math.PI * 2);

    // Trigger redraw when image finishes loading (first paint is placeholder)
    if (!iconImg.complete) {
      iconImg.onload = () => {
        if (n.__drawNode && n.__tex) { n.__drawNode(performance.now()); n.__tex.needsUpdate = true; }
      };
    }

    n.__drawNode = function(t) {
      ctx.clearRect(0, 0, SZ, SZ);
      const cx = SZ / 2, cy = SZ / 2;
      const ph = n.__phase;

      // ── Master pulse: 0→1, ~5s cycle, unique phase per node ─────────
      const pulse  = 0.5 + 0.5 * Math.sin(t * 0.00125 + ph);
      const glowR  = 44 + pulse * 14;                 // halo radius 44–58px
      const haloA  = 0.09 + pulse * 0.20;             // halo alpha 0.09–0.29

      // ── Layer 1: breathing outer halo ─────────────────────────────
      const halo = ctx.createRadialGradient(cx, cy, 26, cx, cy, glowR);
      halo.addColorStop(0, 'rgba(' + r + ',' + g + ',' + b + ',' + haloA.toFixed(3) + ')');
      halo.addColorStop(1, 'rgba(' + r + ',' + g + ',' + b + ',0)');
      ctx.beginPath(); ctx.arc(cx, cy, glowR, 0, 2 * Math.PI);
      ctx.fillStyle = halo; ctx.fill();

      // ── Layer 2: dark disc background ──────────────────────────────
      ctx.beginPath(); ctx.arc(cx, cy, 34, 0, 2 * Math.PI);
      ctx.fillStyle = 'rgba(8,6,18,0.93)'; ctx.fill();

      // ── Layer 3: slow CW rotating dashed outer ring ────────────────
      const dashRot = t * 0.00055 + ph;               // ~11s/revolution
      ctx.save();
      ctx.translate(cx, cy); ctx.rotate(dashRot);
      ctx.beginPath(); ctx.arc(0, 0, 37, 0, 2 * Math.PI);
      ctx.strokeStyle = 'rgba(' + r + ',' + g + ',' + b + ',0.38)';
      ctx.lineWidth = 1.2;
      ctx.setLineDash([9, 5]);
      ctx.stroke();
      ctx.restore();

      // ── Layer 4: fast CCW energy sweep arc (Destiny 2 style) ──────
      const sweepRot = -t * 0.00195 + ph;             // CCW, ~3.2s/revolution
      const arcAlpha = (0.55 + pulse * 0.40).toFixed(3);
      ctx.save();
      ctx.translate(cx, cy); ctx.rotate(sweepRot);
      ctx.beginPath(); ctx.arc(0, 0, 37, -0.50, 0.50);
      ctx.strokeStyle = 'rgba(' + r + ',' + g + ',' + b + ',' + arcAlpha + ')';
      ctx.lineWidth = 2.8;
      ctx.setLineDash([]);
      ctx.shadowColor = col;
      ctx.shadowBlur = 10;
      ctx.stroke();
      // tail fade: dimmer leading sliver behind it
      ctx.beginPath(); ctx.arc(0, 0, 37, 0.50, 1.10);
      ctx.strokeStyle = 'rgba(' + r + ',' + g + ',' + b + ',0.18)';
      ctx.lineWidth = 1.5;
      ctx.shadowBlur = 0;
      ctx.stroke();
      ctx.restore();

      // ── Layer 5: inner border ring ─────────────────────────────────
      ctx.beginPath(); ctx.arc(cx, cy, 34, 0, 2 * Math.PI);
      ctx.strokeStyle = 'rgba(' + r + ',' + g + ',' + b + ',' + (0.40 + pulse * 0.32).toFixed(3) + ')';
      ctx.lineWidth = 1.0; ctx.setLineDash([]); ctx.stroke();

      // ── Layer 6: game icon — alpha breathes in sync with pulse ─────
      if (n.__iconImg && n.__iconImg.complete && n.__iconImg.naturalWidth > 0) {
        ctx.save();
        ctx.globalAlpha = 0.72 + pulse * 0.22;
        ctx.beginPath(); ctx.arc(cx, cy, 32, 0, 2 * Math.PI); ctx.clip();
        ctx.drawImage(n.__iconImg, cx - 24, cy - 24, 48, 48);
        ctx.restore();
      } else {
        ctx.beginPath(); ctx.arc(cx, cy, 5, 0, 2 * Math.PI);
        ctx.fillStyle = col; ctx.fill();
      }

      // ── Layer 7: scan shimmer — horizontal bar sweeps top→bottom ──
      const scanY = cx - 32 + ((t * 0.028 + ph * 18) % 68);
      const shimmer = ctx.createLinearGradient(0, scanY, 0, scanY + 7);
      shimmer.addColorStop(0,   'rgba(255,255,255,0)');
      shimmer.addColorStop(0.5, 'rgba(255,255,255,0.14)');
      shimmer.addColorStop(1,   'rgba(255,255,255,0)');
      ctx.save();
      ctx.beginPath(); ctx.arc(cx, cy, 32, 0, 2 * Math.PI); ctx.clip();
      ctx.fillStyle = shimmer;
      ctx.fillRect(cx - 34, scanY, 68, 7);
      ctx.restore();

      // ── Layer 8: importance badge — anti-phase pulse to halo ──────
      const bPulse = 0.5 + 0.5 * Math.sin(t * 0.00125 + ph + Math.PI); // inverted
      const bx = cx + 19, by = cy + 19;
      ctx.beginPath(); ctx.arc(bx, by, 10, 0, 2 * Math.PI);
      ctx.fillStyle = 'rgba(8,6,18,0.94)'; ctx.fill();
      ctx.strokeStyle = 'rgba(' + r + ',' + g + ',' + b + ',' + (0.38 + bPulse * 0.52).toFixed(3) + ')';
      ctx.lineWidth = 1.2; ctx.stroke();
      ctx.font = '700 9px "DM Mono", monospace';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillStyle = col;
      ctx.shadowColor = col; ctx.shadowBlur = 4 * bPulse;
      ctx.fillText(String(imp), bx, by + 0.5);
      ctx.shadowBlur = 0;
    };

    n.__drawNode(0);
    const tex = new THREE.CanvasTexture(canvas);
    const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false });
    const sp  = new THREE.Sprite(mat);
    const s = 4 + n.importance * 1.6;
    sp.scale.set(s, s, 1);
    n.__sprite = sp;
    n.__canvas = canvas;
    n.__ctx    = ctx;
    n.__tex    = tex;
    return sp;
  })
  .nodeThreeObjectExtend(false)
  .linkSource('source').linkTarget('target')
  .linkColor(l => {
    // Aurora HSL — interpolate between source and target node hues
    const srcCol = (l.source && l.source.color) ? l.source.color : '#67E8F9';
    const tgtCol = (l.target && l.target.color) ? l.target.color : '#C084FC';
    const t = Math.min(1, Math.max(0, (l.similarity - 0.70) / 0.25));
    const sr = parseInt(srcCol.slice(1,3),16), sg = parseInt(srcCol.slice(3,5),16), sb = parseInt(srcCol.slice(5,7),16);
    const tr = parseInt(tgtCol.slice(1,3),16), tg = parseInt(tgtCol.slice(3,5),16), tb = parseInt(tgtCol.slice(5,7),16);
    const ri = Math.round(sr + t*(tr-sr));
    const gi = Math.round(sg + t*(tg-sg));
    const bi = Math.round(sb + t*(tb-sb));
    const alpha = (0.10 + t * 0.55).toFixed(2);
    return 'rgba('+ri+','+gi+','+bi+','+alpha+')';
  })
  .linkWidth(l => 0.15 + (l.similarity - 0.70) * 3.5)
  .linkOpacity(0.65)
  .linkDirectionalParticles(l => l.similarity > 0.90 ? 5 : l.similarity > 0.82 ? 3 : l.similarity > 0.76 ? 1 : 0)
  .linkDirectionalParticleWidth(l => l.similarity > 0.90 ? 1.8 : 1.2)
  .linkDirectionalParticleColor(l => {
    const col = (l.source && l.source.color) ? l.source.color : '#C084FC';
    return col;
  })
  .linkDirectionalParticleSpeed(0.004)
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

// ── Sprite animation loop — 30fps, batch round-robin ─────────────────────────
(function plasmaLoop() {
  let lastT = 0, batchIdx = 0;
  const BATCH = 30;
  function tick(t) {
    if (t - lastT >= 33) {   // ~30fps
      lastT = t;
      const nodes = Graph.graphData ? Graph.graphData().nodes : [];
      const total = nodes.length;
      if (total > 0) {
        for (let i = 0; i < Math.min(BATCH, total); i++) {
          const n = nodes[(batchIdx + i) % total];
          if (n.__drawNode && n.__tex) {
            n.__drawNode(t);
            n.__tex.needsUpdate = true;
          }
        }
        batchIdx = (batchIdx + BATCH) % total;
      }
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
})();

// Bloom post-processing
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
    // Intercept 3d-force-graph's per-frame render call — bloom only
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
      const sseLabel = document.getElementById('hud-sse');
      if (sseLabel) { sseLabel.textContent = 'live'; sseLabel.style.color = '#06d6a0'; }
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
      LIVE_DOT.style.background = '#f59e0b';
      LIVE_DOT.title = 'SSE offline \u2014 start NEMO server to enable live feed';
      const sseLabel2 = document.getElementById('hud-sse');
      if (sseLabel2) { sseLabel2.textContent = 'offline'; sseLabel2.style.color = '#f59e0b'; }
      es.close();
      setTimeout(connectSSE, 8000);
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
