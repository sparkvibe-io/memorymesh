"""Self-contained HTML SPA for the MemoryMesh web dashboard.

The entire front-end -- HTML structure, CSS styles, and JavaScript logic -- is
stored in the ``DASHBOARD_HTML`` constant so that ``dashboard.py`` can serve it
as a single HTTP response with no external dependencies.

CSS variables mirror the dark-mode patterns established in ``html_export.py``.
All user-generated content is rendered via ``textContent`` in JavaScript to
prevent XSS.
"""

from __future__ import annotations

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MemoryMesh Dashboard</title>
<style>
:root {
  --bg: #ffffff;
  --bg2: #f5f5f5;
  --bg3: #eaeaea;
  --fg: #1a1a1a;
  --fg2: #555555;
  --fg3: #888888;
  --border: #e0e0e0;
  --accent: #2563eb;
  --accent2: #7c3aed;
  --green: #16a34a;
  --red: #dc2626;
  --bar-bg: #e5e7eb;
  --card-bg: #ffffff;
  --card-shadow: 0 1px 3px rgba(0,0,0,0.1);
  --modal-bg: rgba(0,0,0,0.4);
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f172a;
    --bg2: #1e293b;
    --bg3: #334155;
    --fg: #e2e8f0;
    --fg2: #94a3b8;
    --fg3: #64748b;
    --border: #334155;
    --accent: #60a5fa;
    --accent2: #a78bfa;
    --green: #4ade80;
    --red: #f87171;
    --bar-bg: #334155;
    --card-bg: #1e293b;
    --card-shadow: 0 1px 3px rgba(0,0,0,0.3);
    --modal-bg: rgba(0,0,0,0.6);
  }
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.6;
  padding: 1.5rem;
  max-width: 1100px;
  margin: 0 auto;
}

/* --- Header / Stats --- */
.header { margin-bottom: 1.5rem; }
.header h1 { font-size: 1.4rem; margin-bottom: 0.25rem; }
.header .subtitle { color: var(--fg2); font-size: 0.85rem; }

.stats-bar {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1.5rem;
}
.stat-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  min-width: 120px;
  flex: 1;
  box-shadow: var(--card-shadow);
}
.stat-card .stat-value {
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--accent);
}
.stat-card .stat-label {
  font-size: 0.75rem;
  color: var(--fg2);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

/* --- Controls --- */
.controls {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
  align-items: center;
}

.search-box {
  flex: 1;
  min-width: 200px;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg2);
  color: var(--fg);
  font-size: 0.9rem;
  outline: none;
}
.search-box:focus { border-color: var(--accent); }

.filter-btn {
  padding: 0.4rem 0.8rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg2);
  color: var(--fg2);
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.15s;
}
.filter-btn:hover { border-color: var(--accent); color: var(--accent); }
.filter-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }

select.category-filter {
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg2);
  color: var(--fg);
  font-size: 0.85rem;
  cursor: pointer;
  outline: none;
}

/* --- Memory List --- */
.list-info {
  color: var(--fg2);
  font-size: 0.85rem;
  margin-bottom: 0.75rem;
}

.memory-list { list-style: none; }

.mem-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 0.75rem;
  box-shadow: var(--card-shadow);
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.15s;
}
.mem-card:hover { border-color: var(--accent); }

.mem-card-inner {
  display: flex;
  align-items: stretch;
}

.imp-stripe {
  width: 4px;
  flex-shrink: 0;
}

.mem-card-content {
  flex: 1;
  padding: 0.65rem 0.85rem;
  min-width: 0;
}

.mem-card-top {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 0.25rem;
}

