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
    --bg:        #03050d;
    --surface:   rgba(8, 14, 30, 0.85);
    --border:    rgba(0, 180, 216, 0.18);
    --accent:    #00b4d8;
    --accent2:   #ff9f1c;
    --text:      #ccd6f6;
    --muted:     #6a80a7;
    --panel-w:   320px;
  }

  html, body {
    width: 100%; height: 100%;
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, sans-serif;
    overflow: hidden;
  }

  #starfield { position: fixed; inset: 0; z-index: 0; pointer-events: none; }
  #graph-root { position: fixed; inset: 0; z-index: 1; }
  #graph-root canvas { display: block; }

  /* ── Top HUD ── */
  #hud {
    position: fixed; top: 0; left: 0; right: 0; z-index: 10;
    display: flex; align-items: center; gap: 18px;
    padding: 12px 22px;
    background: var(--surface);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border);
    animation: slideDown 0.5s ease;
  }
  @keyframes slideDown { from { transform: translateY(-100%); opacity:0; } to { transform: none; opacity:1; } }
  #hud-title {
    font-size: 17px; font-weight: 700; letter-spacing: 2px;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    text-transform: uppercase;
  }
  #hud-stats { font-size: 12px; color: var(--muted); letter-spacing: 0.5px; }
  #hud-pulse {
    width: 8px; height: 8px; border-radius: 50%; background: #06d6a0; flex-shrink: 0;
    animation: pulse 2s ease-in-out infinite;
  }
  @keyframes pulse {
    0%,100% { box-shadow: 0 0 0 0 rgba(6,214,160,0.7); }
    50%      { box-shadow: 0 0 0 7px rgba(6,214,160,0); }
  }
  #hud-spacer { flex: 1; }

  /* ── Side Panel ── */
  #panel {
    position: fixed; top: 56px; right: 0; bottom: 0; width: var(--panel-w);
    z-index: 10;
    background: var(--surface); backdrop-filter: blur(14px);
    border-left: 1px solid var(--border);
    display: flex; flex-direction: column;
    transition: transform 0.35s cubic-bezier(0.4,0,0.2,1);
  }
  #panel.collapsed { transform: translateX(var(--panel-w)); }
  #panel-toggle {
    position: absolute; left: -34px; top: 50%; transform: translateY(-50%);
    width: 34px; height: 56px;
    background: var(--surface); border: 1px solid var(--border); border-right: none;
    border-radius: 8px 0 0 8px; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    color: var(--accent); font-size: 14px; backdrop-filter: blur(14px);
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
  .leg-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; box-shadow: 0 0 5px currentColor; }
  .leg-count { margin-left: auto; font-size: 10px; color: var(--muted); }

  /* Controls */
  .ctrl-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; font-size: 12px; }
  .ctrl-row label { color: var(--muted); min-width: 100px; }
  .ctrl-row input[type=range] {
    flex: 1; -webkit-appearance: none; height: 3px; border-radius: 2px; outline: none;
    background: linear-gradient(to right, var(--accent) 0%, var(--accent) var(--pct, 0%), rgba(0,180,216,0.2) var(--pct,0%));
  }
  .ctrl-row input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none; width: 13px; height: 13px; border-radius: 50%;
    background: var(--accent); box-shadow: 0 0 6px var(--accent); cursor: pointer;
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
    background: var(--surface); backdrop-filter: blur(16px);
    border: 1px solid var(--border); border-radius: 12px;
    padding: 16px 18px; overflow-y: auto; display: none;
    animation: cardIn 0.25s ease;
  }
  @keyframes cardIn { from { opacity:0; transform: translateY(12px); } to { opacity:1; transform: none; } }
  #info-card .card-type { font-size: 10px; letter-spacing: 2px; text-transform: uppercase; font-weight: 700; margin-bottom: 6px; }
  #info-card .card-imp  { font-size: 11px; color: var(--muted); margin-bottom: 8px; }
  #info-card .card-tags { display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 10px; }
  #info-card .tag { font-size: 10px; padding: 2px 8px; border-radius: 20px; background: rgba(0,180,216,0.12); border: 1px solid rgba(0,180,216,0.25); color: var(--accent); }
  #info-card .card-content { font-size: 12px; line-height: 1.65; }
  #info-close { position: absolute; top: 10px; right: 12px; font-size: 16px; cursor: pointer; color: var(--muted); }
  #info-close:hover { color: var(--text); }
  .imp-stars { color: var(--accent2); letter-spacing: 1px; }

  /* Search */
  #search {
    background: rgba(0,0,0,0.35); color: var(--text);
    border: 1px solid var(--border); border-radius: 20px;
    padding: 5px 14px; font-size: 12px; width: 220px; outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  #search:focus { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(0,180,216,0.25); }
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

