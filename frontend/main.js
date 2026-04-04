/**
 * AI Newsroom — Frontend Dashboard
 * Real-time multi-agent workflow visualizer
 */

// ─────────────────────────────────────────────
// CONFIG
// ─────────────────────────────────────────────
const API_BASE = 'http://127.0.0.1:8000';
const WS_URL   = 'ws://127.0.0.1:8000/ws/events';

// Agent definitions — order matters (matches workflow)
const AGENTS = [
  { id: 'scout',      label: 'Scout',      icon: '🔍', desc: 'Topic Discovery'   },
  { id: 'researcher', label: 'Researcher', icon: '📚', desc: 'Data Collection'   },
  { id: 'skeptic',    label: 'Skeptic',    icon: '🧐', desc: 'Fact Checking'     },
  { id: 'writer',     label: 'Writer',     icon: '✍️', desc: 'Content Creation'  },
  { id: 'editor',     label: 'Editor',     icon: '✂️', desc: 'Editorial Review'  },
  { id: 'publisher',  label: 'Publisher',  icon: '🚀', desc: 'Publishing'        },
];

// Graph layout: each sub-array is a row
const ROWS = [
  ['scout'],
  ['researcher'],
  ['skeptic'],
  ['writer'],
  ['editor'],
  ['publisher'],
];

// Defined connections (from → to) — matches actual graph.py edges
const EDGES = [
  { from: 'scout',      to: 'researcher' },
  { from: 'researcher', to: 'skeptic'    },
  { from: 'skeptic',    to: 'writer'     },
  { from: 'writer',     to: 'editor'     },
  { from: 'editor',     to: 'publisher'  },
  // Loop-back edges (shown lighter)
  { from: 'skeptic',    to: 'researcher', loop: true },
  { from: 'editor',     to: 'writer',     loop: true },
  { from: 'editor',     to: 'researcher', loop: true },
  { from: 'publisher',  to: 'editor',     loop: true },
  { from: 'skeptic',    to: 'scout',      loop: true },
];

// ─────────────────────────────────────────────
// STATE
// ─────────────────────────────────────────────
const state = {
  agents: Object.fromEntries(AGENTS.map(a => [a.id, 'idle'])),
  activeEdge: null,
  latestRunId: null,
  ws: null,
  wsRetries: 0,
};

// ─────────────────────────────────────────────
// DOM REFS
// ─────────────────────────────────────────────
const $ = id => document.getElementById(id);

const logOutput    = $('log-output');
const statusText   = $('status-text');
const wsDot        = $('ws-indicator');
const topicValue   = $('topic-value');
const tickerText   = $('ticker-text');
const btnRun       = $('btn-run');
const btnOutputs   = $('btn-outputs');
const outputModal  = $('output-modal');
const runsModal    = $('runs-modal');
const articleEl    = $('article-content');
const modalRunId   = $('modal-run-id');
const btnDownload  = $('btn-download-docx');
const runsList     = $('runs-list');
const svgEl        = $('connections-svg');
const graphNodes   = $('graph-nodes');

// ─────────────────────────────────────────────
// MARKDOWN RENDERER (no external dep)
// ─────────────────────────────────────────────
function renderMarkdown(md) {
  // Very lightweight markdown→HTML (handles most common patterns)
  let html = md
    // Front matter strip
    .replace(/^---[\s\S]*?---\n/, '')
    // Headings
    .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // HR
    .replace(/^---$/gm, '<hr>')
    // Bold / italic
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Code (inline)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    // Unordered lists
    .replace(/^\* (.+)$/gm, '<ul-item>$1</ul-item>')
    // Numbered lists
    .replace(/^\d+\. (.+)$/gm, '<ol-item>$1</ol-item>');

  // Group list items
  html = html
    .replace(/((<ul-item>.*?<\/ul-item>\n?)+)/g, m =>
      '<ul>' + m.replace(/<ul-item>(.*?)<\/ul-item>/g, '<li>$1</li>') + '</ul>')
    .replace(/((<ol-item>.*?<\/ol-item>\n?)+)/g, m =>
      '<ol>' + m.replace(/<ol-item>(.*?)<\/ol-item>/g, '<li>$1</li>') + '</ol>');

  // Paragraphs — wrap remaining text blocks
  html = html
    .split('\n\n')
    .map(block => {
      block = block.trim();
      if (!block) return '';
      if (/^<(h[1-6]|ul|ol|hr|blockquote|pre)/.test(block)) return block;
      return `<p>${block.replace(/\n/g, '<br>')}</p>`;
    })
    .join('\n');

  return html;
}

