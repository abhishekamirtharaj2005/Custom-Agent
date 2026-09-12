/**
 * HermClaw Web Dashboard — Client Application Logic
 * Implements reactive state, interactive Canvas concept graph,
 * live chat console, memory vault, Kanban board, Clawbert pet, and tools sandbox.
 */

// ==========================================================================
// Application State
// ==========================================================================
const state = {
  currentTab: 'overview',
  activeSessionId: null,
  activeMemTab: 'memory',
  overviewData: null,
  sessions: [],
  skills: [],
  tools: [],
  graphData: { nodes: [], edges: [] },
  selectedNode: null,
  selectedTool: null,
  petData: null,
};

// ==========================================================================
// Initialization & Navigation
// ==========================================================================
document.addEventListener('DOMContentLoaded', () => {
  setupNavigation();
  setupModals();
  setupGlobalActions();
  setupChatHandlers();
  setupMemoryHandlers();
  setupKanbanHandlers();
  setupToolsHandlers();
  setupPetHandlers();
  setupDiagnosticsHandlers();
  setupGraphCanvas();

  // Load initial Command Center overview
  loadOverview();

  // Background Telemetry Polling (every 6 seconds)
  setInterval(pollSystemMetrics, 6000);
});

function setupNavigation() {
  const navButtons = document.querySelectorAll('.nav-item');
  const viewTitles = {
    overview: { title: 'Command Center', subtitle: 'Autonomous operations overview & agent health' },
    chat: { title: 'Agent Interactive Console', subtitle: 'Live conversation & transparent tool execution' },
    skills: { title: 'Skills & Reflection', subtitle: 'Hand-authored & self-learning auto-skills registry' },
    graph: { title: 'Concept Learning Graph', subtitle: 'Interactive semantic concept relationships & confidence map' },
    memory: { title: 'Memory & Identity Vault', subtitle: 'Long-term curated memory, user models & personality directives' },
    tasks: { title: 'Tasks & Goals (OKRs)', subtitle: 'Multi-step project boards, quick todos & autonomous milestones' },
    tools: { title: 'Tools Playground', subtitle: 'Catalog of 40+ agent tools and execution sandbox' },
    pet: { title: 'Clawbert & Awards', subtitle: 'Gamified virtual companion & milestone trophy case' },
    diagnostics: { title: 'Doctor & Settings', subtitle: 'Health checks, telemetry and configuration management' },
  };

  navButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.dataset.tab;
      switchTab(targetTab);
    });
  });

  // Shortcut links from overview
  document.getElementById('btn-jump-chat')?.addEventListener('click', () => switchTab('chat'));
  document.getElementById('btn-jump-graph')?.addEventListener('click', () => switchTab('graph'));
}

function switchTab(tabId) {
  state.currentTab = tabId;

  // Update Nav
  document.querySelectorAll('.nav-item').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tabId);
  });

  // Update View Header
  const titles = {
    overview: ['Command Center', 'Autonomous operations overview & agent health'],
    chat: ['Agent Interactive Console', 'Live conversation & transparent tool execution'],
    skills: ['Skills & Reflection', 'Hand-authored & self-learning auto-skills registry'],
    graph: ['Concept Learning Graph', 'Interactive semantic concept relationships & confidence map'],
    memory: ['Memory & Identity Vault', 'Long-term curated memory, user models & personality directives'],
    tasks: ['Tasks & Goals (OKRs)', 'Multi-step project boards, quick todos & autonomous milestones'],
    tools: ['Tools Playground', 'Catalog of 40+ agent tools and execution sandbox'],
    pet: ['Clawbert & Awards', 'Gamified virtual companion & milestone trophy case'],
    diagnostics: ['Doctor & Settings', 'Health checks, telemetry and configuration management'],
  };

  const [t, sub] = titles[tabId] || ['Hermclaw Dashboard', ''];
  document.getElementById('current-view-title').textContent = t;
  document.getElementById('current-view-subtitle').textContent = sub;

  // Update Panes
  document.querySelectorAll('.tab-pane').forEach(p => {
    p.classList.toggle('active', p.id === `pane-${tabId}`);
  });

  // Trigger lazy data loading per tab
  if (tabId === 'overview') loadOverview();
  else if (tabId === 'chat') {
    loadSessionsList();
    fetch('/api/models')
      .then(res => res.json())
      .then(models => populateModelDropdown(models))
      .catch(() => {});
  }
  else if (tabId === 'skills') loadSkills();
  else if (tabId === 'graph') loadLearningGraph();
  else if (tabId === 'memory') loadMemoryFile(state.activeMemTab);
  else if (tabId === 'tasks') { loadKanban(); loadTodos(); loadGoals(); }
  else if (tabId === 'tools') loadToolsCatalog();
  else if (tabId === 'pet') { loadPet(); loadAchievements(); }
  else if (tabId === 'diagnostics') { loadDiagnostics(); loadRawConfig(); loadApiKeysSettings(); }
}

// Toast Notifications
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ==========================================================================
// 1. Overview & Command Center
// ==========================================================================
async function loadOverview() {
  try {
    const res = await fetch('/api/overview');
    const data = await res.json();
    state.overviewData = data;

    // Agent Meta
    document.getElementById('sidebar-agent-profile').textContent = `Profile: ${data.profile}`;
    document.getElementById('sidebar-model-badge').textContent = data.model.name;
    document.getElementById('overview-model-name').textContent = data.model.name;
    document.getElementById('overview-provider-name').textContent = data.model.provider;

    // Ollama Pill
    const pill = document.getElementById('ollama-status-pill');
    const dot = pill.querySelector('.pulse-indicator');
    const pillText = document.getElementById('ollama-status-text');
    if (data.model.ollama_online) {
      dot.className = 'pulse-indicator online';
      const localCount = Array.isArray(data.model.available_models)
        ? data.model.available_models.filter(m => (typeof m === 'object' ? m.type !== 'cloud' : true)).length
        : (data.model.available_models ? data.model.available_models.length : 0);
      pillText.textContent = `Ollama: ${localCount} Models`;
    } else {
      dot.className = 'pulse-indicator offline';
      pillText.textContent = 'Ollama: Offline';
    }

    // Populate model select in chat
    populateModelDropdown(data.model.available_models, data.model.name);
    const sidebarBadge = document.getElementById('sidebar-model-badge');
    if (sidebarBadge && data.model.name) {
      sidebarBadge.textContent = data.model.name;
    }
    const overviewModel = document.getElementById('overview-model-name');
    if (overviewModel && data.model.name) {
      overviewModel.textContent = data.model.name;
    }

    // Stats Grid
    document.getElementById('stat-total-sessions').textContent = data.stats.total_sessions;
    document.getElementById('badge-sessions-count').textContent = data.stats.total_sessions;
    document.getElementById('stat-total-skills').textContent = data.stats.total_skills;
    document.getElementById('badge-skills-count').textContent = data.stats.total_skills;
    document.getElementById('stat-auto-skills-sub').textContent = `${data.stats.auto_skills} auto-generated`;

    document.getElementById('stat-total-concepts').textContent = data.stats.total_concepts;
    document.getElementById('badge-concepts-count').textContent = data.stats.total_concepts;
    document.getElementById('stat-relationships-sub').textContent = `${data.stats.total_relationships} relationships`;

    document.getElementById('stat-active-goals').textContent = data.stats.active_goals;
    document.getElementById('stat-tasks-sub').textContent = `${data.stats.total_tasks} kanban tasks`;

    document.getElementById('overview-pet-summary').textContent = 
      `Clawbert (Level ${data.stats.pet_level}, ${capitalize(data.stats.pet_stage)})`;

    // System Telemetry
    updateTelemetryUI(data.system);

    // Recent Sessions Table
    loadOverviewSessions();

    // Mini Diagnostics
    loadOverviewDiagnostics();
  } catch (err) {
    console.error('Failed to load overview:', err);
  }
}