// Starfield
(function() {
  const cv = document.getElementById('starfield');
  const ctx = cv.getContext('2d');
  const stars = [];
  function resize() { cv.width = innerWidth; cv.height = innerHeight; }
  resize(); window.addEventListener('resize', resize);
  for (let i = 0; i < 220; i++) stars.push({
    x: Math.random(), y: Math.random(),
    r: Math.random() * 1.2 + 0.2,
    a: Math.random(), da: (Math.random() - 0.5) * 0.004
  });
  (function draw() {
    ctx.clearRect(0, 0, cv.width, cv.height);
    for (const s of stars) {
      s.a = Math.max(0.05, Math.min(0.9, s.a + s.da));
      if (s.a <= 0.05 || s.a >= 0.9) s.da *= -1;
      ctx.beginPath();
      ctx.arc(s.x * cv.width, s.y * cv.height, s.r, 0, 2 * Math.PI);
      ctx.fillStyle = 'rgba(180,210,255,' + s.a + ')';
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
  .backgroundColor('#03050d')
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
    const col = n.color || '#00b4d8';
    const grd = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
    grd.addColorStop(0,    col + 'ff');
    grd.addColorStop(0.35, col + 'cc');
    grd.addColorStop(0.6,  col + '44');
    grd.addColorStop(1,    col + '00');
    ctx.fillStyle = grd;
    ctx.beginPath(); ctx.arc(64, 64, 64, 0, 2 * Math.PI); ctx.fill();
    ctx.beginPath(); ctx.arc(64, 64, 13, 0, 2 * Math.PI);
    ctx.fillStyle = '#ffffff55'; ctx.fill();
    const tex = new THREE.CanvasTexture(canvas);
    const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false });
    const sp  = new THREE.Sprite(mat);
    const s = 3 + n.importance * 1.4;
    sp.scale.set(s, s, 1);
    return sp;
  })
  .nodeThreeObjectExtend(false)
  .linkSource('source').linkTarget('target')
  .linkColor(l => {
    const t = Math.min(1, Math.max(0, (l.similarity - 0.70) / 0.25));
    return 'rgba(' + Math.round(t*255) + ',' + Math.round(180-t*30) + ',' + Math.round(216-t*80) + ',' + (0.12+t*0.5).toFixed(2) + ')';
  })
  .linkWidth(l => 0.3 + (l.similarity - 0.70) * 5)
  .linkOpacity(0.6)
  .linkDirectionalParticles(l => l.similarity > 0.85 ? 2 : 0)
  .linkDirectionalParticleWidth(1.2)
  .linkDirectionalParticleColor(() => '#00b4d8')
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

// Bloom post-processing
setTimeout(() => {
  try {
    const renderer = Graph.renderer();
    const scene    = Graph.scene();
    const composer = new THREE.EffectComposer(renderer);
    composer.addPass(new THREE.RenderPass(scene, Graph.camera()));
    const bloom = new THREE.UnrealBloomPass(
      new THREE.Vector2(innerWidth, innerHeight),
      1.4,   // strength
      0.55,  // radius
      0.05   // threshold (low = most objects glow)
    );
    composer.addPass(bloom);
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

// Panel toggle
const panel = document.getElementById('panel');
document.getElementById('panel-toggle').addEventListener('click', () => {
  panel.classList.toggle('collapsed');
  document.getElementById('panel-toggle').textContent = panel.classList.contains('collapsed') ? '\u25b6' : '\u25c4';
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