// ─────────────────────────────────────────────
// LOGGING
// ─────────────────────────────────────────────
function appendLog(text, type = 'info') {
  const atBottom = logOutput.scrollHeight - logOutput.scrollTop <= logOutput.clientHeight + 30;
  const line = document.createElement('span');
  line.className = `log-${type}`;
  line.textContent = text + '\n';
  logOutput.appendChild(line);
  if (atBottom) logOutput.scrollTop = logOutput.scrollHeight;
}

function classifyLog(msg) {
  if (/error|failed|exception/i.test(msg)) return 'error';
  if (/warn/i.test(msg))                    return 'warn';
  if (/✅|published|success|complete/i.test(msg)) return 'success';
  if (/agent|scout|researcher|skeptic|writer|editor|publisher/i.test(msg)) return 'agent';
  if (/^>>>|websocket|connected/i.test(msg)) return 'system';
  return 'info';
}

// ─────────────────────────────────────────────
// AGENT NODE UI
// ─────────────────────────────────────────────
function setAgentStatus(id, status, statusLabel) {
  state.agents[id] = status;
  const node = document.querySelector(`.agent-node[data-id="${id}"]`);
  if (!node) return;

  node.classList.remove('idle', 'running', 'completed', 'error');
  node.classList.add(status);

  const statusEl = node.querySelector('.node-status');
  if (statusEl) {
    const labels = {
      idle:      AGENTS.find(a => a.id === id)?.desc || 'Idle',
      running:   statusLabel || 'Running…',
      completed: 'Done',
      error:     'Error',
    };
    statusEl.textContent = labels[status] || status;
  }
}

function setTicker(msg) {
  tickerText.textContent = msg;
}

// ─────────────────────────────────────────────
// GRAPH BUILDER
// ─────────────────────────────────────────────
function buildGraph() {
  graphNodes.innerHTML = '';

  // Build rows
  ROWS.forEach(rowIds => {
    const row = document.createElement('div');
    row.className = 'graph-row';

    rowIds.forEach(agentId => {
      const meta = AGENTS.find(a => a.id === agentId);
      const node = document.createElement('div');
      node.className = 'agent-node idle';
      node.dataset.id = agentId;
      node.setAttribute('role', 'status');
      node.setAttribute('aria-label', `${meta.label} agent`);
      node.innerHTML = `
        <span class="node-icon">${meta.icon}</span>
        <span class="node-name">${meta.label}</span>
        <span class="node-status">${meta.desc}</span>
      `;
      row.appendChild(node);
    });

    graphNodes.appendChild(row);
  });

  // Draw SVG edges after nodes are in the DOM
  requestAnimationFrame(drawEdges);
}

// ─────────────────────────────────────────────
// SVG EDGE DRAWING
// ─────────────────────────────────────────────
let edgeElements = {}; // edgeKey → { path, particle, markerId }

function getNodeCenter(id) {
  const node = document.querySelector(`.agent-node[data-id="${id}"]`);
  if (!node) return null;
  const graphRect = svgEl.getBoundingClientRect();
  const nodeRect  = node.getBoundingClientRect();
  return {
    x: nodeRect.left - graphRect.left + nodeRect.width / 2,
    y: nodeRect.top  - graphRect.top  + nodeRect.height / 2,
    w: nodeRect.width,
    h: nodeRect.height,
  };
}

