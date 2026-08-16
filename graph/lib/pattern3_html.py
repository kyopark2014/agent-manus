"""Pattern 3 — Neo4j Browser-style holistic view (어두운 배경·라벨 노드·관계 엣지·전체 fit)."""

from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
from typing import Any

import networkx as nx

from .ask_panel import ASK_PANEL_CSS, ASK_PANEL_HTML, ASK_PANEL_JS

# 밝은 배경용 파스텔 팔레트 (스크린샷의 coral / sky 톤 포함)
GROUP_COLORS = [
    "#F08080",
    "#7EB6D9",
    "#90C695",
    "#E8A87C",
    "#C39BD3",
    "#76D7C4",
    "#F5B041",
    "#85C1E9",
    "#F1948A",
    "#A9CCE3",
    "#82E0AA",
    "#D7BDE2",
    "#F9E79F",
    "#AED6F1",
    "#D5DBDB",
]


def _wrap_label(text: str, width: int = 18) -> str:
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
    return "\n".join(parts[:3])


def _infer_community_labels(
    G: nx.Graph,
    communities: dict[int, list[str]],
) -> dict[int, str]:
    labels: dict[int, str] = {}
    degree = dict(G.degree())
    for cid, members in communities.items():
        ranked = sorted(members, key=lambda n: degree.get(n, 0), reverse=True)
        top = []
        for nid in ranked[:3]:
            lab = str(G.nodes[nid].get("label") or nid)
            lab = re.sub(r"\s+", " ", lab).strip()
            if lab and lab not in top:
                top.append(lab[:28])
        labels[cid] = " · ".join(top) if top else f"그룹 {cid}"
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


def to_pattern3_html(
    G: nx.Graph,
    communities: dict[int, list[str]],
    output_path: str | Path,
    *,
    title: str,
    subtitle: str | None = None,
    community_labels: dict[int, str] | None = None,
    query_url: str = "/api/graph/query",
) -> None:
    """Write Neo4j Browser-style holistic overview HTML."""
    community_labels = community_labels or _infer_community_labels(G, communities)
    node_community = {
        nid: cid for cid, members in communities.items() for nid in members
    }
    degree = dict(G.degree())
    # Isolated nodes have degree 0 — avoid ZeroDivisionError on size scale.
    max_deg = max(degree.values()) if degree else 1
    if max_deg <= 0:
        max_deg = 1

    raw_nodes: list[dict[str, Any]] = []
    descriptions: dict[str, str] = {}
    for nid, data in G.nodes(data=True):
        cid = int(node_community.get(nid, 0))
        color = GROUP_COLORS[cid % len(GROUP_COLORS)]
        deg = degree.get(nid, 1)
        # hubs a bit larger; keep sizes moderate for dense overview
        size = 18 + 22 * (deg / max_deg)
        label = str(data.get("label") or nid)
        raw_nodes.append(
            {
                "id": nid,
                "label": _wrap_label(label),
                "group": str(cid),
                "size": round(size, 1),
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
        rel = str(data.get("relation") or "related")
        raw_edges.append(
            {
                "from": src,
                "to": tgt,
                "label": rel.upper() if rel.islower() or "_" in rel else rel,
                "dashed": conf != "EXTRACTED",
                "confidence": conf,
            }
        )

    legend_items = []
    for cid in sorted(communities.keys(), key=lambda c: -len(communities[c])):
        legend_items.append(
            {
                "id": str(cid),
                "label": community_labels.get(cid, f"그룹 {cid}"),
                "color": GROUP_COLORS[cid % len(GROUP_COLORS)],
                "count": len(communities[cid]),
            }
        )

    subtitle = subtitle or "Holistic view · relationship labels · fit entire graph"

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
    background: #0d1117;
    color: #e8eaed;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    color-scheme: dark;
  }}

  #network-container {{
    position: relative;
    width: 100%;
    height: 100%;
    background: #0d1117;
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
      <button type="button" class="ctrl-btn pattern-btn" data-pattern="pattern2" onclick="selectPattern('pattern2')" title="Neo4j Explore">Neo4j Explore</button>
      <button type="button" class="ctrl-btn pattern-btn active" data-pattern="pattern3" onclick="selectPattern('pattern3')" title="Holistic View (현재)">Holistic View</button>
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

function darkenColor(hex, factor) {{
  const r = Math.floor(parseInt(hex.slice(1,3), 16) * (1-factor));
  const g = Math.floor(parseInt(hex.slice(3,5), 16) * (1-factor));
  const b = Math.floor(parseInt(hex.slice(5,7), 16) * (1-factor));
  return `rgb(${{r}},${{g}},${{b}})`;
}}
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
      opacity = n.group === activeGroup ? 1 : 0.12;
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
const STAB_ITERS = SMALL_GRAPH ? 220 : Math.min(480, 200 + Math.floor(NODE_COUNT / 2));
const LIVE_SETTLE_MS = SPARSE_GRAPH ? 5500 : (SMALL_GRAPH ? 4500 : 5000);
let network = null;
let settleGen = 0;
let settleTimer = null;

