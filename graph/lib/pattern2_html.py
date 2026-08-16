"""Pattern 2 — Neo4j Explore/Bloom 스크린샷 스타일 (작은 점·곡선 엣지·플로팅 검색/범례)."""

from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
from typing import Any

import networkx as nx

from .ask_panel import ASK_PANEL_CSS, ASK_PANEL_HTML, ASK_PANEL_JS

# Neo4j Explore 스크린샷에 가까운 타입 팔레트
GROUP_COLORS = [
    "#E85D75",  # Person-like coral
    "#A78BFA",  # Event purple
    "#2DD4BF",  # Organization teal
    "#38BDF8",  # Channel cyan
    "#4ADE80",  # Project green
    "#C084FC",  # Product lavender
    "#60A5FA",  # Creative Work blue
    "#F472B6",  # Web Page pink
    "#FBBF24",  # Defined Term gold
    "#F87171",  # Action red
    "#94A3B8",
    "#FB923C",
    "#34D399",
    "#818CF8",
    "#F0ABFC",
]


def _wrap_label(text: str, width: int = 16) -> str:
    text = (text or "").strip() or "(unnamed)"
    if len(text) <= width:
        return text
    parts: list[str] = []
    buf = ""
    for token in re.split(r"(\s+)", text):
        if len(buf) + len(token) > width and buf:
            parts.append(buf.strip())
            buf = token.lstrip()
        else:
            buf += token
    if buf.strip():
        parts.append(buf.strip())
    if not parts:
        parts = [text[:width]]
    return "\n".join(parts[:4])


def _infer_community_labels(
    G: nx.Graph,
    communities: dict[int, list[str]],
) -> dict[int, str]:
    labels: dict[int, str] = {}
    degree = dict(G.degree())
    for cid, members in communities.items():
        ranked = sorted(members, key=lambda n: degree.get(n, 0), reverse=True)
        top = ""
        for nid in ranked[:1]:
            lab = str(G.nodes[nid].get("label") or nid)
            lab = re.sub(r"\s+", " ", lab).strip()
            top = lab[:32]
        labels[cid] = top if top else f"Group {cid}"
    return labels


def _node_description(G: nx.Graph, node_id: str) -> str:
    data = G.nodes[node_id]
    lines: list[str] = []
    src = data.get("source_file") or ""
    if src:
        lines.append(f"출처: {Path(str(src)).name}")
    captured = data.get("captured_at") or ""
    if captured:
        lines.append(f"시각: {captured}")
    author = data.get("author") or ""
    if author:
        lines.append(f"사용자: {author}")

    rels: list[str] = []
    for _, nbr, edata in G.edges(node_id, data=True):
        rel = edata.get("relation") or "related"
        conf = edata.get("confidence") or ""
        nbr_label = G.nodes[nbr].get("label") or nbr
        tag = f"{rel}"
        if conf and conf != "EXTRACTED":
            tag += f" [{conf}]"
        rels.append(f"→ {tag} → {nbr_label}")
    if rels:
        lines.append("관계:")
        lines.extend(rels[:8])
        if len(rels) > 8:
            lines.append(f"… 외 {len(rels) - 8}개")
    return "\n".join(lines) if lines else "관련 설명이 없습니다."


