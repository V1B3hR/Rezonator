/**
 * Błyskawica Rezonator: Frontend Application Logic
 * Interactive 4-Quadrant Physics Visualizers & Differential Anomaly Radar
 */

// Global Application State
const AppState = {
  examples: {},
  currentAnalysis: null,
  currentComparison: null,
  activeTab: 'single-view',
  diffusionTimeIdx: 0,
  diffusionTimer: null,
  isDiffusionPlaying: false,
  cymaticsAnimFrame: null,
  cymaticsTime: 0,
  isCymaticsPlaying: true,
  selectedNode: null,
  graphLayout: {
    nodes: [],
    edges: []
  }
};

document.addEventListener('DOMContentLoaded', async () => {
  initTabs();
  initEventListeners();
  await loadExamples();
  await triggerAnalysis();
  startCymaticsAnimation();
});

// ==========================================================================
// Tab Management
// ==========================================================================

function initTabs() {
  const tabs = document.querySelectorAll('.tab-btn');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      const paneId = `pane-${tab.getAttribute('data-tab')}`;
      const pane = document.getElementById(paneId);
      if (pane) pane.classList.add('active');
      AppState.activeTab = tab.getAttribute('data-tab');

      if (AppState.activeTab === 'single-view') {
        resizeAllCanvases();
        renderGraph();
        renderCymatics(AppState.cymaticsTime);
        renderDiffusion();
        renderGeodesic();
      } else if (AppState.activeTab === 'compare-view') {
        if (!AppState.currentComparison) {
          triggerComparison();
        } else {
          renderCompareCharts();
        }
      }
    });
  });
}

// ==========================================================================
// Event Listeners
// ==========================================================================

function initEventListeners() {
  document.getElementById('btn-analyze-code').addEventListener('click', () => {
    triggerAnalysis();
  });

  document.getElementById('btn-quick-compare').addEventListener('click', () => {
    document.getElementById('tab-compare').click();
  });

  document.getElementById('example-select').addEventListener('change', (e) => {
    const key = e.target.value;
    if (AppState.examples[key]) {
      document.getElementById('cobol-editor').value = AppState.examples[key].code;
      triggerAnalysis();
    }
  });

  document.getElementById('btn-reset-code').addEventListener('click', () => {
    const key = document.getElementById('example-select').value;
    if (AppState.examples[key]) {
      document.getElementById('cobol-editor').value = AppState.examples[key].code;
      triggerAnalysis();
    }
  });

  // Diffusion controls
  const slider = document.getElementById('slider-time');
  slider.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value);
    document.getElementById('label-current-time').textContent = val.toFixed(2);
    if (AppState.currentAnalysis && AppState.currentAnalysis.diffusion) {
      const times = AppState.currentAnalysis.diffusion.times;
      // Find nearest index
      let bestIdx = 0;
      let minDiff = 999;
      times.forEach((t, i) => {
        const d = Math.abs(t - val);
        if (d < minDiff) { minDiff = d; bestIdx = i; }
      });
      AppState.diffusionTimeIdx = bestIdx;
      renderDiffusion();
      renderGraph(); // Update node glow
    }
  });

  document.getElementById('btn-play-diffusion').addEventListener('click', () => {
    toggleDiffusionPlay();
  });

  document.getElementById('btn-reset-diffusion').addEventListener('click', () => {
    stopDiffusionPlay();
    AppState.diffusionTimeIdx = 0;
    slider.value = 0.0;
    document.getElementById('label-current-time').textContent = "0.00";
    renderDiffusion();
    renderGraph();
  });

  document.getElementById('btn-toggle-cymatics-anim').addEventListener('click', () => {
    AppState.isCymaticsPlaying = !AppState.isCymaticsPlaying;
  });

  document.getElementById('btn-trigger-compare').addEventListener('click', () => {
    triggerComparison();
  });

  document.getElementById('btn-copy-brief').addEventListener('click', () => {
    const text = document.getElementById('brief-text-content').textContent;
    navigator.clipboard.writeText(text).then(() => {
      const btn = document.getElementById('btn-copy-brief');
      btn.textContent = 'Copied to Clipboard!';
      setTimeout(() => { btn.textContent = 'Copy Markdown to Clipboard'; }, 2000);
    });
  });

  // Canvas resize listener
  window.addEventListener('resize', () => {
    resizeAllCanvases();
    renderGraph();
    renderCymatics(AppState.cymaticsTime);
    renderDiffusion();
    renderGeodesic();
  });

  // Canvas graph click listener for node inspector
  const graphCanvas = document.getElementById('canvas-graph');
  graphCanvas.addEventListener('click', handleGraphClick);
}