async function pollSystemMetrics() {
  try {
    const res = await fetch('/api/system');
    const data = await res.json();
    updateTelemetryUI(data);
  } catch (err) {}
}

function updateTelemetryUI(sys) {
  if (!sys) return;
  document.getElementById('quick-cpu-text').textContent = `${sys.cpu_percent}%`;
  document.getElementById('quick-cpu-bar').style.width = `${Math.min(100, sys.cpu_percent)}%`;

  document.getElementById('quick-ram-text').textContent = `${sys.ram_percent}%`;
  document.getElementById('quick-ram-bar').style.width = `${Math.min(100, sys.ram_percent)}%`;
}

async function loadOverviewSessions() {
  try {
    const res = await fetch('/api/sessions?limit=6');
    const sessions = await res.json();
    const tbody = document.getElementById('overview-sessions-tbody');
    if (!sessions || sessions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No session history yet. Start your first conversation!</td></tr>';
      return;
    }
    tbody.innerHTML = sessions.map(s => `
      <tr>
        <td class="font-mono highlight-cyan">${s.id.slice(0, 8)}</td>
        <td><strong>${escapeHtml(s.title)}</strong></td>
        <td><span class="card-badge">${s.channel}</span></td>
        <td class="text-muted text-sm">${s.started_at || '—'}</td>
        <td class="font-mono">${s.total_tokens || 0}</td>
        <td>
          <button class="btn btn-xs btn-outline" onclick="openSession('${s.id}')">Open</button>
        </td>
      </tr>
    `).join('');
  } catch (err) {}
}

async function loadOverviewDiagnostics() {
  try {
    const res = await fetch('/api/doctor');
    const data = await res.json();
    const list = document.getElementById('overview-diagnostics-list');
    list.innerHTML = data.checks.slice(0, 4).map(c => `
      <div class="diag-mini-item">
        <span>${c.name}</span>
        <span class="diag-mini-status ${c.passed ? 'pass' : 'fail'}">${c.passed ? 'PASS' : 'FAIL'}</span>
      </div>
    `).join('');
  } catch (err) {}
}

// ==========================================================================
// 2. Interactive Agent Chat
// ==========================================================================
async function loadSessionsList() {
  try {
    const res = await fetch('/api/sessions');
    state.sessions = await res.json();
    renderSessionsSidebar();

    // If no active session, auto-select first or create one
    if (!state.activeSessionId && state.sessions.length > 0) {
      openSession(state.sessions[0].id);
    } else if (state.sessions.length === 0) {
      document.getElementById('active-session-title').textContent = 'New Conversation';
      document.getElementById('active-session-id').textContent = 'No session';
    }
  } catch (err) {
    console.error('Error loading sessions:', err);
  }
}

function renderSessionsSidebar(filter = '') {
  const container = document.getElementById('chat-sessions-list');
  const filtered = filter 
    ? state.sessions.filter(s => s.title.toLowerCase().includes(filter.toLowerCase()) || s.id.includes(filter))
    : state.sessions;

  if (filtered.length === 0) {
    container.innerHTML = '<div class="text-muted text-sm text-center" style="padding: 1rem;">No sessions found</div>';
    return;
  }

  container.innerHTML = filtered.map(s => `
    <div class="session-item ${s.id === state.activeSessionId ? 'active' : ''}" onclick="openSession('${s.id}')">
      <div class="session-item-title">${escapeHtml(s.title)}</div>
      <div class="session-item-meta">${s.id.slice(0, 8)} • ${s.started_at ? s.started_at.slice(5, 16) : 'recently'}</div>
    </div>
  `).join('');
}

async function openSession(sessionId) {
  state.activeSessionId = sessionId;
  if (state.currentTab !== 'chat') switchTab('chat');

  renderSessionsSidebar();

  const sess = state.sessions.find(s => s.id === sessionId);
  document.getElementById('active-session-title').textContent = sess ? sess.title : `Session ${sessionId.slice(0, 8)}`;
  document.getElementById('active-session-id').textContent = sessionId.slice(0, 8);

  // Fetch messages
  const stream = document.getElementById('chat-messages-stream');
  stream.innerHTML = '<div class="text-center text-muted" style="padding: 2rem;">Loading conversation...</div>';

  try {
    const res = await fetch(`/api/sessions/${sessionId}`);
    const messages = await res.json();
    renderMessages(messages);
  } catch (err) {
    stream.innerHTML = '<div class="text-center text-muted">Failed to load messages.</div>';
  }
}

function renderMessages(messages) {
  const stream = document.getElementById('chat-messages-stream');
  if (!messages || messages.length === 0) {
    stream.innerHTML = `
      <div class="chat-welcome-card">
        <div class="welcome-icon">🦞</div>
        <h3>Session Ready</h3>
        <p>Send a message below to start interacting with Hermclaw.</p>
      </div>
    `;
    return;
  }

  stream.innerHTML = messages.map(m => {
    const isUser = m.role === 'user';
    let toolHtml = '';
    if (m.tool_calls && m.tool_calls.length > 0) {
      toolHtml = m.tool_calls.map(tc => `
        <div class="tool-step-card">
          <div class="tool-step-header" onclick="this.nextElementSibling.classList.toggle('hidden')">
            <span>⚙️ Executed tool: <strong>${escapeHtml(tc.name)}</strong></span>
            <span>▼</span>
          </div>
          <div class="tool-step-output hidden">${escapeHtml(JSON.stringify(tc.arguments, null, 2))}</div>
        </div>
      `).join('');
    }

    return `
      <div class="chat-msg-row ${isUser ? 'user' : 'assistant'}">
        <div class="msg-avatar ${isUser ? 'user' : 'assistant'}">${isUser ? '👤' : '🦞'}</div>
        <div class="msg-bubble">
          ${toolHtml}
          <div>${formatMarkdown(m.content)}</div>
        </div>
      </div>
    `;
  }).join('');

  stream.scrollTop = stream.scrollHeight;
}