def to_pattern2_html(
    G: nx.Graph,
    communities: dict[int, list[str]],
    output_path: str | Path,
    *,
    title: str,
    subtitle: str | None = None,
    community_labels: dict[int, str] | None = None,
    query_url: str = "/api/graph/query",
) -> None:
    """Write Neo4j Explore/Bloom-style interactive knowledge graph HTML."""
    community_labels = community_labels or _infer_community_labels(G, communities)
    node_community = {
        nid: cid for cid, members in communities.items() for nid in members
    }
    degree = dict(G.degree())

    raw_nodes: list[dict[str, Any]] = []
    descriptions: dict[str, str] = {}
    for nid, data in G.nodes(data=True):
        cid = int(node_community.get(nid, 0))
        color = GROUP_COLORS[cid % len(GROUP_COLORS)]
        deg = degree.get(nid, 1)
        label = str(data.get("label") or nid)
        raw_nodes.append(
            {
                "id": nid,
                "label": _wrap_label(label),
                "group": str(cid),
                "color": color,
                "degree": deg,
            }
        )
        descriptions[nid] = _node_description(G, nid)

    hub = max(G.nodes, key=lambda n: degree.get(n, 0)) if G.number_of_nodes() else None

    raw_edges: list[dict[str, Any]] = []
    for u, v, data in G.edges(data=True):
        src = data.get("_src") or u
        tgt = data.get("_tgt") or v
        if src not in G or tgt not in G:
            src, tgt = u, v
        conf = data.get("confidence") or "EXTRACTED"
        raw_edges.append(
            {
                "from": src,
                "to": tgt,
                "label": data.get("relation") or "",
                "confidence": conf,
            }
        )

    legend_items = []
    for cid in sorted(communities.keys(), key=lambda c: -len(communities[c])):
        legend_items.append(
            {
                "id": str(cid),
                "label": community_labels.get(cid, f"Group {cid}"),
                "color": GROUP_COLORS[cid % len(GROUP_COLORS)],
                "count": len(communities[cid]),
            }
        )

    subtitle = subtitle or (
        "Neo4j Explore style · click a node for details"
    )

    payload = {
        "title": title,
        "subtitle": subtitle,
        "nodes": len(raw_nodes),
        "edges": len(raw_edges),
        "groups": len(communities),
        "hub": hub,
        "rawNodes": raw_nodes,
        "rawEdges": raw_edges,
        "descriptions": descriptions,
        "legend": legend_items,
    }

    html_doc = _render_template(payload, query_url=query_url or "/api/graph/query")
    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_text(html_doc, encoding="utf-8")
    os.replace(tmp, dest)