function drawEdges() {
  svgEl.innerHTML = '';
  edgeElements = {};

  const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
  svgEl.appendChild(defs);

  // Forward edges (main pipeline)
  const forwardEdges = EDGES.filter(e => !e.loop);
  // Loop back edges — drawn differently
  const loopEdges    = EDGES.filter(e => e.loop);

  [...forwardEdges, ...loopEdges].forEach((edge, idx) => {
    const fromC = getNodeCenter(edge.from);
    const toC   = getNodeCenter(edge.to);
    if (!fromC || !toC) return;

    const key = `${edge.from}→${edge.to}`;

    // Arrow marker
    const markerId = `arrow-${idx}`;
    const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
    marker.setAttribute('id', markerId);
    marker.setAttribute('markerWidth', '8');
    marker.setAttribute('markerHeight', '8');
    marker.setAttribute('refX', '6');
    marker.setAttribute('refY', '3');
    marker.setAttribute('orient', 'auto');
    const arrowPoly = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    arrowPoly.setAttribute('points', '0 0, 6 3, 0 6');
    arrowPoly.className.baseVal = 'conn-arrow';
    arrowPoly.dataset.key = key;
    marker.appendChild(arrowPoly);
    defs.appendChild(marker);

    // Path data: cubic bezier curves
    let d;
    if (!edge.loop) {
      // Straight down (main flow)
      const x1 = fromC.x, y1 = fromC.y + fromC.h / 2;
      const x2 = toC.x,   y2 = toC.y  - toC.h  / 2 - 2;
      const cy  = (y1 + y2) / 2;
      d = `M ${x1} ${y1} C ${x1} ${cy}, ${x2} ${cy}, ${x2} ${y2}`;
    } else {
      // Loop-back: curve to the right or left
      const side = idx % 2 === 0 ? 1 : -1;
      const x1 = fromC.x + side * fromC.w / 2;
      const y1 = fromC.y;
      const x2 = toC.x  + side * toC.w  / 2;
      const y2 = toC.y;
      const offset = 90 + Math.abs(fromC.y - toC.y) * 0.25;
      d = `M ${x1} ${y1} C ${x1 + side * offset} ${y1}, ${x2 + side * offset} ${y2}, ${x2} ${y2}`;
    }

    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', d);
    path.setAttribute('marker-end', `url(#${markerId})`);
    path.className.baseVal = edge.loop ? 'conn-path' : 'conn-path';
    path.style.opacity = edge.loop ? '0.35' : '1';
    path.dataset.key = key;
    svgEl.appendChild(path);

    // Data particle circle
    const particle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    particle.setAttribute('r', '4');
    particle.className.baseVal = 'data-particle';
    particle.dataset.key = key;
    svgEl.appendChild(particle);

    // Animate particle along path (hidden by default)
    const animateMotion = document.createElementNS('http://www.w3.org/2000/svg', 'animateMotion');
    animateMotion.setAttribute('dur', '1.2s');
    animateMotion.setAttribute('repeatCount', 'indefinite');
    animateMotion.setAttribute('begin', 'indefinite');
    const mpath = document.createElementNS('http://www.w3.org/2000/svg', 'mpath');
    mpath.setAttributeNS('http://www.w3.org/1999/xlink', 'href', '#path-' + idx);
    // Use path itself
    animateMotion.setAttribute('path', d);
    particle.appendChild(animateMotion);
    svgEl.appendChild(particle);

    edgeElements[key] = { path, particle, animateMotion, markerId, arrowPoly };
  });
}

function activateEdge(fromId, toId) {
  // Reset all edges
  Object.values(edgeElements).forEach(({ path, particle, animateMotion, arrowPoly }) => {
    path.classList.remove('active', 'done');
    particle.classList.remove('visible');
    arrowPoly.classList.remove('active', 'done');
    // pause animation
    try { animateMotion.endElement(); } catch(e) {}
  });

  const key = `${fromId}→${toId}`;
  const el  = edgeElements[key];
  if (!el) return;

  el.path.classList.add('active');
  el.arrowPoly.classList.add('active');
  el.particle.classList.add('visible');

  // Restart animation
  try {
    el.animateMotion.beginElement();
  } catch(e) {}

  state.activeEdge = key;
}

function markEdgeDone(fromId, toId) {
  const key = `${fromId}→${toId}`;
  const el  = edgeElements[key];
  if (!el) return;
  el.path.classList.remove('active');
  el.path.classList.add('done');
  el.arrowPoly.classList.remove('active');
  el.arrowPoly.classList.add('done');
  el.particle.classList.remove('visible');
  try { el.animateMotion.endElement(); } catch(e) {}
}

// ─────────────────────────────────────────────
// WORKFLOW SEQUENCING HELPERS
// ─────────────────────────────────────────────
const AGENT_ORDER = AGENTS.map(a => a.id);

function getPreviousAgent(id) {
  const idx = AGENT_ORDER.indexOf(id);
  return idx > 0 ? AGENT_ORDER[idx - 1] : null;
}

