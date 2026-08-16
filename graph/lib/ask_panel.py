"""Shared Ask panel fragments injected into pattern1/2/3 graph HTML.

Document search lives inside `.search-panel` as one unified card:
search box on top, results below when open.
"""

from __future__ import annotations

ASK_PANEL_CSS = """
  .search-panel {
    width: min(315px, calc(100vw - 36px));
    display: flex;
    flex-direction: column;
  }
  .search-panel .ask-close {
    display: none;
    background: transparent;
    border: none;
    color: #9aa3b2;
    font-size: 20px;
    line-height: 1;
    cursor: pointer;
    padding: 2px 6px;
    flex-shrink: 0;
  }
  .search-panel .ask-close:hover { color: #fff; }
  .search-panel.is-ask-open {
    background: rgba(22, 27, 38, 0.97);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 14px;
    box-shadow: 0 16px 48px rgba(0,0,0,0.45);
    overflow: hidden;
    max-height: calc(100vh - 36px);
  }
  .search-panel.is-ask-open .search-box {
    background: transparent;
    border: none;
    border-radius: 0;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    box-shadow: none;
  }
  .search-panel.is-ask-open .ask-close { display: block; }
  #ask-panel {
    display: none;
    flex-direction: column;
    min-height: 0;
    flex: 1;
    overflow: hidden;
  }
  #ask-panel.is-open { display: flex; }
  #ask-panel .ask-body {
    overflow: auto;
    padding: 12px 14px 16px;
    font-size: 12px;
    line-height: 1.55;
    color: #c4cad4;
    max-height: calc(100vh - 120px);
  }
  #ask-panel .ask-status {
    color: #9aa3b2;
    margin-bottom: 8px;
  }
  #ask-panel .ask-error {
    color: #fca5a5;
    background: rgba(239, 68, 68, 0.12);
    border: 1px solid rgba(239, 68, 68, 0.25);
    border-radius: 8px;
    padding: 10px 12px;
  }
  #ask-panel .ask-section {
    margin-top: 12px;
  }
  #ask-panel .ask-section h4 {
    font-size: 11px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: #8b95a5;
    margin-bottom: 6px;
  }
  #ask-panel .ask-chip {
    display: inline-block;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 999px;
    padding: 3px 9px;
    margin: 0 6px 6px 0;
    color: #e5e7eb;
    font-size: 11px;
    cursor: pointer;
  }
  #ask-panel .ask-chip:hover {
    border-color: rgba(96, 165, 250, 0.5);
    color: #fff;
  }
  #ask-panel .ask-edge {
    color: #9aa3b2;
    margin: 0 0 4px;
    font-size: 11px;
  }
  #ask-panel .ask-source {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 10px 12px;
    margin-bottom: 10px;
  }
  #ask-panel .ask-source .src-name {
    font-weight: 650;
    color: #e8eaed;
    margin-bottom: 4px;
    word-break: break-all;
  }
  #ask-panel .ask-source .src-labels {
    color: #8b95a5;
    font-size: 11px;
    margin-bottom: 8px;
  }
  #ask-panel .ask-excerpt {
    white-space: pre-wrap;
    background: rgba(0,0,0,0.25);
    border-radius: 8px;
    padding: 8px 10px;
    margin-top: 6px;
    color: #d1d5db;
    max-height: 220px;
    overflow: auto;
  }
"""

ASK_PANEL_HTML = """
    <div id="ask-panel" aria-hidden="true" data-doc-search="1">
      <div class="ask-body" id="ask-body"></div>
    </div>
"""