def _render_template(payload: dict[str, Any], *, query_url: str = "/api/graph/query") -> str:
    title = html.escape(payload["title"])
    data_json = json.dumps(
        {
            "hub": payload["hub"],
            "rawNodes": payload["rawNodes"],
            "rawEdges": payload["rawEdges"],
            "descriptions": payload["descriptions"],
            "legend": payload["legend"],
        },
        ensure_ascii=False,
    )
    data_json = data_json.replace("</", "<\\/")

    doc = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{
    height: 100%;
    overflow: hidden;
    background: #151922;
    color: #e8eaed;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    color-scheme: dark;
  }}

  #network-container {{
    position: relative;
    width: 100%;
    height: 100%;
    background: #151922;
    outline: none;
  }}
  #mynetwork {{
    width: 100%;
    height: 100%;
    outline: none;
  }}
  #mynetwork .vis-network,
  #mynetwork canvas {{
    outline: none !important;
  }}

  .search-panel {{
    position: absolute;
    top: 18px;
    left: 18px;
    z-index: 20;
    width: min(315px, calc(100vw - 36px));
  }}
  .search-box {{
    display: flex;
    align-items: center;
    gap: 10px;
    background: rgba(28, 33, 44, 0.94);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 10px 14px;
    box-shadow: 0 8px 28px rgba(0,0,0,0.35);
  }}
  .search-box svg {{
    width: 18px;
    height: 18px;
    color: #9aa3b2;
    flex-shrink: 0;
  }}
  #search {{
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    color: #e8eaed;
    font-size: 14px;
  }}
  #search::placeholder {{ color: #7d8696; }}

  .legend-panel {{
    position: absolute;
    left: 18px;
    bottom: 18px;
    z-index: 20;
    width: min(280px, calc(100vw - 36px));
    max-height: min(52vh, 420px);
    display: flex;
    flex-direction: column;
    background: rgba(28, 33, 44, 0.94);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    box-shadow: 0 10px 36px rgba(0,0,0,0.4);
    overflow: hidden;
    transition: opacity 0.15s ease, transform 0.15s ease;
  }}
  .legend-panel.is-hidden {{
    opacity: 0;
    pointer-events: none;
    transform: translateY(8px);
  }}
  #legend {{
    overflow-y: auto;
    padding: 10px 8px 4px;
    scrollbar-width: thin;
    scrollbar-color: rgba(255,255,255,0.2) transparent;
  }}
  .legend-item {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 7px 10px;
    border-radius: 8px;
    cursor: pointer;
  }}
  .legend-item:hover {{ background: rgba(255,255,255,0.06); }}
  .legend-item.active {{ background: rgba(255,255,255,0.08); }}
  .legend-dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }}
  .legend-label {{
    flex: 1;
    min-width: 0;
    font-size: 13px;
    color: #e8eaed;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}
  .legend-count {{
    font-size: 12px;
    color: #8b93a3;
    font-variant-numeric: tabular-nums;
  }}
  .browse-all {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 18px;
    border-top: 1px solid rgba(255,255,255,0.08);
    color: #cfd5df;
    font-size: 13px;
    cursor: pointer;
    background: transparent;
    border-left: none;
    border-right: none;
    border-bottom: none;
    width: 100%;
    text-align: left;
  }}
  .browse-all:hover {{ background: rgba(255,255,255,0.05); }}
  .browse-all svg {{
    width: 16px;
    height: 16px;
    color: #9aa3b2;
  }}

  #node-detail {{
    position: absolute;
    top: 18px;
    right: 18px;
    z-index: 20;
    width: min(300px, calc(100vw - 36px));
    background: rgba(28, 33, 44, 0.96);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 14px 16px;
    box-shadow: 0 10px 36px rgba(0,0,0,0.4);
    display: none;
  }}
  #node-detail .node-type {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 11px;
    margin-bottom: 8px;
  }}
  #node-detail h3 {{
    font-size: 15px;
    font-weight: 600;
    color: #f3f4f6;
    margin-bottom: 8px;
  }}
  #node-detail p {{
    font-size: 12px;
    color: #9aa3b2;
    line-height: 1.55;
    white-space: pre-wrap;
  }}
  #detail-close {{
    position: absolute;
    top: 10px;
    right: 12px;
    background: transparent;
    border: none;
    color: #8b93a3;
    font-size: 18px;
    cursor: pointer;
    line-height: 1;
  }}

  .controls {{
    position: absolute;
    right: 18px;
    bottom: 18px;
    z-index: 20;
    display: flex;
    flex-direction: column;
    gap: 8px;
    align-items: flex-end;
    pointer-events: auto;
  }}
  .controls-row {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    justify-content: flex-end;
  }}
  .ctrl-btn {{
    background: rgba(28, 33, 44, 0.94);
    border: 1px solid rgba(255,255,255,0.1);
    color: #e8eaed;
    padding: 8px 12px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 12px;
    box-shadow: 0 6px 18px rgba(0,0,0,0.28);
  }}
  .ctrl-btn:hover {{ border-color: rgba(255,255,255,0.22); background: rgba(40,46,60,0.96); }}
  .ctrl-btn.active {{
    background: #3b82f6;
    border-color: #3b82f6;
    color: #fff;
    font-weight: 650;
  }}
  .ctrl-btn.pattern-btn.active {{
    background: #3b82f6;
    border-color: #3b82f6;
    color: #fff;
    font-weight: 650;
  }}
  .ctrl-btn:disabled {{ opacity: 0.55; cursor: wait; }}
<<<ASK_PANEL_CSS>>>
</style>
</head>
<body>
<div id="network-container">
  <div id="mynetwork"></div>

  <div class="search-panel">
    <div class="search-box">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="11" cy="11" r="7"/>
        <path d="m20 20-3.5-3.5"/>
      </svg>
      <input id="search" type="search" placeholder="Search entities..." autocomplete="off" data-doc-search="1">
      <button type="button" class="ask-close" aria-label="닫기" onclick="closeAskPanel()">×</button>
    </div>