function setupChatHandlers() {
  // New session button
  document.getElementById('btn-new-session').addEventListener('click', async () => {
    const title = prompt('Session title (optional):', 'New Conversation');
    try {
      const res = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title || 'New Conversation' }),
      });
      const data = await res.json();
      await loadSessionsList();
      openSession(data.session_id);
    } catch (err) {
      showToast('Failed to create session', 'error');
    }
  });

  document.getElementById('btn-quick-new-chat')?.addEventListener('click', () => {
    document.getElementById('btn-new-session').click();
  });

  // Session search
  document.getElementById('session-search-input')?.addEventListener('input', (e) => {
    renderSessionsSidebar(e.target.value);
  });

  // Send message
  const input = document.getElementById('chat-input-textarea');
  const btnSend = document.getElementById('btn-send-message');

  const sendMessage = async () => {
    const text = input.value.trim();
    if (!text) return;

    if (!state.activeSessionId) {
      // Auto-create session
      const sRes = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: text.slice(0, 30) }),
      });
      const sData = await sRes.json();
      state.activeSessionId = sData.session_id;
      await loadSessionsList();
    }

    // Append user bubble immediately
    const stream = document.getElementById('chat-messages-stream');
    const userRow = document.createElement('div');
    userRow.className = 'chat-msg-row user';
    userRow.innerHTML = `
      <div class="msg-avatar user">👤</div>
      <div class="msg-bubble">${escapeHtml(text)}</div>
    `;
    stream.appendChild(userRow);
    input.value = '';
    stream.scrollTop = stream.scrollHeight;

    // Show Thinking Pill
    const pill = document.getElementById('agent-thinking-pill');
    pill.classList.remove('hidden');

    try {
      const selectedModel = document.getElementById('chat-model-select')?.value;
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: state.activeSessionId,
          message: text,
          model: selectedModel || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        showToast(data.detail || 'Error from agent', 'error');
      }


      // Append assistant bubble
      let toolsHtml = '';
      if (data.tools_executed && data.tools_executed.length > 0) {
        toolsHtml = data.tools_executed.map(te => `
          <div class="tool-step-card">
            <div class="tool-step-header" onclick="this.nextElementSibling.classList.toggle('hidden')">
              <span>🛠️ Tool: <strong>${escapeHtml(te.name)}</strong> (${te.output ? 'Done' : 'Executed'})</span>
              <span>▼</span>
            </div>
            <div class="tool-step-output hidden">${escapeHtml(te.output || JSON.stringify(te.arguments, null, 2))}</div>
          </div>
        `).join('');
      }

      const agentRow = document.createElement('div');
      agentRow.className = 'chat-msg-row assistant';
      agentRow.innerHTML = `
        <div class="msg-avatar assistant">🦞</div>
        <div class="msg-bubble">
          ${toolsHtml}
          <div>${formatMarkdown(data.text || '(empty response)')}</div>
          <div class="text-dim text-sm" style="margin-top: 0.4rem; font-family: var(--font-mono);">
            ⏱️ ${data.elapsed_seconds || 0}s • 🔢 ${data.output_tokens || 0} tokens
          </div>
        </div>
      `;
      stream.appendChild(agentRow);
      stream.scrollTop = stream.scrollHeight;
    } catch (err) {
      showToast('Error communicating with agent', 'error');
    } finally {
      pill.classList.add('hidden');
    }
  };

  btnSend.addEventListener('click', sendMessage);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Slash commands chip clicks
  document.querySelectorAll('.slash-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      input.value = chip.dataset.cmd + ' ';
      input.focus();
    });
  });

  // Welcome prompt chips
  document.querySelectorAll('.chip-shortcuts .chip').forEach(c => {
    c.addEventListener('click', () => {
      input.value = c.dataset.prompt;
      sendMessage();
    });
  });

  // Export session
  document.getElementById('btn-export-session')?.addEventListener('click', async () => {
    if (!state.activeSessionId) return;
    try {
      const res = await fetch(`/api/sessions/${state.activeSessionId}`);
      const msgs = await res.json();
      const blob = new Blob([JSON.stringify(msgs, null, 2)], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `hermclaw_session_${state.activeSessionId.slice(0, 8)}.json`;
      a.click();
      showToast('Session exported to JSON', 'success');
    } catch (err) {
      showToast('Export failed', 'error');
    }
  });

  // Delete session
  document.getElementById('btn-delete-session')?.addEventListener('click', async () => {
    if (!state.activeSessionId) return;
    if (!confirm('Are you sure you want to delete this session?')) return;
    try {
      await fetch(`/api/sessions/${state.activeSessionId}`, { method: 'DELETE' });
      showToast('Session deleted', 'success');
      state.activeSessionId = null;
      await loadSessionsList();
    } catch (err) {
      showToast('Delete failed', 'error');
    }
  });

  // Switch model on dropdown change
  const modelSelect = document.getElementById('chat-model-select');
  modelSelect?.addEventListener('change', async () => {
    const newModel = modelSelect.value;
    if (!newModel) return;
    try {
      const res = await fetch('/api/chat/switch-model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: newModel }),
      });
      const data = await res.json();
      if (res.ok) {
        showToast(`Switched active model to ${newModel}`, 'success');
        const badge = document.getElementById('sidebar-model-badge');
        if (badge) badge.textContent = newModel;
        const ov = document.getElementById('overview-model-name');
        if (ov) ov.textContent = newModel;
      } else {
        showToast(`Model switch failed: ${data.detail || 'Error'}`, 'error');
        await loadOverview();
      }
    } catch (err) {
      showToast('Error switching model', 'error');
    }
  });
}


// ==========================================================================
// 3. Skills Registry & Self-Learning Reflection
// ==========================================================================
async function loadSkills() {
  try {
    const res = await fetch('/api/skills');
    state.skills = await res.json();

    const autoCount = state.skills.filter(s => s.auto_generated).length;
    const handCount = state.skills.length - autoCount;

    document.getElementById('skills-count-all').textContent = state.skills.length;
    document.getElementById('skills-count-auto').textContent = autoCount;
    document.getElementById('skills-count-hand').textContent = handCount;

    renderSkillsGrid(state.skills);
  } catch (err) {
    console.error('Failed to load skills:', err);
  }
}

function renderSkillsGrid(skills) {
  const container = document.getElementById('skills-container-grid');
  if (!skills || skills.length === 0) {
    container.innerHTML = `
      <div class="empty-state-card" style="grid-column: 1 / -1; text-align: center; padding: 2rem;">
        <h4>No skills found in profile directory</h4>
        <p class="text-muted text-sm" style="margin-top: 0.5rem;">
          Run reflection to auto-distill skills from recent repetitive tasks, or add SKILL.md folders.
        </p>
      </div>
    `;
    return;
  }

  container.innerHTML = skills.map(s => `
    <div class="skill-card">
      <div class="skill-card-top">
        <span class="skill-name">${escapeHtml(s.name)}</span>
        <span class="${s.auto_generated ? 'badge-auto' : 'badge-hand'}">
          ${s.auto_generated ? '⚡ Auto-Generated' : '✍️ Hand-Authored'}
        </span>
      </div>
      <p class="skill-desc">${escapeHtml(s.description || 'No description provided.')}</p>
      <div class="skill-actions">
        <button class="btn btn-xs btn-outline" onclick="showSkillBody('${escapeHtml(s.name)}')">View SKILL.md</button>
      </div>
    </div>
  `).join('');
}

// Filter Skills Tabs
document.querySelectorAll('#pane-skills .tab-subnav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#pane-skills .tab-subnav-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    const filter = btn.dataset.filter;
    if (filter === 'auto') {
      renderSkillsGrid(state.skills.filter(s => s.auto_generated));
    } else if (filter === 'hand') {
      renderSkillsGrid(state.skills.filter(s => !s.auto_generated));
    } else {
      renderSkillsGrid(state.skills);
    }
  });
});

function showSkillBody(name) {
  const skill = state.skills.find(s => s.name === name);
  if (!skill) return;
  alert(`SKILL.md for [${skill.name}]:\n\n${skill.body || skill.description}`);
}