// ==========================================================================
// API Communication
// ==========================================================================

async function loadExamples() {
  try {
    const res = await fetch('/api/examples');
    if (!res.ok) throw new Error('Failed to fetch examples');
    AppState.examples = await res.json();

    // Populate compare code editors
    if (AppState.examples['bank_demo_v1']) {
      document.getElementById('compare-code-a').value = AppState.examples['bank_demo_v1'].code;
    }
    if (AppState.examples['bank_demo_v2']) {
      document.getElementById('compare-code-b').value = AppState.examples['bank_demo_v2'].code;
    }

    // Set initial active code
    const initialKey = document.getElementById('example-select').value;
    if (AppState.examples[initialKey]) {
      document.getElementById('cobol-editor').value = AppState.examples[initialKey].code;
    }
  } catch (err) {
    console.error('Error loading examples:', err);
  }
}

async function triggerAnalysis() {
  const code = document.getElementById('cobol-editor').value;
  if (!code.trim()) return;

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    });

    if (!res.ok) throw new Error('Analysis API failed');
    const data = await res.json();
    AppState.currentAnalysis = data;

    updateSingleViewUI(data);
    setupGraphLayout(data);
    resizeAllCanvases();

    renderGraph();
    renderCymatics(AppState.cymaticsTime);
    renderDiffusion();
    renderGeodesic();

    // Update LLM brief
    document.getElementById('brief-text-content').textContent = data.llm_brief;

  } catch (err) {
    console.error('Analysis error:', err);
  }
}

async function triggerComparison() {
  const code_a = document.getElementById('compare-code-a').value;
  const code_b = document.getElementById('compare-code-b').value;
  if (!code_a.trim() || !code_b.trim()) return;

  try {
    const res = await fetch('/api/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code_a, code_b })
    });

    if (!res.ok) throw new Error('Comparison API failed');
    const data = await res.json();
    AppState.currentComparison = data;

    updateCompareViewUI(data);
    renderCompareCharts();

  } catch (err) {
    console.error('Comparison error:', err);
  }
}

// ==========================================================================
// UI Updates & Ribbons
// ==========================================================================