function onAgentStarted(id) {
  setAgentStatus(id, 'running', 'Running…');
  const prev = getPreviousAgent(id);
  if (prev) activateEdge(prev, id);
  setTicker(`[${id.toUpperCase()}] is running…`);
}

function onAgentCompleted(id) {
  setAgentStatus(id, 'completed');
  const prev = getPreviousAgent(id);
  if (prev) markEdgeDone(prev, id);
}

function onAgentError(id) {
  setAgentStatus(id, 'error');
}

// ─────────────────────────────────────────────
// WEBSOCKET
// ─────────────────────────────────────────────
function setWsState(s) {
  wsDot.className = `ws-dot ${s}`;
}

function connectWebSocket() {
  const ws = new WebSocket(WS_URL);
  state.ws = ws;

  ws.onopen = () => {
    setWsState('connected');
    statusText.textContent = 'Connected';
    appendLog('>>> WebSocket connected to AI Newsroom backend', 'system');
    state.wsRetries = 0;
    btnRun.disabled = false;
  };

  ws.onmessage = ({ data }) => {
    let parsed;
    try { parsed = JSON.parse(data); } catch { parsed = null; }

    if (!parsed) {
      appendLog(data, classifyLog(data));
      return;
    }

    // ── Log message ──
    if (parsed.type === 'log') {
      const msg = (parsed.message || '').trim();
      appendLog(msg, classifyLog(msg));

      // Detect run ID from artifact storage message
      const m = msg.match(/Artifacts stored in:.*?run_(\d+_\d+)/);
      if (m) {
        state.latestRunId = `run_${m[1]}`;
        setTimeout(() => loadAndShowOutput(state.latestRunId), 1200);
        appendLog(`>>> Fetching output for ${state.latestRunId}…`, 'system');
      }

      // Update topic from log
      const topicMatch = msg.match(/Topic:\s*(.+)/i);
      if (topicMatch) topicValue.textContent = topicMatch[1].trim();

      return;
    }

    // ── Structured agent event ──
    const { agent, event, message } = parsed;
    if (agent) {
      const id = agent.toLowerCase().replace(/\s+/g, '_');
      if (message) setTicker(message);

      if (event === 'started' || event === 'running') {
        onAgentStarted(id);
        appendLog(`[${id.toUpperCase()}] started`, 'agent');
      } else if (event === 'completed' || event === 'done') {
        onAgentCompleted(id);
        appendLog(`[${id.toUpperCase()}] completed`, 'success');
      } else if (event === 'error') {
        onAgentError(id);
        appendLog(`[${id.toUpperCase()}] error: ${message || ''}`, 'error');
      } else if (event === 'decision') {
        appendLog(`[${id.toUpperCase()}] → ${message || ''}`, 'agent');
      } else if (message) {
        appendLog(`[${id.toUpperCase()}] ${message}`, 'agent');
      }

      // Topic updates from events
      if (parsed.data?.topic) topicValue.textContent = parsed.data.topic;

      // Output run id from events
      if (parsed.data?.run_id) {
        state.latestRunId = parsed.data.run_id;
      }
    }
  };

  ws.onclose = () => {
    setWsState('disconnected');
    statusText.textContent = 'Disconnected';
    btnRun.disabled = true;
    const delay = Math.min(5000, 1000 * (state.wsRetries + 1));
    state.wsRetries++;
    appendLog(`>>> Connection lost. Reconnecting in ${delay/1000}s…`, 'system');
    setTimeout(connectWebSocket, delay);
  };

  ws.onerror = () => {
    setWsState('error');
    appendLog('>>> WebSocket error.', 'error');
  };
}