<<<ASK_PANEL_HTML>>>
  </div>

  <div id="node-detail">
    <button type="button" id="detail-close" aria-label="닫기" onclick="hideDetail()">×</button>
    <div class="node-type" id="detail-type"></div>
    <h3 id="detail-title"></h3>
    <p id="detail-desc"></p>
  </div>

  <div class="legend-panel">
    <div id="legend"></div>
    <button type="button" class="browse-all" onclick="filterGroup(null)">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
        <path d="M4 7h16M4 12h16M4 17h16"/>
      </svg>
      Browse all
    </button>
  </div>

  <div class="controls">
    <div class="controls-row">
      <button type="button" class="ctrl-btn pattern-btn" data-pattern="pattern1" onclick="selectPattern('pattern1')" title="Force Atlas">Force Atlas</button>
      <button type="button" class="ctrl-btn pattern-btn active" data-pattern="pattern2" onclick="selectPattern('pattern2')" title="Neo4j Explore (현재)">Neo4j Explore</button>
      <button type="button" class="ctrl-btn pattern-btn" data-pattern="pattern3" onclick="selectPattern('pattern3')" title="Holistic View">Holistic View</button>
    </div>
    <div class="controls-row">
      <button type="button" class="ctrl-btn" id="fit-view-btn" onclick="fitView()">전체 보기</button>
      <button type="button" class="ctrl-btn" onclick="stabilize()">레이아웃 재정렬</button>
      <button type="button" class="ctrl-btn" id="legend-toggle-btn" onclick="toggleLegend()">범례 숨기기</button>
      <button type="button" class="ctrl-btn" id="isolate-toggle-btn" onclick="toggleIsolates()" title="연결(edge)이 없는 노드 표시/숨기기">고립 숨기기</button>
      <button type="button" class="ctrl-btn" onclick="filterGroup(null)">필터 해제</button>
    </div>
  </div>
</div>

<script>
const DATA = {data_json};
const rawNodes = DATA.rawNodes;
const rawEdges = DATA.rawEdges;
const nodeDescriptions = DATA.descriptions;
const legend = DATA.legend;
let activeGroup = null;
let legendHidden = false;
let hideIsolates = false;
const isolateCount = rawNodes.filter(n => (n.degree || 0) === 0).length;

function lightenColor(hex, factor) {{
  const r = Math.min(255, Math.floor(parseInt(hex.slice(1,3), 16) + 255 * factor));
  const g = Math.min(255, Math.floor(parseInt(hex.slice(3,5), 16) + 255 * factor));
  const b = Math.min(255, Math.floor(parseInt(hex.slice(5,7), 16) + 255 * factor));
  return `rgb(${{r}},${{g}},${{b}})`;
}}

function hideDetail() {{
  document.getElementById('node-detail').style.display = 'none';
}}

function syncLegendToggleLabel() {{
  const btn = document.getElementById('legend-toggle-btn');
  if (btn) btn.textContent = legendHidden ? '범례 보이기' : '범례 숨기기';
}}

function toggleLegend(force) {{
  const panel = document.querySelector('.legend-panel');
  if (!panel) return;
  legendHidden = typeof force === 'boolean' ? force : !legendHidden;
  panel.classList.toggle('is-hidden', legendHidden);
  syncLegendToggleLabel();
}}

function syncIsolateToggleLabel() {{
  const btn = document.getElementById('isolate-toggle-btn');
  if (!btn) return;
  if (isolateCount === 0) {{
    btn.disabled = true;
    btn.classList.remove('active');
    btn.textContent = '고립 없음';
    btn.title = '연결 없는 노드가 없습니다';
    return;
  }}
  btn.disabled = false;
  btn.classList.toggle('active', hideIsolates);
  btn.textContent = hideIsolates
    ? `고립 보이기 (${{isolateCount}})`
    : `고립 숨기기 (${{isolateCount}})`;
  btn.title = hideIsolates
    ? '연결 없는 노드를 다시 표시'
    : '연결(edge)이 없는 노드 숨기기';
}}

function applyNodeVisibility() {{
  if (typeof networkData === 'undefined' || !networkData) return;
  networkData.nodes.update(rawNodes.map(n => {{
    const isolated = (n.degree || 0) === 0;
    const hidden = hideIsolates && isolated;
    let opacity = 1;
    if (!hidden && activeGroup) {{
      opacity = n.group === activeGroup ? 1 : 0.08;
    }}
    return {{ id: n.id, hidden: !!hidden, opacity: hidden ? 0 : opacity }};
  }}));
}}