function updateSingleViewUI(data) {
  const stats = data.stats || {};
  const spectrum = data.spectrum || {};
  const diff = data.diffusion || {};
  const geo = data.geodesic || {};

  document.getElementById('val-nodes').textContent = stats.num_nodes || 0;
  document.getElementById('val-edges').textContent = stats.num_edges || 0;
  document.getElementById('val-vars').textContent = stats.num_variables || 0;

  const fiedler = spectrum.fiedler_value !== undefined ? spectrum.fiedler_value.toFixed(4) : '--';
  document.getElementById('val-fiedler').textContent = fiedler;

  const hl = diff.diffusion_half_life;
  document.getElementById('val-halflife').textContent = (hl && !isFinite(hl)) ? '∞' : (hl ? hl.toFixed(2) + 's' : '--');

  document.getElementById('val-mass').textContent = geo.mass_M ? geo.mass_M.toFixed(2) : '--';

  // Nodal ratio
  const nodal = data.chladni ? (data.chladni.nodal_ratio * 100).toFixed(1) + '%' : '--';
  document.getElementById('val-nodal-ratio').textContent = nodal;

  // Modal frequency badges
  const modalBar = document.getElementById('modal-freq-bar');
  modalBar.innerHTML = '';
  if (spectrum.eigenvalues) {
    spectrum.eigenvalues.slice(0, 8).forEach((ev, i) => {
      const pill = document.createElement('div');
      pill.className = 'modal-pill';
      pill.textContent = `λ${i}: ${ev.toFixed(3)}`;
      modalBar.appendChild(pill);
    });
  }

  // Geodesic HUD
  document.getElementById('hud-rplus').textContent = geo.event_horizon_r_plus ? geo.event_horizon_r_plus.toFixed(2) : '--';
  document.getElementById('hud-spin').textContent = geo.spin_a ? geo.spin_a.toFixed(2) : '--';

  const trapBox = document.getElementById('geodesic-verdict-box');
  const badgeStatus = document.getElementById('badge-geodesic-status');
  if (geo.fell_into_horizon_trap) {
    badgeStatus.textContent = 'Event Horizon Crossed';
    badgeStatus.className = 'badge badge-gold';
    trapBox.textContent = 'CRITICAL: Execution trajectory crossed into Event Horizon trap r ≤ r+. Potential infinite loop or unreachable deadlock sink.';
    trapBox.style.color = '#ffb800';
  } else {
    badgeStatus.textContent = 'Trajectory Normal';
    badgeStatus.className = 'badge badge-violet';
    trapBox.textContent = 'Execution path successfully avoids terminal trap singularity; flow terminates gracefully at STOP RUN sink.';
    trapBox.style.color = 'var(--text-muted)';
  }

  // Populate impulse node selector
  const selectImpulse = document.getElementById('select-impulse-node');
  selectImpulse.innerHTML = '';
  if (data.parsed && data.parsed.nodes) {
    data.parsed.nodes.forEach((n, idx) => {
      const opt = document.createElement('option');
      opt.value = idx;
      opt.textContent = `${n.id}: ${n.label}`;
      selectImpulse.appendChild(opt);
    });
  }
}

function updateCompareViewUI(data) {
  const m = data.metrics || {};
  document.getElementById('cmp-spectral-dist').textContent = m.spectral_distance_L2 ? m.spectral_distance_L2.toFixed(3) : '--';
  
  const fDelta = m.fiedler_delta;
  const fElem = document.getElementById('cmp-fiedler-delta');
  fElem.textContent = fDelta >= 0 ? `+${fDelta.toFixed(4)}` : fDelta.toFixed(4);
  fElem.className = fDelta >= 0 ? 'score-number emerald' : 'score-number gold';

  const cymaticMatch = (m.cymatic_cross_similarity * 100).toFixed(1) + '%';
  document.getElementById('cmp-cymatic-match').textContent = cymaticMatch;

  const health = m.refactoring_health_score ? m.refactoring_health_score.toFixed(1) + ' / 100' : '--';
  document.getElementById('cmp-health-score').textContent = health;

  document.getElementById('scorecard-verdict').textContent = data.verdict || 'Evaluation Complete';
}

// ==========================================================================
// Physics Graph Layout (CFG + DFG)
// ==========================================================================

function setupGraphLayout(data) {
  const nodes = data.parsed ? data.parsed.nodes : [];
  const edges = data.parsed ? data.parsed.edges : [];

  const canvas = document.getElementById('canvas-graph');
  const width = canvas.width || 400;
  const height = canvas.height || 350;

  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.min(width, height) * 0.38;

  AppState.graphLayout.nodes = nodes.map((n, i) => {
    // Arrange in elliptical layout with variable hubs in inner orbit
    const isVar = n.node_type === 'var';
    const r = isVar ? radius * 0.45 : radius;
    const angle = (i / nodes.length) * Math.PI * 2;
    return {
      id: n.id,
      label: n.label,
      node_type: n.node_type,
      paragraph: n.paragraph,
      code: n.code,
      reads: n.reads,
      writes: n.writes,
      x: cx + r * Math.cos(angle) + (Math.random() - 0.5) * 20,
      y: cy + r * Math.sin(angle) + (Math.random() - 0.5) * 20,
      radius: isVar ? 14 : 12,
      index: i
    };
  });

  AppState.graphLayout.edges = edges.map(e => ({
    source: e.source,
    target: e.target,
    edge_type: e.edge_type,
    weight: e.weight
  }));
}