// Validation & Reflection Trigger
document.getElementById('btn-validate-skills')?.addEventListener('click', async () => {
  try {
    const res = await fetch('/api/skills/validate', { method: 'POST' });
    const checks = await res.json();
    const allPassed = checks.every(c => c.passed);
    if (allPassed) {
      showToast(`All ${checks.length} skills passed schema validation!`, 'success');
    } else {
      const errCount = checks.filter(c => !c.passed).length;
      showToast(`${errCount} skill(s) failed validation!`, 'error');
    }
  } catch (err) {
    showToast('Validation failed', 'error');
  }
});

async function runReflection() {
  showToast('Running self-learning reflection...', 'info');
  const box = document.getElementById('reflection-results-box');
  box.classList.remove('hidden');

  try {
    const res = await fetch('/api/reflect', { method: 'POST' });
    const data = await res.json();

    document.getElementById('ref-sessions-count').textContent = data.sessions_reviewed;
    document.getElementById('ref-facts-count').textContent = data.facts_saved.length;
    document.getElementById('ref-user-facts-count').textContent = data.user_facts_saved.length;
    document.getElementById('ref-skills-count').textContent = data.draft_skills_created.length;

    const logBox = document.getElementById('ref-details-log');
    let logLines = [];
    if (data.facts_saved.length > 0) {
      logLines.push('<b>Learned Facts:</b>');
      data.facts_saved.forEach(f => logLines.push(`• ${escapeHtml(f)}`));
    }
    if (data.draft_skills_created.length > 0) {
      logLines.push('<b>New Auto-Skills Created:</b>');
      data.draft_skills_created.forEach(sk => logLines.push(`• ${escapeHtml(sk)}`));
    }
    logBox.innerHTML = logLines.length > 0 ? logLines.join('<br>') : '<span class="text-muted">No new facts or skills to distill in this turn.</span>';

    showToast('Reflection complete!', 'success');
    loadSkills();
    loadOverview();
  } catch (err) {
    showToast('Reflection failed: ' + err.message, 'error');
  }
}

document.getElementById('btn-trigger-reflect-tab')?.addEventListener('click', runReflection);
document.getElementById('btn-global-reflect')?.addEventListener('click', runReflection);
document.getElementById('btn-close-reflection-results')?.addEventListener('click', () => {
  document.getElementById('reflection-results-box').classList.add('hidden');
});

// ==========================================================================
// 4. Concept Learning Graph (Interactive HTML5 Canvas)
// ==========================================================================
let graphCtx = null;
let graphNodes = [];
let graphEdges = [];
let draggedNode = null;
let transform = { x: 0, y: 0, k: 1 };
let isPanning = false;
let startPan = { x: 0, y: 0 };

function setupGraphCanvas() {
  const canvas = document.getElementById('learning-graph-canvas');
  if (!canvas) return;
  graphCtx = canvas.getContext('2d');

  function resize() {
    canvas.width = canvas.parentElement.clientWidth;
    canvas.height = canvas.parentElement.clientHeight;
  }
  window.addEventListener('resize', resize);
  resize();

  // Mouse interaction for pan & drag
  canvas.addEventListener('mousedown', (e) => {
    const rect = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left - transform.x) / transform.k;
    const my = (e.clientY - rect.top - transform.y) / transform.k;

    // Check hit on node
    for (let i = graphNodes.length - 1; i >= 0; i--) {
      const n = graphNodes[i];
      const dx = mx - n.x;
      const dy = my - n.y;
      if (Math.sqrt(dx * dx + dy * dy) <= (n.radius || 20)) {
        draggedNode = n;
        selectGraphNode(n);
        return;
      }
    }

    // Otherwise pan
    isPanning = true;
    startPan = { x: e.clientX - transform.x, y: e.clientY - transform.y };
  });

  window.addEventListener('mousemove', (e) => {
    if (draggedNode) {
      const rect = canvas.getBoundingClientRect();
      draggedNode.x = (e.clientX - rect.left - transform.x) / transform.k;
      draggedNode.y = (e.clientY - rect.top - transform.y) / transform.k;
      draggedNode.vx = 0;
      draggedNode.vy = 0;
    } else if (isPanning) {
      transform.x = e.clientX - startPan.x;
      transform.y = e.clientY - startPan.y;
    }
  });

  window.addEventListener('mouseup', () => {
    draggedNode = null;
    isPanning = false;
  });

  canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    transform.k = Math.max(0.3, Math.min(3, transform.k * zoomFactor));
  });

  document.getElementById('btn-reset-graph')?.addEventListener('click', () => {
    transform = { x: canvas.width / 2, y: canvas.height / 2, k: 1 };
  });

  // Start physics animation loop
  requestAnimationFrame(graphAnimationLoop);
}

async function loadLearningGraph() {
  try {
    const res = await fetch('/api/learning-graph');
    const data = await res.json();
    state.graphData = data;

    const canvas = document.getElementById('learning-graph-canvas');
    const w = canvas.width || 800;
    const h = canvas.height || 500;

    transform = { x: w / 2, y: h / 2, k: 1 };

    // Initialize node coordinates in a circular spread
    const n = data.nodes.length;
    graphNodes = data.nodes.map((node, i) => {
      const angle = (i / (n || 1)) * 2 * Math.PI;
      const radius = 120 + Math.random() * 80;
      return {
        ...node,
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
        vx: 0,
        vy: 0,
        radius: 20 + Math.min(15, (node.usage_count || 1) * 2),
      };
    });

    graphEdges = data.edges;

    if (graphNodes.length > 0) {
      selectGraphNode(graphNodes[0]);
    }
  } catch (err) {
    console.error('Failed to load learning graph:', err);
  }
}

function selectGraphNode(node) {
  state.selectedNode = node;
  document.getElementById('inspector-concept-name').textContent = node.name;
  document.getElementById('inspector-concept-cat').textContent = node.category;
  document.getElementById('inspector-concept-desc').textContent = node.description || 'No description recorded.';
  document.getElementById('inspector-concept-conf').textContent = `${Math.round((node.confidence || 0.5) * 100)}%`;
  document.getElementById('inspector-conf-bar').style.width = `${Math.round((node.confidence || 0.5) * 100)}%`;
  document.getElementById('inspector-concept-usage').textContent = `${node.usage_count || 0} times`;

  // Find relationships
  const rels = graphEdges.filter(e => e.source_name === node.name.toLowerCase() || e.target_name === node.name.toLowerCase());
  const relsBox = document.getElementById('inspector-rels-container');
  if (rels.length === 0) {
    relsBox.innerHTML = '<span class="text-muted text-sm">No connected relationships yet.</span>';
  } else {
    relsBox.innerHTML = rels.map(r => `
      <div class="rel-tag-item">
        <span>${escapeHtml(r.source_name)} ➔ ${escapeHtml(r.target_name)}</span>
        <span class="highlight-cyan">[${r.relation_type}]</span>
      </div>
    `).join('');
  }
}

function graphAnimationLoop() {
  if (state.currentTab === 'graph' && graphCtx) {
    updateGraphPhysics();
    renderGraphCanvas();
  }
  requestAnimationFrame(graphAnimationLoop);
}