function toggleIsolates() {{
  if (isolateCount === 0) return;
  hideIsolates = !hideIsolates;
  syncIsolateToggleLabel();
  applyNodeVisibility();
  if (hideIsolates && network) {{
    stabilize();
  }} else if (network) {{
    try {{ network.fit({{ animation: {{ duration: 400 }} }}); }} catch (e) {{}}
  }}
}}

const NODE_COUNT = rawNodes.length;
const SMALL_GRAPH = NODE_COUNT < 120;
const SPARSE_GRAPH = isolateCount / Math.max(NODE_COUNT, 1) >= 0.2;
const STAB_ITERS = SMALL_GRAPH ? 260 : Math.min(480, 200 + Math.floor(NODE_COUNT / 2));
const LIVE_SETTLE_MS = SPARSE_GRAPH ? 5500 : (SMALL_GRAPH ? 4500 : 5000);
let network = null;
let settleGen = 0;
let settleTimer = null;

const PHYSICS_BASE = {{
  enabled: true,
  solver: 'barnesHut',
  barnesHut: SMALL_GRAPH ? {{
    gravitationalConstant: -3200,
    centralGravity: 0.05,
    springLength: 120,
    springConstant: 0.04,
    damping: 0.4,
    avoidOverlap: 0.35
  }} : {{
    gravitationalConstant: -14000,
    centralGravity: 0.12,
    springLength: 85,
    springConstant: 0.03,
    damping: 0.45,
    avoidOverlap: 0.12
  }},
  stabilization: {{
    enabled: false,
    iterations: STAB_ITERS,
    updateInterval: 25,
    fit: false
  }}
}};


function physicsForLiveSettle() {{
  // Always re-apply this pattern's own solver (FA / Barnes-Hut / Holistic).
  // Do not swap Force Atlas → Barnes-Hut on sparse graphs — that flattens the
  // circular FA layout into separate islands. Label crashes were a separate bug
  // (safeVisLabel); physics should stay true to the selected pattern.
  return Object.assign({{}}, PHYSICS_BASE, {{
    enabled: true,
    stabilization: Object.assign({{}}, PHYSICS_BASE.stabilization || {{}}, {{ enabled: false }})
  }});
}}


function safeVisLabel(s) {{
  // vis-network LabelSplitter builds RegExp from label tokens. Unescaped
  // "(" in labels like "(INVERTER & SYSTEM MENUS)" throws
  // "Invalid regular expression: Unterminated group" and breaks layout.
  return String(s == null ? '' : s)
    .split('\\n').join(' ')
    .split('(').join('\\uFF08')
    .split(')').join('\\uFF09')
    .split('[').join('\\uFF3B')
    .split(']').join('\\uFF3D');
}}

function graphDbg(tag, extra) {{
  try {{
    const el = document.getElementById('mynetwork');
    const payload = Object.assign({{
      tag,
      t: Date.now(),
      hasNetwork: !!network,
      settleGen,
      settleTimer: !!settleTimer,
      nodeCount: typeof rawNodes !== 'undefined' ? rawNodes.length : null,
      isolateCount: typeof isolateCount !== 'undefined' ? isolateCount : null,
      sparse: typeof SPARSE_GRAPH !== 'undefined' ? SPARSE_GRAPH : null,
      canvas: el ? {{ w: el.clientWidth, h: el.clientHeight }} : null,
      scale: (network && network.getScale) ? network.getScale() : null
    }}, extra || {{}});
    console.log('[graph-ctrl]', payload);
  }} catch (err) {{
    console.warn('[graph-ctrl] log failed', tag, err);
  }}
}}





function stopPhysics() {{
  graphDbg('stopPhysics');
  if (!network) return;
  try {{ network.stopSimulation(); }} catch (e) {{}}
  network.setOptions({{
    physics: {{ enabled: false, stabilization: {{ enabled: false }} }}
  }});
}}