function renderGraph() {
  const canvas = document.getElementById('canvas-graph');
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;

  ctx.clearRect(0, 0, width, height);

  const nodes = AppState.graphLayout.nodes;
  const edges = AppState.graphLayout.edges;
  const nodeMap = {};
  nodes.forEach(n => { nodeMap[n.id] = n; });

  // Get current diffusion temperatures if available
  let temps = [];
  if (AppState.currentAnalysis && AppState.currentAnalysis.diffusion) {
    const traj = AppState.currentAnalysis.diffusion.trajectory;
    if (traj && traj[AppState.diffusionTimeIdx]) {
      temps = traj[AppState.diffusionTimeIdx];
    }
  }

  // 1. Draw Edges
  edges.forEach(e => {
    const src = nodeMap[e.source];
    const dst = nodeMap[e.target];
    if (!src || !dst) return;

    ctx.beginPath();
    ctx.moveTo(src.x, src.y);
    ctx.lineTo(dst.x, dst.y);

    if (e.edge_type === 'cfg_call') {
      ctx.strokeStyle = 'rgba(0, 255, 136, 0.4)';
      ctx.lineWidth = 2.0;
    } else if (e.edge_type === 'cfg_branch') {
      ctx.strokeStyle = 'rgba(255, 184, 0, 0.4)';
      ctx.lineWidth = 1.5;
    } else if (e.edge_type.startsWith('dfg')) {
      ctx.strokeStyle = 'rgba(176, 38, 255, 0.35)';
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1.0;
    } else {
      ctx.strokeStyle = 'rgba(0, 240, 255, 0.3)';
      ctx.lineWidth = 1.2;
      ctx.setLineDash([]);
    }

    ctx.stroke();
    ctx.setLineDash([]);

    // Draw small directional arrow
    const dx = dst.x - src.x;
    const dy = dst.y - src.y;
    const dist = Math.hypot(dx, dy);
    if (dist > 20) {
      const midX = (src.x + dst.x) / 2;
      const midY = (src.y + dst.y) / 2;
      const angle = Math.atan2(dy, dx);
      ctx.save();
      ctx.translate(midX, midY);
      ctx.rotate(angle);
      ctx.fillStyle = ctx.strokeStyle;
      ctx.beginPath();
      ctx.moveTo(4, 0);
      ctx.lineTo(-4, -3);
      ctx.lineTo(-4, 3);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }
  });

  // 2. Draw Nodes
  nodes.forEach(n => {
    const tVal = (temps[n.index] !== undefined) ? temps[n.index] : 0.0;
    const isSelected = AppState.selectedNode && AppState.selectedNode.id === n.id;

    ctx.save();

    // Heat color modulation (Blue cold -> Emerald -> Amber -> Red hot)
    let fillStyle = '#3b82f6';
    if (n.node_type === 'branch') fillStyle = '#f59e0b';
    else if (n.node_type === 'perform') fillStyle = '#10b981';
    else if (n.node_type === 'var') fillStyle = '#8b5cf6';

    if (tVal > 0.05) {
      // Glow with temperature
      const glowR = Math.min(255, Math.floor(tVal * 400));
      const glowG = Math.min(255, Math.floor(tVal * 250));
      ctx.shadowColor = `rgba(${glowR}, ${glowG}, 0, 0.8)`;
      ctx.shadowBlur = Math.min(20, tVal * 25);
    }

    ctx.beginPath();
    ctx.arc(n.x, n.y, n.radius + (isSelected ? 3 : 0), 0, Math.PI * 2);
    ctx.fillStyle = fillStyle;
    ctx.fill();

    ctx.lineWidth = isSelected ? 3 : 1.5;
    ctx.strokeStyle = isSelected ? '#ffffff' : 'rgba(255, 255, 255, 0.7)';
    ctx.stroke();

    // Node label
    ctx.fillStyle = '#ffffff';
    ctx.font = '9px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(n.id.replace('node_', '').replace('var_', '$'), n.x, n.y);

    ctx.restore();
  });
}