ASK_PANEL_JS = r"""
function openAskPanel() {
  const panel = document.getElementById('ask-panel');
  if (!panel) return;
  panel.classList.add('is-open');
  panel.setAttribute('aria-hidden', 'false');
  const searchPanel = document.querySelector('.search-panel');
  if (searchPanel) searchPanel.classList.add('is-ask-open');
  const detail = document.getElementById('node-detail');
  if (detail) detail.style.display = 'none';
  if (typeof toggleLegend === 'function') toggleLegend(true);
}

function closeAskPanel() {
  const panel = document.getElementById('ask-panel');
  if (!panel) return;
  panel.classList.remove('is-open');
  panel.setAttribute('aria-hidden', 'true');
  const searchPanel = document.querySelector('.search-panel');
  if (searchPanel) searchPanel.classList.remove('is-ask-open');
  const body = document.getElementById('ask-body');
  if (body) body.innerHTML = '';
}

function toggleAskPanel() {
  const panel = document.getElementById('ask-panel');
  if (!panel) return;
  if (panel.classList.contains('is-open')) closeAskPanel();
  else openAskPanel();
}

document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('search');
  if (input) {
    input.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') {
        ev.preventDefault();
        submitAsk();
      } else if (ev.key === 'Escape') {
        closeAskPanel();
        input.blur();
      }
    });
  }
});

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function focusAskNode(nodeId) {
  if (!nodeId || typeof network === 'undefined') return;
  try {
    network.selectNodes([nodeId]);
    network.focus(nodeId, { scale: 1.15, animation: true });
  } catch (e) {}
}

function highlightAskNodes(nodeIds) {
  if (typeof networkData === 'undefined' || !rawNodes) return;
  const hit = new Set(nodeIds || []);
  if (!hit.size) {
    networkData.nodes.update(rawNodes.map(n => ({
      id: n.id,
      hidden: false,
      opacity: (!activeGroup || n.group === activeGroup) ? 1 : 0.08
    })));
    return;
  }
  networkData.nodes.update(rawNodes.map(n => ({
    id: n.id,
    hidden: false,
    opacity: hit.has(n.id) ? 1 : 0.08
  })));
  if (hit.size === 1) focusAskNode([...hit][0]);
  else if (typeof network !== 'undefined') {
    try { network.fit({ nodes: [...hit], animation: { duration: 400 } }); } catch (e) {}
  }
}

function renderAskResult(data) {
  const body = document.getElementById('ask-body');
  if (data.message && !(data.nodes && data.nodes.length)) {
    body.innerHTML = `<div class="ask-error">${escapeHtml(data.message)}</div>`;
    highlightAskNodes([]);
    return;
  }

  const start = (data.start_nodes || [])
    .map(n => `<span class="ask-chip" data-nid="${escapeHtml(n.id)}">${escapeHtml(n.label)}</span>`)
    .join('');
  const nodes = (data.nodes || []).slice(0, 24)
    .map(n => `<span class="ask-chip" data-nid="${escapeHtml(n.id)}">${escapeHtml(n.label)}</span>`)
    .join('');
  const edges = (data.edges || []).slice(0, 18)
    .map(e => `<div class="ask-edge">${escapeHtml(e.source_label)} —${escapeHtml(e.relation)} [${escapeHtml(e.confidence)}]→ ${escapeHtml(e.target_label)}</div>`)
    .join('');

  const sources = (data.sources || []).map(src => {
    const labels = (src.matched_labels || []).map(escapeHtml).join(', ');
    if (!src.readable || !(src.excerpts || []).length) {
      return `<div class="ask-source"><div class="src-name">${escapeHtml(src.name || src.path)}</div>` +
        `<div class="src-labels">${escapeHtml(labels || '')}</div>` +
        `<div class="ask-error">${escapeHtml(src.error || '본문을 읽지 못했습니다.')}</div></div>`;
    }
    const excerpts = src.excerpts.map(ex => `<div class="ask-excerpt">${escapeHtml(ex)}</div>`).join('');
    return `<div class="ask-source"><div class="src-name">${escapeHtml(src.name)}</div>` +
      `<div class="src-labels">관련: ${escapeHtml(labels)}</div>${excerpts}</div>`;
  }).join('');

  body.innerHTML =
    `<div class="ask-status">Traversal: ${escapeHtml((data.mode || 'bfs').toUpperCase())} · ` +
    `시작 ${ (data.start_nodes || []).length } · 노드 ${ (data.nodes || []).length }` +
    `${data.truncated ? ' · truncated' : ''}</div>` +
    `<div class="ask-section"><h4>시작 노드</h4>${start || '<span class="ask-status">없음</span>'}</div>` +
    `<div class="ask-section"><h4>관련 노드</h4>${nodes || '<span class="ask-status">없음</span>'}</div>` +
    (edges ? `<div class="ask-section"><h4>관계</h4>${edges}</div>` : '') +
    `<div class="ask-section"><h4>소스 본문</h4>${sources || '<span class="ask-status">연결된 소스 파일이 없습니다.</span>'}</div>`;

  body.querySelectorAll('.ask-chip[data-nid]').forEach(el => {
    el.addEventListener('click', () => focusAskNode(el.getAttribute('data-nid')));
  });
  highlightAskNodes((data.nodes || []).map(n => n.id));
}

async function submitAsk() {
  const input = document.getElementById('search');
  const body = document.getElementById('ask-body');
  const question = (input && input.value || '').trim();
  if (!question) {
    closeAskPanel();
    return;
  }
  openAskPanel();
  body.innerHTML = '<div class="ask-status">문서를 검색하는 중…</div>';
  try {
    const res = await fetch('/api/graph/query', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify({ question, mode: 'bfs' })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data.detail || data.message || res.statusText || 'query failed';
      body.innerHTML = `<div class="ask-error">${escapeHtml(typeof detail === 'string' ? detail : JSON.stringify(detail))}</div>`;
      return;
    }
    renderAskResult(data);
  } catch (err) {
    body.innerHTML = `<div class="ask-error">${escapeHtml(err && err.message ? err.message : String(err))}</div>`;
  }
}
"""