function whenCanvasReady(fn) {{
  let tries = 0;
  const tick = () => {{
    const el = document.getElementById('mynetwork');
    const w = el ? el.clientWidth : 0;
    const h = el ? el.clientHeight : 0;
    if (w >= 60 && h >= 60) {{
      fn();
      return;
    }}
    if (tries++ < 80) {{
      setTimeout(tick, 40);
      return;
    }}
    fn();
  }};
  requestAnimationFrame(tick);
}}

function fitView() {{
  graphDbg('fitView:click');
  if (!network) {{
    graphDbg('fitView:abort', {{ reason: 'no-network' }});
    return;
  }}
  cancelSettle();
  stopPhysics();
  const doFit = (phase) => {{
    try {{
      const before = network.getScale();
      network.redraw();
      // Prefer a hard fit first — animated fit is a no-op when the camera
      // already matches a huge isolate cloud (common on wiki graphs).
      network.fit({{ animation: false, padding: 56 }});
      let scale = network.getScale();
      if (!Number.isFinite(scale) || scale < 0.04 || scale > 8) {{
        network.moveTo({{ scale: 0.45, position: {{ x: 0, y: 0 }}, animation: false }});
        scale = network.getScale();
      }}
      network.fit({{
        animation: {{ duration: 400, easingFunction: 'easeInOutQuad' }},
        padding: 56
      }});
      graphDbg('fitView:done', {{ phase: phase || 'direct', before, after: network.getScale() }});
    }} catch (e) {{
      graphDbg('fitView:error', {{ phase: phase || 'direct', error: String(e) }});
      console.error('[graph-ctrl] fitView error', e);
    }}
  }};
  doFit('immediate');
  whenCanvasReady(() => doFit('whenCanvasReady'));
}}

function seedLayout(nodes) {{
  // Random seed (not a circle) — circular seed + short stabilize freezes a hairball.
  const spread = Math.max(520, Math.sqrt(nodes.length) * 95);
  nodes.forEach((n) => {{
    n.x = (Math.random() - 0.5) * spread * 2;
    n.y = (Math.random() - 0.5) * spread * 2;
    n.fixed = false;
  }});
}}

function markLegendActive(group) {{
  document.querySelectorAll('.legend-item').forEach(el => {{
    el.classList.toggle('active', group != null && el.dataset.group === String(group));
  }});
}}

const legendEl = document.getElementById('legend');
legend.forEach(item => {{
  const div = document.createElement('div');
  div.className = 'legend-item';
  div.dataset.group = item.id;
  div.onclick = () => filterGroup(item.id);
  div.innerHTML = `<div class="legend-dot" style="background:${{item.color}}"></div>` +
    `<span class="legend-label" title="${{item.label}}">${{item.label}}</span>` +
    `<span class="legend-count">${{item.count}}</span>`;
  legendEl.appendChild(div);
}});

const maxDeg = Math.max(...rawNodes.map(n => n.degree || 1), 1);
const labelFloor = Math.max(2, maxDeg * 0.2);
const visNodes = rawNodes.map(n => {{
  const showLabel = (n.degree || 1) >= labelFloor;
  const name = (n.label || '').replace(/\\n/g, ' ').trim();
  const short = name.length > 34 ? name.slice(0, 33) + '…' : name;
  return {{
    id: n.id,
    label: showLabel ? safeVisLabel(short) : '',
    group: n.group,
    size: 4.2 + 2.8 * ((n.degree || 1) / maxDeg),
    color: {{
      background: n.color,
      border: n.color,
      highlight: {{ background: lightenColor(n.color, 0.2), border: lightenColor(n.color, 0.2) }},
      hover: {{ background: lightenColor(n.color, 0.12), border: lightenColor(n.color, 0.12) }}
    }},
    font: {{
      color: '#f5f7fa',
      size: showLabel ? 12 : 0,
      face: 'Segoe UI',
      strokeWidth: 3,
      strokeColor: 'rgba(21,25,34,0.85)',
      align: 'right',
      vadjust: -1
    }},
    shadow: false,
    borderWidth: 0,
    shape: 'dot',
    title: name
  }};
}});