function updateGraphPhysics() {
  // Simple force-directed physics
  const repulsion = 800;
  const springLength = 140;
  const springK = 0.04;
  const damping = 0.85;

  // Repulsion between nodes
  for (let i = 0; i < graphNodes.length; i++) {
    for (let j = i + 1; j < graphNodes.length; j++) {
      const n1 = graphNodes[i];
      const n2 = graphNodes[j];
      const dx = n2.x - n1.x;
      const dy = n2.y - n1.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      if (dist < 300) {
        const force = repulsion / (dist * dist);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        n1.vx -= fx;
        n1.vy -= fy;
        n2.vx += fx;
        n2.vy += fy;
      }
    }
  }

  // Edge spring attraction
  graphEdges.forEach(e => {
    const s = graphNodes.find(n => n.name.toLowerCase() === e.source_name);
    const t = graphNodes.find(n => n.name.toLowerCase() === e.target_name);
    if (s && t) {
      const dx = t.x - s.x;
      const dy = t.y - s.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = (dist - springLength) * springK;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      s.vx += fx;
      s.vy += fy;
      t.vx -= fx;
      t.vy -= fy;
    }
  });

  // Apply velocities
  graphNodes.forEach(n => {
    if (n !== draggedNode) {
      n.x += n.vx;
      n.y += n.vy;
      n.vx *= damping;
      n.vy *= damping;
    }
  });
}

function renderGraphCanvas() {
  const canvas = graphCtx.canvas;
  graphCtx.clearRect(0, 0, canvas.width, canvas.height);

  graphCtx.save();
  graphCtx.translate(transform.x, transform.y);
  graphCtx.scale(transform.k, transform.k);

  // Draw Edges
  graphEdges.forEach(e => {
    const s = graphNodes.find(n => n.name.toLowerCase() === e.source_name);
    const t = graphNodes.find(n => n.name.toLowerCase() === e.target_name);
    if (s && t) {
      graphCtx.beginPath();
      graphCtx.moveTo(s.x, s.y);
      graphCtx.lineTo(t.x, t.y);
      graphCtx.strokeStyle = 'rgba(255, 255, 255, 0.18)';
      graphCtx.lineWidth = 1.5;
      graphCtx.stroke();

      // Relation label at midpoint
      const mx = (s.x + t.x) / 2;
      const my = (s.y + t.y) / 2;
      graphCtx.fillStyle = '#64748b';
      graphCtx.font = '10px JetBrains Mono';
      graphCtx.textAlign = 'center';
      graphCtx.fillText(e.relation_type, mx, my - 4);
    }
  });

  // Draw Nodes
  const colors = {
    programming: '#00f2fe',
    tools: '#9d4edd',
    devops: '#10b981',
    general: '#f59e0b',
  };

  graphNodes.forEach(n => {
    const col = colors[n.category] || colors.general;
    const isSelected = state.selectedNode && state.selectedNode.name === n.name;

    // Node Glow
    graphCtx.beginPath();
    graphCtx.arc(n.x, n.y, n.radius + (isSelected ? 6 : 2), 0, 2 * Math.PI);
    graphCtx.fillStyle = isSelected ? 'rgba(0, 242, 254, 0.3)' : 'rgba(255, 255, 255, 0.05)';
    graphCtx.fill();

    // Main Circle
    graphCtx.beginPath();
    graphCtx.arc(n.x, n.y, n.radius, 0, 2 * Math.PI);
    graphCtx.fillStyle = '#0f172a';
    graphCtx.fill();
    graphCtx.strokeStyle = col;
    graphCtx.lineWidth = isSelected ? 3 : 2;
    graphCtx.stroke();

    // Node Name
    graphCtx.fillStyle = '#fff';
    graphCtx.font = 'bold 11px Outfit, sans-serif';
    graphCtx.textAlign = 'center';
    graphCtx.textBaseline = 'middle';
    graphCtx.fillText(n.name, n.x, n.y);
  });

  graphCtx.restore();
}