.badge {
  display: inline-block;
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
}
.scope-project { background: #dbeafe; color: #1e40af; }
.scope-global { background: #ede9fe; color: #5b21b6; }
@media (prefers-color-scheme: dark) {
  .scope-project { background: #1e3a5f; color: #93c5fd; }
  .scope-global { background: #2e1065; color: #c4b5fd; }
}

.mem-id { font-size: 0.75rem; color: var(--fg3); font-family: monospace; }
.mem-meta-badge {
  font-size: 0.7rem;
  color: var(--fg3);
  margin-left: auto;
}

.mem-text-preview {
  font-size: 0.88rem;
  color: var(--fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mem-card-bottom {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.35rem;
  font-size: 0.75rem;
  color: var(--fg3);
}

.imp-bar-mini {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}
.imp-track {
  width: 50px;
  height: 4px;
  background: var(--bar-bg);
  border-radius: 2px;
  overflow: hidden;
}
.imp-fill {
  height: 100%;
  border-radius: 2px;
}

/* --- Pagination --- */
.pagination {
  display: flex;
  justify-content: center;
  gap: 0.5rem;
  margin-top: 1rem;
}
.pagination button {
  padding: 0.35rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg2);
  color: var(--fg);
  cursor: pointer;
  font-size: 0.85rem;
}
.pagination button:hover { border-color: var(--accent); }
.pagination button:disabled { opacity: 0.4; cursor: default; }
.pagination .page-info { line-height: 2; font-size: 0.85rem; color: var(--fg2); }

/* --- Modal --- */
.modal-overlay {
  display: none;
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: var(--modal-bg);
  z-index: 100;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}
.modal-overlay.open { display: flex; }

.modal {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  max-width: 650px;
  width: 100%;
  max-height: 85vh;
  overflow-y: auto;
  box-shadow: 0 10px 30px rgba(0,0,0,0.25);
}

.modal-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--border);
  background: var(--bg2);
  flex-wrap: wrap;
}
.modal-header .modal-title {
  font-weight: 600;
  font-family: monospace;
  font-size: 0.9rem;
}
.modal-close {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--fg2);
  font-size: 1.4rem;
  cursor: pointer;
  line-height: 1;
  padding: 0 0.2rem;
}
.modal-close:hover { color: var(--red); }

.modal-body { padding: 1rem; }

.modal-text {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-size: 0.9rem;
  line-height: 1.55;
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.75rem;
  margin-bottom: 1rem;
  max-height: 250px;
  overflow-y: auto;
}

.modal-fields {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.4rem 1rem;
  font-size: 0.85rem;
  margin-bottom: 1rem;
}
.modal-fields dt { color: var(--fg2); font-weight: 600; }
.modal-fields dd { color: var(--fg); }

.imp-slider-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 1rem;
}
.imp-slider-row label { font-size: 0.85rem; color: var(--fg2); font-weight: 600; }
.imp-slider-row input[type=range] { flex: 1; accent-color: var(--accent); }
.imp-slider-row .imp-val { font-size: 0.85rem; font-weight: 600; min-width: 2.5em; }

.modal-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  padding: 0 1rem 1rem;
}
.btn {
  padding: 0.4rem 1rem;
  border-radius: 6px;
  font-size: 0.85rem;
  cursor: pointer;
  border: 1px solid var(--border);
  background: var(--bg2);
  color: var(--fg);
  transition: all 0.15s;
}
.btn:hover { border-color: var(--accent); }
.btn-danger { background: var(--red); color: #fff; border-color: var(--red); }
.btn-danger:hover { opacity: 0.85; }

.no-results {
  text-align: center;
  color: var(--fg2);
  padding: 3rem 1rem;
  font-style: italic;
}

.toast {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  background: var(--accent);
  color: #fff;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-size: 0.85rem;
  z-index: 200;
  opacity: 0;
  transition: opacity 0.3s;
  pointer-events: none;
}
.toast.show { opacity: 1; }

@media (max-width: 600px) {
  body { padding: 0.75rem; }
  .controls { flex-direction: column; }
  .search-box { min-width: 100%; }
  .stats-bar { flex-direction: column; }
  .stat-card { min-width: 100%; }
  .modal { max-height: 95vh; }
}
</style>
</head>
<body>

<div class="header">
  <h1>MemoryMesh Dashboard</h1>
  <div class="subtitle">View, search, and manage your AI memories</div>
</div>

<div class="stats-bar" id="stats-bar">
  <div class="stat-card">
    <div class="stat-value" id="stat-total">-</div>
    <div class="stat-label">Total Memories</div>
  </div>
  <div class="stat-card">
    <div class="stat-value" id="stat-project">-</div>
    <div class="stat-label">Project</div>
  </div>
  <div class="stat-card">
    <div class="stat-value" id="stat-global">-</div>
    <div class="stat-label">Global</div>
  </div>
  <div class="stat-card">
    <div class="stat-value" id="stat-time">-</div>
    <div class="stat-label">Time Range</div>
  </div>
</div>

<div class="controls">
  <input type="text" id="search-input" class="search-box" placeholder="Search memories...">
  <button class="filter-btn active" data-scope="all">All</button>
  <button class="filter-btn" data-scope="project">Project</button>
  <button class="filter-btn" data-scope="global">Global</button>
  <select class="category-filter" id="category-filter">
    <option value="">All categories</option>
    <option value="decision">Decision</option>
    <option value="pattern">Pattern</option>
    <option value="context">Context</option>
    <option value="preference">Preference</option>
    <option value="guardrail">Guardrail</option>
    <option value="mistake">Mistake</option>
    <option value="personality">Personality</option>
    <option value="question">Question</option>
    <option value="session_summary">Session Summary</option>
  </select>
</div>

<div class="list-info" id="list-info">Loading...</div>

<ul class="memory-list" id="memory-list"></ul>

<div class="pagination" id="pagination">
  <button id="btn-prev" disabled>Previous</button>
  <span class="page-info" id="page-info"></span>
  <button id="btn-next" disabled>Next</button>
</div>

<div class="modal-overlay" id="modal-overlay">
  <div class="modal" id="modal">
    <div class="modal-header">
      <span class="modal-title" id="modal-id"></span>
      <span class="badge" id="modal-scope-badge"></span>
      <button class="modal-close" id="modal-close">&times;</button>
    </div>
    <div class="modal-body">
      <div class="modal-text" id="modal-text"></div>
      <dl class="modal-fields" id="modal-fields"></dl>
      <div class="imp-slider-row">
        <label>Importance</label>
        <input type="range" id="modal-imp-slider" min="0" max="100" step="1">
        <span class="imp-val" id="modal-imp-val">0.50</span>
      </div>
    </div>
    <div class="modal-actions">
      <button class="btn btn-danger" id="modal-delete">Delete</button>
      <button class="btn" id="modal-close-btn">Close</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
(function() {
  "use strict";

  /* ---- State ---- */
  var currentScope = "all";
  var currentSearch = "";
  var currentCategory = "";
  var currentOffset = 0;
  var pageSize = 50;
  var totalMemories = 0;
  var currentModalId = null;

  /* ---- DOM refs ---- */
  var $statTotal = document.getElementById("stat-total");
  var $statProject = document.getElementById("stat-project");
  var $statGlobal = document.getElementById("stat-global");
  var $statTime = document.getElementById("stat-time");
  var $searchInput = document.getElementById("search-input");
  var $categoryFilter = document.getElementById("category-filter");
  var $listInfo = document.getElementById("list-info");
  var $memoryList = document.getElementById("memory-list");
  var $pagination = document.getElementById("pagination");
  var $btnPrev = document.getElementById("btn-prev");
  var $btnNext = document.getElementById("btn-next");
  var $pageInfo = document.getElementById("page-info");
  var $modalOverlay = document.getElementById("modal-overlay");
  var $modalId = document.getElementById("modal-id");
  var $modalScopeBadge = document.getElementById("modal-scope-badge");
  var $modalText = document.getElementById("modal-text");
  var $modalFields = document.getElementById("modal-fields");
  var $modalImpSlider = document.getElementById("modal-imp-slider");
  var $modalImpVal = document.getElementById("modal-imp-val");
  var $modalDelete = document.getElementById("modal-delete");
  var $toast = document.getElementById("toast");

  /* ---- API helpers ---- */
  function fetchJSON(url) {
    return fetch(url).then(function(r) {
      if (!r.ok) return r.json().then(function(e) { throw e; });
      return r.json();
    });
  }

  function apiDelete(url) {
    return fetch(url, { method: "DELETE" }).then(function(r) { return r.json(); });
  }

  function apiPatch(url, data) {
    return fetch(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    }).then(function(r) { return r.json(); });
  }

  /* ---- Toast ---- */
  var toastTimer = null;
  function showToast(msg) {
    $toast.textContent = msg;
    $toast.classList.add("show");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function() { $toast.classList.remove("show"); }, 2500);
  }

  /* ---- Stats ---- */
  function loadStats() {
    fetchJSON("/api/stats").then(function(d) {
      $statTotal.textContent = d.total;
      $statProject.textContent = d.project_count;
      $statGlobal.textContent = d.global_count;
      if (d.oldest && d.newest) {
        $statTime.textContent = shortDate(d.oldest) + " - " + shortDate(d.newest);
        $statTime.style.fontSize = "0.75rem";
      } else {
        $statTime.textContent = "-";
        $statTime.style.fontSize = "";
      }
    });
  }

  function shortDate(iso) {
    if (!iso) return "-";
    return iso.substring(0, 10);
  }

  /* ---- Importance color ---- */
  function impColor(v) {
    if (v >= 0.8) return "var(--red)";
    if (v >= 0.5) return "var(--accent)";
    if (v >= 0.3) return "var(--green)";
    return "var(--fg3)";
  }

  /* ---- Memory list ---- */
  function loadMemories() {
    var scopeParam = currentScope === "all" ? "" : "&scope=" + currentScope;
    var searchParam = currentSearch ? "&search=" + encodeURIComponent(currentSearch) : "";
    var url = "/api/memories?limit=" + pageSize + "&offset=" + currentOffset + scopeParam + searchParam;

    fetchJSON(url).then(function(d) {
      totalMemories = d.total;
      renderMemoryList(d.memories);
      updatePagination();
      var showing = d.memories.length;
      $listInfo.textContent = "Showing " + (currentOffset + 1) + "-" + (currentOffset + showing) + " of " + totalMemories + " memories";
      if (showing === 0) {
        $listInfo.textContent = "No memories found.";
      }
    });
  }

  function renderMemoryList(memories) {
    $memoryList.innerHTML = "";
    if (memories.length === 0) {
      var li = document.createElement("li");
      li.className = "no-results";
      li.textContent = currentSearch ? "No memories match your search." : "No memories stored yet.";
      $memoryList.appendChild(li);
      return;
    }
    for (var i = 0; i < memories.length; i++) {
      var mem = memories[i];
      if (currentCategory && (!mem.metadata || mem.metadata.category !== currentCategory)) {
        continue;
      }
      $memoryList.appendChild(renderMemoryCard(mem));
    }
    if ($memoryList.children.length === 0) {
      var empty = document.createElement("li");
      empty.className = "no-results";
      empty.textContent = "No memories match the selected category.";
      $memoryList.appendChild(empty);
    }
  }

  function renderMemoryCard(mem) {
    var li = document.createElement("li");
    li.className = "mem-card";
    li.setAttribute("data-id", mem.id);

    var inner = document.createElement("div");
    inner.className = "mem-card-inner";

    /* importance stripe */
    var stripe = document.createElement("div");
    stripe.className = "imp-stripe";
    stripe.style.background = impColor(mem.importance);
    inner.appendChild(stripe);

    var content = document.createElement("div");
    content.className = "mem-card-content";

    /* top row */
    var top = document.createElement("div");
    top.className = "mem-card-top";

    var scopeBadge = document.createElement("span");
    scopeBadge.className = "badge " + (mem.scope === "project" ? "scope-project" : "scope-global");
    scopeBadge.textContent = mem.scope;
    top.appendChild(scopeBadge);

    var idSpan = document.createElement("span");
    idSpan.className = "mem-id";
    idSpan.textContent = mem.id.substring(0, 8);
    top.appendChild(idSpan);

    if (mem.metadata && mem.metadata.category) {
      var catBadge = document.createElement("span");
      catBadge.className = "mem-meta-badge";
      catBadge.textContent = mem.metadata.category;
      top.appendChild(catBadge);
    }

    var hits = document.createElement("span");
    hits.className = "mem-meta-badge";
    hits.textContent = mem.access_count + "x";
    top.appendChild(hits);

    content.appendChild(top);

    /* text preview */
    var textPrev = document.createElement("div");
    textPrev.className = "mem-text-preview";
    textPrev.textContent = mem.text;
    content.appendChild(textPrev);

    /* bottom row */
    var bottom = document.createElement("div");
    bottom.className = "mem-card-bottom";

    var impMini = document.createElement("span");
    impMini.className = "imp-bar-mini";
    var track = document.createElement("span");
    track.className = "imp-track";
    var fill = document.createElement("span");
    fill.className = "imp-fill";
    fill.style.width = Math.round(mem.importance * 100) + "%";
    fill.style.background = impColor(mem.importance);
    track.appendChild(fill);
    impMini.appendChild(track);
    var impLbl = document.createElement("span");
    impLbl.textContent = mem.importance.toFixed(2);
    impMini.appendChild(impLbl);
    bottom.appendChild(impMini);

    var created = document.createElement("span");
    created.textContent = "Created: " + shortDate(mem.created_at);
    bottom.appendChild(created);

    var updated = document.createElement("span");
    updated.textContent = "Updated: " + shortDate(mem.updated_at);
    bottom.appendChild(updated);

    content.appendChild(bottom);
    inner.appendChild(content);
    li.appendChild(inner);

    li.addEventListener("click", function() { showModal(mem.id); });
    return li;
  }

  /* ---- Pagination ---- */
  function updatePagination() {
    var page = Math.floor(currentOffset / pageSize) + 1;
    var totalPages = Math.max(1, Math.ceil(totalMemories / pageSize));
    $pageInfo.textContent = "Page " + page + " of " + totalPages;
    $btnPrev.disabled = currentOffset === 0;
    $btnNext.disabled = currentOffset + pageSize >= totalMemories;
  }

  $btnPrev.addEventListener("click", function() {
    currentOffset = Math.max(0, currentOffset - pageSize);
    loadMemories();
  });

  $btnNext.addEventListener("click", function() {
    currentOffset += pageSize;
    loadMemories();
  });

  /* ---- Modal ---- */
  function showModal(memoryId) {
    fetchJSON("/api/memories/" + memoryId).then(function(mem) {
      currentModalId = mem.id;
      $modalId.textContent = mem.id;

      $modalScopeBadge.textContent = mem.scope;
      $modalScopeBadge.className = "badge " + (mem.scope === "project" ? "scope-project" : "scope-global");

      $modalText.textContent = mem.text;

      /* Build fields */
      $modalFields.innerHTML = "";
      var fields = [
        ["Scope", mem.scope],
        ["Importance", mem.importance.toFixed(4)],
        ["Decay Rate", mem.decay_rate.toFixed(4)],
        ["Access Count", mem.access_count],
        ["Created", mem.created_at.replace("T", " ").substring(0, 19)],
        ["Updated", mem.updated_at.replace("T", " ").substring(0, 19)],
        ["Has Embedding", mem.has_embedding ? "Yes" : "No"]
      ];
      if (mem.session_id) {
        fields.push(["Session", mem.session_id.substring(0, 12)]);
      }
      if (mem.metadata && Object.keys(mem.metadata).length > 0) {
        fields.push(["Metadata", JSON.stringify(mem.metadata)]);
      }
      for (var i = 0; i < fields.length; i++) {
        var dt = document.createElement("dt");
        dt.textContent = fields[i][0];
        var dd = document.createElement("dd");
        dd.textContent = String(fields[i][1]);
        $modalFields.appendChild(dt);
        $modalFields.appendChild(dd);
      }

      /* Importance slider */
      $modalImpSlider.value = Math.round(mem.importance * 100);
      $modalImpVal.textContent = mem.importance.toFixed(2);

      $modalOverlay.classList.add("open");
    });
  }

  function closeModal() {
    $modalOverlay.classList.remove("open");
    currentModalId = null;
  }

  document.getElementById("modal-close").addEventListener("click", closeModal);
  document.getElementById("modal-close-btn").addEventListener("click", closeModal);
  $modalOverlay.addEventListener("click", function(e) {
    if (e.target === $modalOverlay) closeModal();
  });
  document.addEventListener("keydown", function(e) {
    if (e.key === "Escape" && $modalOverlay.classList.contains("open")) closeModal();
  });

  /* Importance slider */
  $modalImpSlider.addEventListener("input", function() {
    var v = parseInt(this.value, 10) / 100;
    $modalImpVal.textContent = v.toFixed(2);
  });
  $modalImpSlider.addEventListener("change", function() {
    if (!currentModalId) return;
    var v = parseInt(this.value, 10) / 100;
    apiPatch("/api/memories/" + currentModalId, { importance: v }).then(function(d) {
      if (d.updated) {
        showToast("Importance updated to " + v.toFixed(2));
        loadMemories();
        loadStats();
      }
    });
  });

  /* Delete */
  $modalDelete.addEventListener("click", function() {
    if (!currentModalId) return;
    if (!confirm("Delete this memory permanently?")) return;
    apiDelete("/api/memories/" + currentModalId).then(function(d) {
      if (d.deleted) {
        showToast("Memory deleted");
        closeModal();
        loadMemories();
        loadStats();
      } else {
        showToast("Memory not found");
      }
    });
  });

  /* ---- Scope filter ---- */
  var filterBtns = document.querySelectorAll(".filter-btn");
  for (var i = 0; i < filterBtns.length; i++) {
    filterBtns[i].addEventListener("click", function() {
      for (var j = 0; j < filterBtns.length; j++) filterBtns[j].classList.remove("active");
      this.classList.add("active");
      currentScope = this.getAttribute("data-scope");
      currentOffset = 0;
      loadMemories();
    });
  }

  /* ---- Search ---- */
  var searchTimer = null;
  $searchInput.addEventListener("input", function() {
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(function() {
      currentSearch = $searchInput.value.trim();
      currentOffset = 0;
      loadMemories();
    }, 300);
  });

  /* ---- Category filter ---- */
  $categoryFilter.addEventListener("change", function() {
    currentCategory = this.value;
    currentOffset = 0;
    loadMemories();
  });

  /* ---- Initial load ---- */
  loadStats();
  loadMemories();

  /* ---- Auto-refresh stats every 30s ---- */
  setInterval(loadStats, 30000);

})();
</script>
</body>
</html>"""