const visEdges = rawEdges.map((e, i) => ({{
  id: i,
  from: e.from,
  to: e.to,
  label: '',
  color: {{
    color: 'rgba(170, 178, 192, 0.28)',
    highlight: 'rgba(210, 216, 228, 0.65)',
    hover: 'rgba(210, 216, 228, 0.5)'
  }},
  dashes: false,
  arrows: {{ to: {{ enabled: false }} }},
  font: {{ size: 0 }},
  width: 0.55,
  selectionWidth: 1.2,
  smooth: {{ type: 'continuous', roundness: 0.45 }},
  title: e.label + (e.confidence ? ` [${{e.confidence}}]` : '')
}}));
seedLayout(visNodes);

const container = document.getElementById('mynetwork');
const networkData = {{
  nodes: new vis.DataSet(visNodes),
  edges: new vis.DataSet(visEdges)
}};

const options = {{
  groups: {{ useDefaultGroups: false }},
  nodes: {{
    shape: 'dot',
    scaling: {{ min: 4, max: 12 }}
  }},
  edges: {{
    smooth: {{ type: 'continuous', roundness: 0.45 }}
  }},
  // Prefer sparse settle solver when present; else Neo4j barnesHut base.
  physics: PHYSICS_BASE,
  interaction: {{
    hover: true,
    tooltipDelay: 100,
    zoomView: true,
    dragView: true,
    hideEdgesOnDrag: false,
    keyboard: {{ enabled: true, bindToWindow: false }}
  }},
  layout: {{ improvedLayout: false }}
}};

network = new vis.Network(container, networkData, options);
container.setAttribute('tabindex', '0');
document.getElementById('fit-view-btn').addEventListener('click', (ev) => {{
  graphDbg('fit-view-btn:listener');
  ev.preventDefault();
  fitView();
}});

network.on('click', function(params) {{
  if (params.nodes.length === 0) {{
    hideDetail();
    // empty canvas (not an edge hit): toggle legend visibility
    if (params.edges.length === 0) toggleLegend();
    return;
  }}
  const nodeId = params.nodes[0];
  const node = rawNodes.find(n => n.id === nodeId);
  if (!node) return;
  const leg = legend.find(l => l.id === node.group);
  const detail = document.getElementById('node-detail');
  const typeEl = document.getElementById('detail-type');
  const titleEl = document.getElementById('detail-title');
  const descEl = document.getElementById('detail-desc');

  typeEl.textContent = leg ? leg.label : (`Group ${{node.group}}`);
  typeEl.style.background = node.color + '33';
  typeEl.style.color = node.color;
  typeEl.style.border = `1px solid ${{node.color}}66`;
  titleEl.textContent = node.label.replace(/\\n/g, ' ');
  descEl.textContent = nodeDescriptions[nodeId] || '관련 설명이 없습니다.';
  detail.style.display = 'block';
}});

network.on('hoverNode', () => {{ container.style.cursor = 'pointer'; }});
network.on('blurNode', () => {{ container.style.cursor = 'default'; }});

function finishInitialLayout() {{
  if (DATA.hub) {{
    network.focus(DATA.hub, {{ scale: 0.9, animation: {{ duration: 700 }} }});
  }} else {{
    network.fit({{ animation: {{ duration: 500 }} }});
  }}
}}

function cancelSettle() {{
  const prev = settleGen;
  settleGen += 1;
  if (settleTimer) {{
    clearTimeout(settleTimer);
    settleTimer = null;
  }}
  graphDbg('cancelSettle', {{ prevGen: prev, nextGen: settleGen }});
}}

function beginLiveSettle(onDone) {{
  if (!network) {{
    graphDbg('beginLiveSettle:abort', {{ reason: 'no-network' }});
    return;
  }}
  cancelSettle();
  const gen = settleGen;
  const phys = physicsForLiveSettle();
  graphDbg('beginLiveSettle:start', {{
    gen,
    ms: LIVE_SETTLE_MS,
    solver: phys && phys.solver,
    sparseGraph: !!SPARSE_GRAPH
  }});
  network.setOptions({{
    groups: {{ useDefaultGroups: false }},
    layout: {{ improvedLayout: false }},
    physics: phys
  }});
  try {{ network.startSimulation(); }} catch (e) {{
    graphDbg('beginLiveSettle:startSimulation-error', {{ error: String(e) }});
    console.error('[graph-ctrl] startSimulation', e);
  }}
  // Time-box only — do not use 'stabilized' (fires too early on sparse graphs).
  settleTimer = setTimeout(() => {{
    if (gen !== settleGen) {{
      graphDbg('beginLiveSettle:skip-stale', {{ gen, settleGen }});
      return;
    }}
    settleTimer = null;
    graphDbg('beginLiveSettle:timeout-done', {{ gen }});
    stopPhysics();
    if (typeof onDone === 'function') onDone();
  }}, LIVE_SETTLE_MS);
}}