// ─────────────────────────────────────────────
// RUN WORKFLOW (trigger backend)
// ─────────────────────────────────────────────
async function triggerWorkflow() {
  btnRun.disabled = true;
  btnRun.innerHTML = '<span class="btn-icon">⏳</span> Running…';

  // Reset all agent states
  AGENTS.forEach(a => setAgentStatus(a.id, 'idle'));
  Object.values(edgeElements).forEach(({ path, particle, arrowPoly }) => {
    path.classList.remove('active', 'done');
    particle.classList.remove('visible');
    arrowPoly.classList.remove('active', 'done');
  });
  setTicker('Workflow starting…');
  appendLog('>>> Triggering AI Newsroom workflow…', 'system');

  try {
    const res = await fetch(`${API_BASE}/api/run`, { method: 'POST' });
    if (res.ok) {
      appendLog('>>> Workflow started successfully.', 'success');
    } else {
      const txt = await res.text();
      appendLog(`>>> Failed to start workflow (${res.status}): ${txt}`, 'error');
      btnRun.disabled = false;
      btnRun.innerHTML = '<span class="btn-icon">▶</span> Run Workflow';
    }
  } catch (err) {
    appendLog(`>>> Could not reach backend: ${err.message}`, 'error');
    appendLog('>>> Make sure uvicorn is running on port 8000.', 'warn');
    btnRun.disabled = false;
    btnRun.innerHTML = '<span class="btn-icon">▶</span> Run Workflow';
  }
}

// ─────────────────────────────────────────────
// OUTPUT: LIST RUNS
// ─────────────────────────────────────────────
async function showRunsList() {
  runsModal.classList.remove('hidden');
  runsList.innerHTML = '<div class="dim mono" style="padding:16px;font-size:12px">Loading…</div>';

  try {
    const res = await fetch(`${API_BASE}/api/runs`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const runs = await res.json(); // [{id, article_md, article_docx}]

    runsList.innerHTML = '';
    if (!runs.length) {
      runsList.innerHTML = '<div style="padding:16px;color:var(--text-dim);font-size:13px">No outputs yet. Run the workflow first.</div>';
      return;
    }

    runs.reverse().forEach(run => {
      const item = document.createElement('div');
      item.className = 'run-item';
      item.innerHTML = `
        <div>
          <div class="run-item-id">${run.id}</div>
          <div class="run-item-meta">${run.article_md ? 'Article available' : 'No article'}</div>
        </div>
        <button class="btn btn-ghost run-item-btn" data-run="${run.id}">View →</button>
      `;
      item.querySelector('button').addEventListener('click', () => {
        runsModal.classList.add('hidden');
        loadAndShowOutput(run.id);
      });
      runsList.appendChild(item);
    });
  } catch (err) {
    runsList.innerHTML = `<div style="padding:16px;color:var(--c-error);font-size:12px" class="mono">Error: ${err.message}</div>`;
  }
}

// ─────────────────────────────────────────────
// OUTPUT: LOAD & SHOW ARTICLE
// ─────────────────────────────────────────────
async function loadAndShowOutput(runId) {
  articleEl.innerHTML = '<div class="dim mono" style="padding:20px;font-size:12px">Loading article…</div>';
  modalRunId.textContent = runId;
  btnDownload.href = `${API_BASE}/output/${runId}/article.docx`;
  btnDownload.setAttribute('download', `${runId}_article.docx`);
  outputModal.classList.remove('hidden');

  try {
    const res = await fetch(`${API_BASE}/output/${runId}/article.md`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const md = await res.text();
    articleEl.innerHTML = renderMarkdown(md);
    articleEl.className = 'markdown-body';
  } catch (err) {
    articleEl.innerHTML = `<div style="color:var(--c-error)" class="mono">Failed to load: ${err.message}</div>`;
  }
}

// ─────────────────────────────────────────────
// MODAL EVENT HANDLERS
// ─────────────────────────────────────────────
$('btn-close-modal').addEventListener('click', () => outputModal.classList.add('hidden'));
$('modal-backdrop').addEventListener('click', () => outputModal.classList.add('hidden'));

$('btn-close-runs').addEventListener('click', () => runsModal.classList.add('hidden'));
$('runs-backdrop').addEventListener('click', () => runsModal.classList.add('hidden'));

btnRun.addEventListener('click', triggerWorkflow);

btnOutputs.addEventListener('click', showRunsList);

$('btn-clear-log').addEventListener('click', () => {
  logOutput.innerHTML = '';
  appendLog('>>> Log cleared.', 'system');
});

// Keyboard shortcuts
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    outputModal.classList.add('hidden');
    runsModal.classList.add('hidden');
  }
});

// ─────────────────────────────────────────────
// RESIZE: REDRAW EDGES
// ─────────────────────────────────────────────
let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(drawEdges, 120);
});

// ─────────────────────────────────────────────
// INIT
// ─────────────────────────────────────────────
appendLog('>>> Booting AI Newsroom dashboard…', 'system');
buildGraph();
connectWebSocket();