function handleGraphClick(e) {
  const canvas = document.getElementById('canvas-graph');
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const clickX = (e.clientX - rect.left) * scaleX;
  const clickY = (e.clientY - rect.top) * scaleY;

  let clicked = null;
  AppState.graphLayout.nodes.forEach(n => {
    const dist = Math.hypot(n.x - clickX, n.y - clickY);
    if (dist <= n.radius + 4) {
      clicked = n;
    }
  });

  if (clicked) {
    AppState.selectedNode = clicked;
    renderGraph();
    const inspector = document.getElementById('node-inspector');
    inspector.innerHTML = `
      <div><strong>[${clicked.id}] ${clicked.label}</strong> in <em>${clicked.paragraph}</em></div>
      <div style="color: #92e0ff; margin-top: 3px;"><code>${clicked.code}</code></div>
      <div style="font-size: 0.72rem; color: #8b9bb4; margin-top: 2px;">
        Reads: ${clicked.reads.join(', ') || 'None'} | Writes: ${clicked.writes.join(', ') || 'None'}
      </div>
    `;
  }
}

// ==========================================================================
// Diamond Yant 2D Cymatics (Chladni Plate Wave Engine)
// ==========================================================================

function startCymaticsAnimation() {
  function animate() {
    if (AppState.isCymaticsPlaying) {
      AppState.cymaticsTime += 0.035;
      if (AppState.activeTab === 'single-view') {
        renderCymatics(AppState.cymaticsTime);
      }
    }
    AppState.cymaticsAnimFrame = requestAnimationFrame(animate);
  }
  animate();
}

function renderCymatics(time) {
  const canvas = document.getElementById('canvas-cymatics');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;

  if (width === 0 || height === 0) return;

  const imgData = ctx.createImageData(width, height);
  const data = imgData.data;

  // Retrieve active modes
  const analysis = AppState.currentAnalysis;
  const activeModes = (analysis && analysis.chladni) ? analysis.chladni.active_modes : [];

  const modes = (activeModes && activeModes.length > 0) ? activeModes : [
    { n: 2, m: 3, amplitude: 1.0, eigenvalue: 0.2 },
    { n: 3, m: 5, amplitude: 0.7, eigenvalue: 0.6 }
  ];

  const pi = Math.PI;

  // Render 2D standing wave field
  for (let py = 0; py < height; py += 2) {
    const y = -1.0 + 2.0 * (py / height);
    for (let px = 0; px < width; px += 2) {
      const x = -1.0 + 2.0 * (px / width);

      let w = 0;
      modes.forEach((mode, idx) => {
        const omega = 1.0 + mode.eigenvalue * 2.0;
        const wave = Math.sin(mode.n * pi * x) * Math.sin(mode.m * pi * y) +
                     0.5 * Math.sin(mode.m * pi * x) * Math.sin(mode.n * pi * y);
        w += mode.amplitude * wave * Math.cos(omega * time + idx * 0.5);
      });

      // Clamp w to [-1.5, 1.5]
      const absW = Math.abs(w);
      const isNodal = absW < 0.12;

      let r, g, b;
      if (isNodal) {
        // Gold sand nodal lines
        r = 255; g = 184; b = 0;
      } else if (w > 0) {
        // Crest: Cyan gradient
        const intensity = Math.min(1.0, w);
        r = Math.floor(10 + intensity * 20);
        g = Math.floor(120 + intensity * 135);
        b = Math.floor(180 + intensity * 75);
      } else {
        // Trough: Deep violet gradient
        const intensity = Math.min(1.0, -w);
        r = Math.floor(60 + intensity * 120);
        g = Math.floor(15 + intensity * 40);
        b = Math.floor(110 + intensity * 145);
      }

      // 2x2 pixel block for smooth 60fps render
      for (let dy = 0; dy < 2; dy++) {
        for (let dx = 0; dx < 2; dx++) {
          const pIdx = ((py + dy) * width + (px + dx)) * 4;
          data[pIdx] = r;
          data[pIdx + 1] = g;
          data[pIdx + 2] = b;
          data[pIdx + 3] = 255;
        }
      }
    }
  }

  ctx.putImageData(imgData, 0, 0);
}