// User rearrange: live settle (visible). Batch network.stabilize() freezes/no-ops
// on Force Atlas + sparse wiki graphs; Neo4j barnesHut hid the bug.
function runBatchStabilize(onDone) {{
  beginLiveSettle(onDone);
}}

beginLiveSettle(() => {{
  whenCanvasReady(() => {{
    try {{
      if (DATA.hub) {{
        network.focus(DATA.hub, {{ scale: 0.85, animation: {{ duration: 700 }} }});
      }} else {{
        network.fit({{ animation: {{ duration: 600 }} }});
      }}
    }} catch (e) {{}}
  }});
}});

function filterGroup(group) {{
  activeGroup = group;
  markLegendActive(group);
  applyNodeVisibility();
}}

function stabilize() {{
  graphDbg('stabilize:click');
  if (!network || typeof networkData === 'undefined') {{
    graphDbg('stabilize:abort', {{ reason: !network ? 'no-network' : 'no-networkData' }});
    return;
  }}
  const spread = Math.max(900, Math.sqrt(rawNodes.length) * 200);
  const beforeScale = network.getScale();
  networkData.nodes.update(rawNodes.map(n => ({{
    id: n.id,
    x: (Math.random() - 0.5) * spread,
    y: (Math.random() - 0.5) * spread,
    fixed: false
  }})));
  applyNodeVisibility();
  graphDbg('stabilize:reseeded', {{ spread, beforeScale }});
  runBatchStabilize(() => {{
    whenCanvasReady(() => {{
      try {{
        network.fit({{ animation: false, padding: 56 }});
        network.fit({{ animation: {{ duration: 500 }} }});
        graphDbg('stabilize:fit-done', {{ afterScale: network.getScale() }});
      }} catch (e) {{
        graphDbg('stabilize:fit-error', {{ error: String(e) }});
        console.error('[graph-ctrl] stabilize fit', e);
      }}
    }});
  }});
}}


function selectPattern(pattern) {{
  pattern = String(pattern || '');
  if (pattern !== 'pattern1' && pattern !== 'pattern2' && pattern !== 'pattern3') return;
  if (pattern === 'pattern2') return;
  document.querySelectorAll('.pattern-btn').forEach(btn => {{ btn.disabled = true; }});
  if (window.parent && window.parent !== window) {{
    window.parent.postMessage({{ type: 'graph-pattern', pattern }}, '*');
  }}
  // If parent fails to reload (network/API hang), unlock buttons again.
  setTimeout(() => {{
    document.querySelectorAll('.pattern-btn').forEach(btn => {{ btn.disabled = false; }});
  }}, 15000);
}}

syncIsolateToggleLabel();
graphDbg('boot', {{
  pattern: document.querySelector('.pattern-btn.active')?.dataset?.pattern || null,
  liveMs: typeof LIVE_SETTLE_MS !== 'undefined' ? LIVE_SETTLE_MS : null,
  settleSolver: PHYSICS_BASE && PHYSICS_BASE.solver
}});

<<<ASK_PANEL_JS>>>
</script>
</body>
</html>
"""
    return (
        doc.replace("<<<ASK_PANEL_CSS>>>", ASK_PANEL_CSS)
        .replace("<<<ASK_PANEL_HTML>>>", ASK_PANEL_HTML)
        .replace("<<<ASK_PANEL_JS>>>", ASK_PANEL_JS)
        .replace("<<<GRAPH_QUERY_URL>>>", query_url or "/api/graph/query")
    )