// ==========================================================================
// 5. Memory & Identity Vault
// ==========================================================================
function setupMemoryHandlers() {
  const tabs = document.querySelectorAll('#pane-memory .tab-subnav-btn');
  tabs.forEach(btn => {
    btn.addEventListener('click', () => {
      tabs.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const memtab = btn.dataset.memtab;
      state.activeMemTab = memtab;

      if (memtab === 'vector') {
        document.getElementById('mem-editor-box').classList.add('hidden');
        document.getElementById('vector-search-box').classList.remove('hidden');
      } else {
        document.getElementById('mem-editor-box').classList.remove('hidden');
        document.getElementById('vector-search-box').classList.add('hidden');
        loadMemoryFile(memtab);
      }
    });
  });

  // Save memory file
  document.getElementById('btn-save-memory-file')?.addEventListener('click', async () => {
    if (state.activeMemTab === 'vector') return;
    const content = document.getElementById('memfile-textarea').value;
    try {
      const res = await fetch(`/api/memory/${state.activeMemTab}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });
      const data = await res.json();
      if (data.saved) {
        showToast(`${state.activeMemTab.toUpperCase()}.md saved successfully!`, 'success');
      }
    } catch (err) {
      showToast('Failed to save file', 'error');
    }
  });

  // Vector memory search
  document.getElementById('btn-run-vector-search')?.addEventListener('click', async () => {
    const q = document.getElementById('vector-query-input').value.trim();
    if (!q) return;
    const list = document.getElementById('vector-results-list');
    list.innerHTML = '<div class="text-center text-muted">Searching vector memory...</div>';

    try {
      const res = await fetch(`/api/vector-memory/search?q=${encodeURIComponent(q)}`);
      const results = await res.json();
      if (!results || results.length === 0) {
        list.innerHTML = '<div class="empty-state-card text-center text-muted">No semantic matches found.</div>';
        return;
      }
      list.innerHTML = results.map(r => `
        <div class="col-card" style="padding: 0.85rem;">
          <div style="display: flex; justify-content: space-between; margin-bottom: 0.35rem;">
            <span class="highlight-cyan font-mono text-sm">Score: ${r.score.toFixed(3)}</span>
          </div>
          <p style="font-size: 0.85rem; line-height: 1.45;">${escapeHtml(r.content)}</p>
        </div>
      `).join('');
    } catch (err) {
      list.innerHTML = '<div class="empty-state-card text-center text-muted">Vector search error.</div>';
    }
  });
}

async function loadMemoryFile(type) {
  const textarea = document.getElementById('memfile-textarea');
  const pathBadge = document.getElementById('active-memfile-path');
  pathBadge.textContent = `~/.hermclaw/profiles/default/${type.toUpperCase()}.md`;
  textarea.value = 'Loading file contents...';

  try {
    const res = await fetch(`/api/memory/${type}`);
    const data = await res.json();
    textarea.value = data.content || '';
  } catch (err) {
    textarea.value = 'Failed to load file contents.';
  }
}

// ==========================================================================
// 6. Tasks, Kanban & Autonomous Goals
// ==========================================================================
function setupKanbanHandlers() {
  document.getElementById('btn-modal-add-task')?.addEventListener('click', () => {
    document.getElementById('modal-add-task').classList.remove('hidden');
  });

  document.getElementById('btn-modal-add-goal')?.addEventListener('click', () => {
    document.getElementById('modal-add-goal').classList.remove('hidden');
  });

  // Submit task
  document.getElementById('btn-submit-task')?.addEventListener('click', async () => {
    const title = document.getElementById('task-title-input').value.trim();
    const desc = document.getElementById('task-desc-input').value.trim();
    const col = document.getElementById('task-column-select').value;
    const prio = document.getElementById('task-priority-select').value;
    if (!title) return;

    try {
      const kData = await (await fetch('/api/kanban')).json();
      const boardId = kData.current_board.id || kData.boards[0].id;

      await fetch('/api/kanban/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ board_id: boardId, column_name: col, title, description: desc, priority: prio }),
      });
      document.getElementById('modal-add-task').classList.add('hidden');
      document.getElementById('task-title-input').value = '';
      document.getElementById('task-desc-input').value = '';
      showToast('Task added!', 'success');
      loadKanban();
    } catch (err) {
      showToast('Error creating task', 'error');
    }
  });

  // Submit Goal
  document.getElementById('btn-submit-goal')?.addEventListener('click', async () => {
    const title = document.getElementById('goal-title-input').value.trim();
    const desc = document.getElementById('goal-desc-input').value.trim();
    const prio = document.getElementById('goal-priority-select').value;
    if (!title) return;

    try {
      await fetch('/api/goals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, description: desc, priority: prio }),
      });
      document.getElementById('modal-add-goal').classList.add('hidden');
      document.getElementById('goal-title-input').value = '';
      document.getElementById('goal-desc-input').value = '';
      showToast('Goal created!', 'success');
      loadGoals();
    } catch (err) {
      showToast('Error creating goal', 'error');
    }
  });

  // Quick Todo Add
  document.getElementById('btn-add-todo')?.addEventListener('click', async () => {
    const input = document.getElementById('new-todo-input');
    const text = input.value.trim();
    if (!text) return;
    try {
      await fetch('/api/todos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, priority: 'medium' }),
      });
      input.value = '';
      loadTodos();
    } catch (err) {}
  });
}

async function loadKanban() {
  try {
    const res = await fetch('/api/kanban');
    const data = await res.json();
    const board = data.current_board;
    if (!board || !board.columns) return;

    const colMap = {
      'Backlog': document.getElementById('col-list-backlog'),
      'In Progress': document.getElementById('col-list-progress'),
      'Review': document.getElementById('col-list-review'),
      'Done': document.getElementById('col-list-done'),
    };

    const countMap = {
      'Backlog': document.getElementById('count-col-backlog'),
      'In Progress': document.getElementById('count-col-progress'),
      'Review': document.getElementById('count-col-review'),
      'Done': document.getElementById('count-col-done'),
    };

    // Reset columns
    Object.values(colMap).forEach(el => { if (el) el.innerHTML = ''; });

    board.columns.forEach(col => {
      const target = colMap[col.name];
      const countEl = countMap[col.name];
      if (countEl) countEl.textContent = col.tasks.length;
      if (!target) return;

      target.innerHTML = col.tasks.map(t => `
        <div class="kanban-task-card" id="task-${t.id}">
          <div class="task-card-title">${escapeHtml(t.title)}</div>
          ${t.description ? `<div class="task-card-desc">${escapeHtml(t.description)}</div>` : ''}
          <div class="task-card-bottom">
            <span class="priority-pill priority-${t.priority}">${t.priority}</span>
            <select class="task-move-select" onchange="moveTask('${t.id}', this.value)">
              <option value="">Move ➔</option>
              <option value="Backlog">Backlog</option>
              <option value="In Progress">In Progress</option>
              <option value="Review">Review</option>
              <option value="Done">Done</option>
            </select>
          </div>
        </div>
      `).join('');
    });
  } catch (err) {
    console.error('Failed to load kanban:', err);
  }
}

async function moveTask(taskId, colName) {
  if (!colName) return;
  try {
    await fetch('/api/kanban/move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: taskId, column_name: colName }),
    });
    loadKanban();
  } catch (err) {}
}

async function loadTodos() {
  try {
    const res = await fetch('/api/todos');
    const todos = await res.json();
    const container = document.getElementById('todos-container-list');
    const pending = todos.filter(t => !t.done).length;
    document.getElementById('todos-badge-count').textContent = `${pending} pending`;

    container.innerHTML = todos.map(t => `
      <div class="todo-item-row ${t.done ? 'done' : ''}">
        <input type="checkbox" ${t.done ? 'checked' : ''} onchange="toggleTodo('${t.id}', this.checked)">
        <span style="flex: 1; font-size: 0.82rem;">${escapeHtml(t.text)}</span>
        <button class="btn-close-sm" onclick="deleteTodo('${t.id}')">✕</button>
      </div>
    `).join('');
  } catch (err) {}
}

async function toggleTodo(id, done) {
  await fetch(`/api/todos/${id}/toggle`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ done }),
  });
  loadTodos();
}

async function deleteTodo(id) {
  await fetch(`/api/todos/${id}`, { method: 'DELETE' });
  loadTodos();
}

async function loadGoals() {
  try {
    const res = await fetch('/api/goals');
    const goals = await res.json();
    const container = document.getElementById('goals-container-list');
    if (!goals || goals.length === 0) {
      container.innerHTML = '<div class="text-muted text-sm text-center">No active goals. Add an autonomous OKR above!</div>';
      return;
    }

    container.innerHTML = goals.map(g => `
      <div class="goal-card-item">
        <div class="goal-top-row">
          <span class="goal-title">${escapeHtml(g.title)}</span>
          <span class="priority-pill priority-${g.priority}">${g.status}</span>
        </div>
        ${g.description ? `<p style="font-size: 0.78rem; color: var(--text-muted);">${escapeHtml(g.description)}</p>` : ''}
        <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted);">
          <span>Progress:</span>
          <span class="highlight-cyan font-mono">${g.progress}%</span>
        </div>
        <div class="progress-bar-bg"><div class="progress-bar-fill cyan" style="width: ${g.progress}%;"></div></div>
        <div style="display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.35rem;">
          <button class="btn btn-xs btn-outline" onclick="bumpGoalProgress('${g.id}', ${g.progress + 25})">+25%</button>
          <button class="btn btn-xs btn-danger-ghost" onclick="deleteGoal('${g.id}')">✕</button>
        </div>
      </div>
    `).join('');
  } catch (err) {}
}

async function bumpGoalProgress(goalId, newProg) {
  await fetch(`/api/goals/${goalId}/progress`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ progress: Math.min(100, newProg), log_entry: 'Updated via dashboard' }),
  });
  loadGoals();
}

async function deleteGoal(goalId) {
  await fetch(`/api/goals/${goalId}`, { method: 'DELETE' });
  loadGoals();
}

// ==========================================================================
// 7. Tools Directory & Playground
// ==========================================================================
async function loadToolsCatalog() {
  try {
    const res = await fetch('/api/tools');
    state.tools = await res.json();
    renderToolsGrid(state.tools);
    if (state.tools.length > 0) {
      selectToolPlayground(state.tools[0]);
    }
  } catch (err) {
    console.error('Failed to load tools:', err);
  }
}

function renderToolsGrid(tools) {
  const container = document.getElementById('tools-catalog-list');
  container.innerHTML = tools.map(t => `
    <div class="tool-info-card" onclick="selectToolByName('${t.name}')">
      <div class="tool-card-name">🛠️ ${escapeHtml(t.name)}</div>
      <p class="tool-card-desc">${escapeHtml(t.description || 'No description.')}</p>
    </div>
  `).join('');
}

function selectToolByName(name) {
  const tool = state.tools.find(t => t.name === name);
  if (tool) selectToolPlayground(tool);
}

function selectToolPlayground(tool) {
  state.selectedTool = tool;
  document.getElementById('play-tool-name').textContent = `🛠️ ${tool.name}`;
  document.getElementById('play-tool-desc').textContent = tool.description;

  // Build sample JSON args based on tool parameters schema
  const sample = {};
  if (tool.parameters && tool.parameters.properties) {
    Object.keys(tool.parameters.properties).forEach(k => {
      const p = tool.parameters.properties[k];
      sample[k] = p.default || (p.type === 'string' ? '' : p.type === 'boolean' ? false : 0);
    });
  }
  document.getElementById('tool-args-textarea').value = JSON.stringify(sample, null, 2);
  document.getElementById('tool-output-box').textContent = 'Awaiting execution...';
}

function setupToolsHandlers() {
  // Search tool
  document.getElementById('tool-search-input')?.addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase();
    const filtered = state.tools.filter(t => t.name.toLowerCase().includes(q) || (t.description || '').toLowerCase().includes(q));
    renderToolsGrid(filtered);
  });

  // Run Tool Playground
  document.getElementById('btn-run-tool-playground')?.addEventListener('click', async () => {
    if (!state.selectedTool) return;
    const outBox = document.getElementById('tool-output-box');
    const elapsedEl = document.getElementById('tool-run-elapsed');
    outBox.textContent = 'Executing tool...';

    let args = {};
    try {
      args = JSON.parse(document.getElementById('tool-args-textarea').value);
    } catch (err) {
      outBox.textContent = 'Error: Invalid JSON arguments!';
      return;
    }

    try {
      const res = await fetch('/api/tools/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool_name: state.selectedTool.name, arguments: args }),
      });
      const data = await res.json();
      elapsedEl.textContent = `Elapsed: ${data.elapsed_seconds || 0}s`;
      outBox.textContent = data.ok 
        ? (data.output || '(Execution returned empty success)')
        : `Execution Error: ${data.error}`;
    } catch (err) {
      outBox.textContent = 'Execution failed: ' + err.message;
    }
  });
}

// ==========================================================================
// 8. Virtual Pet (Clawbert) & Achievements
// ==========================================================================
async function loadPet() {
  try {
    const res = await fetch('/api/pet');
    const data = await res.json();
    state.petData = data;

    document.getElementById('pet-name').textContent = data.name || 'Clawbert';
    document.getElementById('pet-stage-badge').textContent = `${capitalize(data.stage || 'egg')} Stage`;
    document.getElementById('pet-mood-tag').textContent = `Mood: ${capitalize(data.mood || 'curious')} ${data.emote || ''}`;
    document.getElementById('pet-ascii-art').textContent = data.art || '';

    // Meters
    document.getElementById('pet-hunger-val').textContent = `${data.hunger || 0}%`;
    document.getElementById('pet-hunger-bar').style.width = `${data.hunger || 0}%`;

    document.getElementById('pet-energy-val').textContent = `${data.energy || 0}%`;
    document.getElementById('pet-energy-bar').style.width = `${data.energy || 0}%`;

    document.getElementById('pet-happy-val').textContent = `${data.happiness || 0}%`;
    document.getElementById('pet-happy-bar').style.width = `${data.happiness || 0}%`;

    document.getElementById('pet-level-val').textContent = `Lv. ${data.level || 1} (${data.experience || 0} XP)`;
    document.getElementById('pet-xp-bar').style.width = `${Math.min(100, (data.experience || 0) % 100)}%`;
  } catch (err) {
    console.error('Failed to load pet:', err);
  }
}

function setupPetHandlers() {
  document.querySelectorAll('.btn-pet-act').forEach(btn => {
    btn.addEventListener('click', async () => {
      const act = btn.dataset.action;
      try {
        const res = await fetch('/api/pet/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: act }),
        });
        const data = await res.json();
        const toastEl = document.getElementById('pet-action-toast');
        toastEl.textContent = `✨ ${data.name} responded to ${act}!`;
        setTimeout(() => toastEl.textContent = '', 4000);
        loadPet();
      } catch (err) {
        showToast('Pet action failed', 'error');
      }
    });
  });
}

async function loadAchievements() {
  try {
    const res = await fetch('/api/achievements');
    const list = await res.json();
    const container = document.getElementById('achievements-grid');
    const unlockedCount = list.filter(a => a.unlocked).length;
    document.getElementById('achievements-unlocked-badge').textContent = `${unlockedCount} / ${list.length} Unlocked`;

    container.innerHTML = list.map(a => `
      <div class="ach-badge-card ${a.unlocked ? 'unlocked' : ''}">
        <div class="ach-icon">${a.unlocked ? '🏆' : '🔒'}</div>
        <div>
          <div class="ach-name">${escapeHtml(a.name)}</div>
          <div class="ach-desc">${escapeHtml(a.description)}</div>
        </div>
      </div>
    `).join('');
  } catch (err) {}
}

// ==========================================================================
// 9. Doctor & System Settings
// ==========================================================================
async function loadDiagnostics() {
  try {
    const res = await fetch('/api/doctor');
    const data = await res.json();

    const badge = document.getElementById('doctor-overall-badge');
    badge.textContent = data.all_passed ? 'ALL PASSED' : 'ACTION REQUIRED';
    badge.className = `card-badge ${data.all_passed ? 'success' : 'danger'}`;

    const container = document.getElementById('doctor-checks-list');
    container.innerHTML = data.checks.map(c => `
      <div class="doctor-check-row">
        <div>
          <div class="doc-name">${c.name}</div>
          <div class="doc-detail">${escapeHtml(c.detail)}</div>
        </div>
        <span class="diag-mini-status ${c.passed ? 'pass' : 'fail'}">${c.passed ? 'PASS' : 'FAIL'}</span>
      </div>
    `).join('');
  } catch (err) {}
}

async function loadRawConfig() {
  try {
    const res = await fetch('/api/config');
    const data = await res.json();
    document.getElementById('config-yaml-textarea').value = data.raw_yaml || '';
  } catch (err) {}
}

async function loadApiKeysSettings() {
  try {
    const res = await fetch('/api/settings/keys');
    if (!res.ok) return;
    const providers = await res.json();
    providers.forEach(p => {
      const badge = document.getElementById(`badge-key-${p.id}`);
      const input = document.getElementById(`input-key-${p.id}`);
      if (badge) {
        if (p.configured) {
          badge.className = 'badge-configured';
          badge.textContent = `✓ Configured (${p.preview})`;
        } else {
          badge.className = 'badge-not-set';
          badge.textContent = 'Not Set';
        }
      }
      if (input) {
        input.placeholder = p.configured ? `Configured (${p.preview}) - enter new to change` : p.placeholder;
      }
    });
  } catch (err) {
    console.error('Failed to load API keys status:', err);
  }
}

async function saveApiKeysSettings() {
  const btn = document.getElementById('btn-save-api-keys');
  const toast = document.getElementById('api-keys-toast');
  const originalText = btn ? btn.textContent : 'Save API Keys';
  if (btn) {
    btn.textContent = 'Saving...';
    btn.disabled = true;
  }

  const payload = {};
  const mapping = {
    openai: 'OPENAI_API_KEY',
    anthropic: 'ANTHROPIC_API_KEY',
    gemini: 'GEMINI_API_KEY',
    groq: 'GROQ_API_KEY',
    deepseek: 'DEEPSEEK_API_KEY',
    openrouter: 'OPENROUTER_API_KEY',
  };

  Object.entries(mapping).forEach(([id, envKey]) => {
    const input = document.getElementById(`input-key-${id}`);
    if (input && input.value.trim()) {
      payload[envKey] = input.value.trim();
    }
  });

  try {
    const res = await fetch('/api/settings/keys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keys: payload }),
    });
    const data = await res.json();
    if (res.ok) {
      showToast('Cloud LLM API keys saved! Models unlocked in chat.', 'success');
      if (toast) {
        toast.className = 'alert-banner success';
        toast.textContent = '✓ Cloud LLM API keys saved successfully. Associated models are now unlocked in the Chat LLM dropdown.';
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), 5000);
      }
      // Clear entered values for security
      Object.keys(mapping).forEach(id => {
        const input = document.getElementById(`input-key-${id}`);
        if (input) input.value = '';
      });
      // Refresh status and model dropdown
      await loadApiKeysSettings();
      await loadOverview();
    } else {
      showToast(`Error: ${data.detail || 'Could not save keys'}`, 'error');
      if (toast) {
        toast.className = 'alert-banner error';
        toast.textContent = `Error saving API keys: ${data.detail || 'Unknown error'}`;
        toast.classList.remove('hidden');
      }
    }
  } catch (err) {
    showToast('Failed to save API keys', 'error');
  } finally {
    if (btn) {
      btn.textContent = originalText;
      btn.disabled = false;
    }
  }
}

function populateModelDropdown(models, currentModel) {
  const modelSelect = document.getElementById('chat-model-select');
  if (!modelSelect) return;

  if (!models || !Array.isArray(models) || models.length === 0) {
    modelSelect.innerHTML = '<option value="gemma4:12b">gemma4:12b [Local]</option>';
    return;
  }

  const currentVal = currentModel || modelSelect.value;
  const localModels = [];
  const cloudByProvider = {};

  models.forEach(m => {
    let id = '';
    let label = '';
    let isCloud = false;
    let provider = 'other';

    if (typeof m === 'string') {
      id = m;
      label = `${m} [Local]`;
      isCloud = false;
      provider = 'ollama';
    } else if (typeof m === 'object' && m !== null) {
      id = m.id || m.name || '';
      isCloud = m.type === 'cloud';
      provider = m.provider || (isCloud ? 'other' : 'ollama');
      label = m.display_label || (isCloud ? `${id} [Cloud - ${provider}]` : `${id} [Local]`);
    }

    if (!id || typeof id !== 'string') return;

    if (!isCloud) {
      localModels.push({ id, label });
    } else {
      if (!cloudByProvider[provider]) cloudByProvider[provider] = [];
      cloudByProvider[provider].push({ id, label });
    }
  });

  let html = '';
  if (localModels.length > 0) {
    html += '<optgroup label="Local Models (Ollama)">';
    localModels.forEach(m => {
      html += `<option value="${escapeHtml(m.id)}" ${m.id === currentVal ? 'selected' : ''}>${escapeHtml(m.label)}</option>`;
    });
    html += '</optgroup>';
  }

  const providerDisplayNames = {
    openai: 'Cloud Models (OpenAI)',
    anthropic: 'Cloud Models (Anthropic Claude)',
    gemini: 'Cloud Models (Google Gemini)',
    groq: 'Cloud Models (Groq)',
    deepseek: 'Cloud Models (DeepSeek)',
    openrouter: 'Cloud Models (OpenRouter)',
  };

  Object.keys(cloudByProvider).forEach(p => {
    const groupLabel = providerDisplayNames[p] || `Cloud Models (${p.toUpperCase()})`;
    html += `<optgroup label="${escapeHtml(groupLabel)}">`;
    cloudByProvider[p].forEach(m => {
      html += `<option value="${escapeHtml(m.id)}" ${m.id === currentVal ? 'selected' : ''}>${escapeHtml(m.label)}</option>`;
    });
    html += '</optgroup>';
  });

  if (!html) {
    html = '<option value="gemma4:12b">gemma4:12b [Local]</option>';
  }

  modelSelect.innerHTML = html;
}

function setupDiagnosticsHandlers() {
  document.getElementById('btn-run-doctor-full')?.addEventListener('click', () => {
    showToast('Re-running diagnostics...', 'info');
    loadDiagnostics();
  });

  document.getElementById('btn-save-yaml-config')?.addEventListener('click', async () => {
    const yaml_content = document.getElementById('config-yaml-textarea').value;
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ yaml_content }),
      });
      const data = await res.json();
      if (data.accepted) {
        showToast('Configuration updated and reloaded!', 'success');
      } else {
        showToast(`Config error: ${data.errors.join('; ')}`, 'error');
      }
    } catch (err) {
      showToast('Failed to save config', 'error');
    }
  });

  // Save API keys button
  document.getElementById('btn-save-api-keys')?.addEventListener('click', saveApiKeysSettings);

  // Eye toggles for password visibility
  document.querySelectorAll('.btn-toggle-eye').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.dataset.target;
      const input = document.getElementById(targetId);
      if (!input) return;
      if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = '🙈';
      } else {
        input.type = 'password';
        btn.textContent = '👁';
      }
    });
  });

  // Initial load of API keys status
  loadApiKeysSettings();
}


// ==========================================================================
// Modals & Global Helpers
// ==========================================================================
function setupModals() {
  document.querySelectorAll('[data-close]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.getElementById(btn.dataset.close).classList.add('hidden');
    });
  });

  // Concept modal triggers
  document.getElementById('btn-modal-add-concept')?.addEventListener('click', () => {
    document.getElementById('modal-add-concept').classList.remove('hidden');
  });

  document.getElementById('btn-modal-add-rel')?.addEventListener('click', () => {
    document.getElementById('modal-add-rel').classList.remove('hidden');
  });

  // Submit Concept
  document.getElementById('btn-submit-concept')?.addEventListener('click', async () => {
    const name = document.getElementById('concept-name-input').value.trim();
    const category = document.getElementById('concept-cat-select').value;
    const desc = document.getElementById('concept-desc-input').value.trim();
    const conf = parseFloat(document.getElementById('concept-conf-input').value) || 0.8;
    if (!name) return;

    try {
      await fetch('/api/learning-graph/concept', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, category, description: desc, confidence: conf }),
      });
      document.getElementById('modal-add-concept').classList.add('hidden');
      document.getElementById('concept-name-input').value = '';
      showToast('Concept added to graph!', 'success');
      loadLearningGraph();
    } catch (err) {}
  });

  // Submit Relationship
  document.getElementById('btn-submit-rel')?.addEventListener('click', async () => {
    const sName = document.getElementById('rel-source-input').value.trim();
    const tName = document.getElementById('rel-target-input').value.trim();
    const relType = document.getElementById('rel-type-select').value;
    if (!sName || !tName) return;

    try {
      await fetch('/api/learning-graph/relationship', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_name: sName, target_name: tName, relation_type: relType, strength: 0.8 }),
      });
      document.getElementById('modal-add-rel').classList.add('hidden');
      document.getElementById('rel-source-input').value = '';
      document.getElementById('rel-target-input').value = '';
      showToast('Nodes connected in graph!', 'success');
      loadLearningGraph();
    } catch (err) {}
  });
}

function setupGlobalActions() {
  document.getElementById('btn-refresh-overview')?.addEventListener('click', () => {
    showToast('Refreshing overview...', 'info');
    loadOverview();
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function capitalize(s) {
  if (!s) return '';
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function formatMarkdown(text) {
  if (!text) return '';
  let out = escapeHtml(text);
  // Bold
  out = out.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Inline code
  out = out.replace(/`([^`]+)`/g, '<code class="font-mono">$1</code>');
  // Newlines to br
  out = out.replace(/\n/g, '<br>');
  return out;
}