// ==========================================================================
// PINN Heat Diffusion Engine
// ==========================================================================

function toggleDiffusionPlay() {
  if (AppState.isDiffusionPlaying) {
    stopDiffusionPlay();
  } else {
    startDiffusionPlay();
  }
}

function startDiffusionPlay() {
  AppState.isDiffusionPlaying = true;
  document.getElementById('btn-play-diffusion').textContent = 'Pause Wave';

  AppState.diffusionTimer = setInterval(() => {
    if (!AppState.currentAnalysis || !AppState.currentAnalysis.diffusion) return;
    const traj = AppState.currentAnalysis.diffusion.trajectory;
    if (!traj) return;

    AppState.diffusionTimeIdx = (AppState.diffusionTimeIdx + 1) % traj.length;
    const times = AppState.currentAnalysis.diffusion.times;
    const curTime = times[AppState.diffusionTimeIdx];

    document.getElementById('slider-time').value = curTime;
    document.getElementById('label-current-time').textContent = curTime.toFixed(2);

    renderDiffusion();
    renderGraph();
  }, 100);
}

function stopDiffusionPlay() {
  AppState.isDiffusionPlaying = false;
  document.getElementById('btn-play-diffusion').textContent = 'Play Wave';
  if (AppState.diffusionTimer) {
    clearInterval(AppState.diffusionTimer);
    AppState.diffusionTimer = null;
  }
}

function renderDiffusion() {
  const canvas = document.getElementById('canvas-diffusion');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;

  ctx.clearRect(0, 0, width, height);

  const diff = (AppState.currentAnalysis && AppState.currentAnalysis.diffusion) ? AppState.currentAnalysis.diffusion : null;
  if (!diff || !diff.trajectory) return;

  const traj = diff.trajectory;
  const currentTemps = traj[AppState.diffusionTimeIdx] || [];
  const numNodes = currentTemps.length;

  if (numNodes === 0) return;

  // Draw Heat Distribution Histogram / Wavefront Bars
  const barWidth = (width - 40) / numNodes;
  const maxVal = Math.max(0.2, ...currentTemps);

  currentTemps.forEach((t, i) => {
    const barHeight = (t / maxVal) * (height - 60);
    const x = 20 + i * barWidth;
    const y = height - 30 - barHeight;

    // Gradient based on heat
    const grad = ctx.createLinearGradient(0, y, 0, height - 30);
    grad.addColorStop(0, '#ff3366');
    grad.addColorStop(0.5, '#ffb800');
    grad.addColorStop(1, '#00ff88');

    ctx.fillStyle = grad;
    ctx.fillRect(x, y, barWidth - 3, barHeight);

    // Node index label
    ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
    ctx.font = '8px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    ctx.fillText(i, x + barWidth / 2, height - 15);
  });

  // Equilibrium Line
  const avgTemp = currentTemps.reduce((a, b) => a + b, 0) / numNodes;
  const eqY = height - 30 - (avgTemp / maxVal) * (height - 60);
  ctx.beginPath();
  ctx.moveTo(20, eqY);
  ctx.lineTo(width - 20, eqY);
  ctx.strokeStyle = 'rgba(0, 240, 255, 0.6)';
  ctx.setLineDash([4, 4]);
  ctx.lineWidth = 1.5;
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.fillStyle = 'rgba(0, 240, 255, 0.8)';
  ctx.font = '9px "Inter", sans-serif';
  ctx.textAlign = 'left';
  ctx.fillText(`Asymptotic Mean u_∞: ${avgTemp.toFixed(3)}`, 24, eqY - 4);
}