const PHYSICS_BASE = {{
  enabled: true,
  solver: 'forceAtlas2Based',
  forceAtlas2Based: {{
    gravitationalConstant: -55,
    centralGravity: 0.008,
    springLength: 160,
    springConstant: 0.05,
    damping: 0.45,
    avoidOverlap: 0.9
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
const nCount = rawNodes.length;
const labelFloor = nCount <= 120 ? 1 : Math.max(1, maxDeg * 0.12);
const visNodes = rawNodes.map(n => {{
  const showLabel = (n.degree || 1) >= labelFloor;
  const name = (n.label || '').replace(/\\n/g, ' ').trim();
  const short = name.length > 28 ? name.slice(0, 27) + '…' : name;
  const hubish = (n.degree || 1) >= maxDeg * 0.45;
  return {{
    id: n.id,
    label: showLabel ? safeVisLabel(n.label || short) : '',
    group: n.group,
    size: n.size,
    color: {{
      background: hubish ? n.color : darkenColor(n.color, 0.08),
      border: lightenColor(n.color, 0.2),
      highlight: {{ background: lightenColor(n.color, 0.18), border: '#ffffff' }},
      hover: {{ background: lightenColor(n.color, 0.12), border: lightenColor(n.color, 0.28) }}
    }},
    font: {{
      color: '#f5f7fa',
      size: showLabel ? (hubish ? 12 : 10) : 0,
      face: 'Segoe UI',
      multi: true,
      align: 'center',
      strokeWidth: 3,
      strokeColor: 'rgba(13,17,23,0.9)',
      vadjust: 0
    }},
    shadow: {{ enabled: hubish, color: n.color + '55', size: 10, x: 0, y: 0 }},
    borderWidth: hubish ? 2.5 : 1.5,
    shape: 'ellipse',
    title: name
  }};
}});

const visEdges = rawEdges.map((e, i) => ({{
  id: i,
  from: e.from,
  to: e.to,
  label: safeVisLabel(e.label || ''),
  color: {{
    color: 'rgba(170, 178, 192, 0.45)',
    highlight: 'rgba(230, 234, 240, 0.85)',
    hover: 'rgba(210, 216, 228, 0.7)'
  }},
  dashes: e.dashed || false,
  arrows: {{ to: {{ enabled: true, scaleFactor: 0.65 }} }},
  font: {{
    size: 9,
    color: '#c8d0dc',
    align: 'middle',
    background: '#0d1117',
    strokeWidth: 0
  }},
  width: e.dashed ? 0.9 : 1.15,
  smooth: {{ type: 'dynamic', roundness: 0.3 }},
  title: e.label + (e.confidence ? ` [${{e.confidence}}]` : '')
}}));
if (true) {{
  // Always seed randomly (community ring only for small graphs previously left
  // large graphs on vis' default circle, which then froze after short stabilize).
  const groups = {{}};
  visNodes.forEach((n) => {{
    const g = n.group == null ? 0 : n.group;
    if (!groups[g]) groups[g] = [];
    groups[g].push(n);
  }});
  const keys = Object.keys(groups);
  const R = Math.max(420, Math.sqrt(visNodes.length) * 70);
  if (SMALL_GRAPH && keys.length > 1) {{
    keys.forEach((g, gi) => {{
      const angle = (2 * Math.PI * gi) / Math.max(keys.length, 1);
      const cx = Math.cos(angle) * R;
      const cy = Math.sin(angle) * R;
      const members = groups[g];
      const local = Math.max(80, Math.sqrt(members.length) * 28);
      members.forEach((n, i) => {{
        const a = (2 * Math.PI * i) / Math.max(members.length, 1);
        const r = local * (0.25 + 0.75 * ((i % 7) / 7));
        n.x = cx + Math.cos(a) * r + (Math.random() - 0.5) * 40;
        n.y = cy + Math.sin(a) * r + (Math.random() - 0.5) * 40;
      }});
    }});
  }} else {{
    const spread = Math.max(520, Math.sqrt(visNodes.length) * 95);
    visNodes.forEach((n) => {{
      n.x = (Math.random() - 0.5) * spread * 2;
      n.y = (Math.random() - 0.5) * spread * 2;
    }});
  }}
}}

const container = document.getElementById('mynetwork');
const networkData = {{
  nodes: new vis.DataSet(visNodes),
  edges: new vis.DataSet(visEdges)
}};

const options = {{
  groups: {{ useDefaultGroups: false }},
  nodes: {{
    shape: 'ellipse',
    scaling: {{ label: {{ enabled: true, min: 8, max: 14 }} }}
  }},
  edges: {{
    font: {{ size: 9, align: 'middle', background: '#0d1117', color: '#c8d0dc' }},
    smooth: {{ type: 'dynamic', roundness: 0.3 }}
  }},
  physics: PHYSICS_BASE,
  interaction: {{
    hover: true,
    tooltipDelay: 100,
    zoomView: true,
    dragView: true,
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

  typeEl.textContent = leg ? leg.label : (`그룹 ${{node.group}}`);
  typeEl.style.background = node.color + '33';
  typeEl.style.color = darkenColor(node.color, 0.35);
  typeEl.style.border = `1px solid ${{node.color}}`;
  titleEl.textContent = node.label.replace(/\\n/g, ' ');
  descEl.textContent = nodeDescriptions[nodeId] || '관련 설명이 없습니다.';
  detail.style.display = 'block';
}});

network.on('hoverNode', () => {{ container.style.cursor = 'pointer'; }});
network.on('blurNode', () => {{ container.style.cursor = 'default'; }});

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
  const spread = Math.max(1000, Math.sqrt(rawNodes.length) * 220);
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
  if (pattern === 'pattern3') return;
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