// ==========================================================================
// Relativistic State-Space Geodesic Radar
// ==========================================================================

function renderGeodesic() {
  const canvas = document.getElementById('canvas-geodesic');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;

  ctx.clearRect(0, 0, width, height);

  const geo = (AppState.currentAnalysis && AppState.currentAnalysis.geodesic) ? AppState.currentAnalysis.geodesic : null;
  if (!geo) return;

  const cx = width / 2;
  const cy = height / 2;
  const scale = (Math.min(width, height) / 2) * 0.022;

  // 1. Radar Grid Lines
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
  ctx.lineWidth = 1;
  for (let r = 10; r <= 45; r += 10) {
    ctx.beginPath();
    ctx.arc(cx, cy, r * scale, 0, Math.PI * 2);
    ctx.stroke();
  }

  // 2. Event Horizon Boundary (r_+)
  const rPlus = geo.event_horizon_r_plus || 10;
  ctx.beginPath();
  ctx.arc(cx, cy, rPlus * scale, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(10, 10, 16, 0.95)';
  ctx.fill();
  ctx.strokeStyle = '#ff3366';
  ctx.lineWidth = 2.0;
  ctx.stroke();

  // Ergosphere / Frame-dragging vortex
  const spinA = geo.spin_a || 2;
  ctx.beginPath();
  ctx.arc(cx, cy, (rPlus + spinA * 1.5) * scale, 0, Math.PI * 2);
  ctx.strokeStyle = 'rgba(176, 38, 255, 0.35)';
  ctx.setLineDash([3, 3]);
  ctx.stroke();
  ctx.setLineDash([]);

  // 3. Geodesic Trajectory
  const xPts = geo.x_phase || [];
  const yPts = geo.y_phase || [];

  if (xPts.length > 1) {
    ctx.beginPath();
    ctx.moveTo(cx + xPts[0] * scale, cy + yPts[0] * scale);
    for (let i = 1; i < xPts.length; i++) {
      ctx.lineTo(cx + xPts[i] * scale, cy + yPts[i] * scale);
    }
    ctx.strokeStyle = geo.fell_into_horizon_trap ? '#ffb800' : '#00f0ff';
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // End point beacon
    const lastX = cx + xPts[xPts.length - 1] * scale;
    const lastY = cy + yPts[yPts.length - 1] * scale;
    ctx.beginPath();
    ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
    ctx.fillStyle = '#ffffff';
    ctx.fill();
  }

  // Labels
  ctx.fillStyle = '#ff3366';
  ctx.font = '8px "JetBrains Mono", monospace';
  ctx.fillText('EVENT HORIZON r+', cx + rPlus * scale + 4, cy);
}

// ==========================================================================
// Comparison Charts (Spectrum Bar & Anomaly Radar)
// ==========================================================================

function renderCompareCharts() {
  renderCompareSpectrum();
  renderCompareRadar();
}

function renderCompareSpectrum() {
  const canvas = document.getElementById('canvas-compare-spectrum');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;

  ctx.clearRect(0, 0, width, height);

  const cmp = AppState.currentComparison;
  if (!cmp) return;

  const evA = (cmp.program_a_details && cmp.program_a_details.spectrum) ? cmp.program_a_details.spectrum.eigenvalues : [];
  const evB = (cmp.program_b_details && cmp.program_b_details.spectrum) ? cmp.program_b_details.spectrum.eigenvalues : [];

  const modesCount = Math.min(8, Math.max(evA.length, evB.length));
  if (modesCount === 0) return;

  const maxVal = Math.max(1.0, ...evA, ...evB);
  const groupWidth = (width - 60) / modesCount;
  const barWidth = groupWidth * 0.38;

  for (let i = 0; i < modesCount; i++) {
    const valA = evA[i] || 0;
    const valB = evB[i] || 0;

    const x = 30 + i * groupWidth;

    // Bar A (Cyan)
    const hA = (valA / maxVal) * (height - 60);
    ctx.fillStyle = '#00f0ff';
    ctx.fillRect(x, height - 30 - hA, barWidth, hA);

    // Bar B (Emerald)
    const hB = (valB / maxVal) * (height - 60);
    ctx.fillStyle = '#00ff88';
    ctx.fillRect(x + barWidth + 3, height - 30 - hB, barWidth, hB);

    // Label
    ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
    ctx.font = '9px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    ctx.fillText(`λ${i}`, x + barWidth, height - 12);
  }

  // Legend
  ctx.fillStyle = '#00f0ff';
  ctx.fillText('■ V1 Baseline', 60, 20);
  ctx.fillStyle = '#00ff88';
  ctx.fillText('■ V2 Patched', 140, 20);
}

function renderCompareRadar() {
  const canvas = document.getElementById('canvas-compare-radar');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;

  ctx.clearRect(0, 0, width, height);

  const cmp = AppState.currentComparison;
  if (!cmp || !cmp.metrics) return;

  const m = cmp.metrics;
  const cx = width / 2;
  const cy = height / 2;
  const maxR = Math.min(width, height) * 0.38;

  const categories = [
    { label: 'Spectral Continuity', val: Math.max(0, 1.0 - m.spectral_distance_L2 / 5.0) },
    { label: 'Cymatic Resonance', val: m.cymatic_cross_similarity },
    { label: 'Refactor Health', val: m.refactoring_health_score / 100.0 },
    { label: 'Low Coupling Drag', val: Math.max(0, 1.0 - Math.abs(m.frame_dragging_shift) * 5.0) },
    { label: 'Modularity Balance', val: 0.85 }
  ];

  const numAxes = categories.length;
  const angleStep = (Math.PI * 2) / numAxes;

  // Grid rings
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
  ctx.lineWidth = 1;
  for (let ring = 1; ring <= 4; ring++) {
    ctx.beginPath();
    for (let i = 0; i < numAxes; i++) {
      const a = i * angleStep - Math.PI / 2;
      const r = (ring / 4) * maxR;
      const x = cx + r * Math.cos(a);
      const y = cy + r * Math.sin(a);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.stroke();
  }

  // Value Polygon
  ctx.beginPath();
  categories.forEach((cat, i) => {
    const a = i * angleStep - Math.PI / 2;
    const r = Math.max(0.1, Math.min(1.0, cat.val)) * maxR;
    const x = cx + r * Math.cos(a);
    const y = cy + r * Math.sin(a);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.closePath();
  ctx.fillStyle = 'rgba(176, 38, 255, 0.25)';
  ctx.fill();
  ctx.strokeStyle = '#b026ff';
  ctx.lineWidth = 2.0;
  ctx.stroke();

  // Axis labels
  ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
  ctx.font = '9px "Inter", sans-serif';
  categories.forEach((cat, i) => {
    const a = i * angleStep - Math.PI / 2;
    const x = cx + (maxR + 16) * Math.cos(a);
    const y = cy + (maxR + 16) * Math.sin(a);
    ctx.textAlign = Math.abs(Math.cos(a)) < 0.1 ? 'center' : (Math.cos(a) > 0 ? 'left' : 'right');
    ctx.fillText(cat.label, x, y);
  });
}

function resizeAllCanvases() {
  const ids = ['canvas-graph', 'canvas-cymatics', 'canvas-diffusion', 'canvas-geodesic', 'canvas-compare-spectrum', 'canvas-compare-radar'];
  ids.forEach(id => {
    const c = document.getElementById(id);
    if (c && c.parentElement) {
      c.width = c.parentElement.clientWidth;
      c.height = c.parentElement.clientHeight;
    }
  });
}
