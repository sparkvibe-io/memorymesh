"""HTML export for MemoryMesh -- generates a self-contained memory wiki page.

Produces a single HTML file with inline CSS and vanilla JavaScript.
No external dependencies, CDNs, or build steps required.

Features:
    - Scope filter tabs (project / global / all)
    - Client-side text search
    - Memory cards with full text, metadata, importance bar, timestamps
    - Scope badges (color-coded)
    - Dark mode via ``prefers-color-scheme`` CSS media query
    - Responsive layout for desktop and mobile
    - All content HTML-escaped to prevent XSS

Usage::

    from memorymesh.html_export import generate_html
    html = generate_html(memories, title="My Memories")
"""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any

from .memory import Memory


def _escape(text: str) -> str:
    """HTML-escape text to prevent XSS.

    Args:
        text: Raw text.

    Returns:
        HTML-safe string.
    """
    return html.escape(text, quote=True)


def _format_timestamp(dt: datetime) -> str:
    """Format a datetime to ``YYYY-MM-DD HH:MM``.

    Args:
        dt: A datetime object.

    Returns:
        A short human-readable timestamp string.
    """
    return dt.strftime("%Y-%m-%d %H:%M")


def _importance_bar(importance: float) -> str:
    """Generate an inline HTML importance bar.

    Args:
        importance: Value between 0.0 and 1.0.

    Returns:
        HTML string for the importance bar.
    """
    pct = int(importance * 100)
    return (
        f'<div class="imp-bar">'
        f'<div class="imp-fill" style="width:{pct}%"></div>'
        f'<span class="imp-label">{importance:.2f}</span>'
        f"</div>"
    )


def _metadata_html(metadata: dict[str, Any]) -> str:
    """Render metadata as an HTML key-value list.

    Args:
        metadata: Dictionary of metadata.

    Returns:
        HTML string, or empty string if no metadata.
    """
    if not metadata:
        return ""
    items = []
    for k, v in metadata.items():
        items.append(
            f'<span class="meta-key">{_escape(str(k))}</span>='
            f'<span class="meta-val">{_escape(str(v))}</span>'
        )
    return '<div class="meta">' + " &middot; ".join(items) + "</div>"


def _memory_card(mem: Memory) -> str:
    """Render a single memory as an HTML card.

    Args:
        mem: The memory to render.

    Returns:
        HTML string for the memory card.
    """
    scope_class = "scope-project" if mem.scope == "project" else "scope-global"
    emb = mem.embedding
    has_emb = emb is not None and len(emb) > 0
    emb_badge = f' <span class="badge">emb:{len(emb)}d</span>' if has_emb and emb else ""

    return f"""<div class="card" data-scope="{_escape(mem.scope)}" data-text="{_escape(mem.text.lower())}">
  <div class="card-header">
    <span class="badge {scope_class}">{_escape(mem.scope)}</span>
    <code class="mem-id">{_escape(mem.id[:8])}</code>
    {emb_badge}
    <span class="hits">{mem.access_count}x</span>
  </div>
  <div class="card-body">
    <pre class="mem-text">{_escape(mem.text)}</pre>
  </div>
  <div class="card-footer">
    {_importance_bar(mem.importance)}
    {_metadata_html(mem.metadata)}
    <div class="timestamps">
      Created: {_format_timestamp(mem.created_at)} &middot;
      Updated: {_format_timestamp(mem.updated_at)}
    </div>
  </div>
</div>"""


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = """
:root {
  --bg: #ffffff;
  --bg2: #f5f5f5;
  --fg: #1a1a1a;
  --fg2: #555555;
  --border: #e0e0e0;
  --accent: #2563eb;
  --accent2: #7c3aed;
  --green: #16a34a;
  --bar-bg: #e5e7eb;
  --card-bg: #ffffff;
  --card-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f172a;
    --bg2: #1e293b;
    --fg: #e2e8f0;
    --fg2: #94a3b8;
    --border: #334155;
    --accent: #60a5fa;
    --accent2: #a78bfa;
    --green: #4ade80;
    --bar-bg: #334155;
    --card-bg: #1e293b;
    --card-shadow: 0 1px 3px rgba(0,0,0,0.3);
  }
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.6;
  padding: 2rem;
  max-width: 1000px;
  margin: 0 auto;
}

h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
.subtitle { color: var(--fg2); font-size: 0.85rem; margin-bottom: 1.5rem; }

.controls {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-bottom: 1.5rem;
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
}

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

.card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 1rem;
  box-shadow: var(--card-shadow);
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 1rem;
  background: var(--bg2);
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
}

.card-body { padding: 1rem; }

.mem-text {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: inherit;
  font-size: 0.9rem;
  line-height: 1.5;
}

.card-footer {
  padding: 0.6rem 1rem;
  border-top: 1px solid var(--border);
  font-size: 0.8rem;
  color: var(--fg2);
}

.badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}
.scope-project { background: #dbeafe; color: #1e40af; }
.scope-global { background: #ede9fe; color: #5b21b6; }
@media (prefers-color-scheme: dark) {
  .scope-project { background: #1e3a5f; color: #93c5fd; }
  .scope-global { background: #2e1065; color: #c4b5fd; }
}

.mem-id { font-size: 0.8rem; color: var(--fg2); }
.hits { margin-left: auto; color: var(--fg2); font-size: 0.8rem; }

.imp-bar {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 0.3rem;
}
.imp-bar .imp-fill {
  width: 60px;
  height: 6px;
  background: var(--accent);
  border-radius: 3px;
  display: inline-block;
}
.imp-bar {
  position: relative;
}
.imp-bar .imp-fill {
  max-width: 60px;
}
.imp-label { font-size: 0.8rem; color: var(--fg2); }

.meta {
  margin-top: 0.3rem;
  font-size: 0.8rem;
}
.meta-key { font-weight: 600; color: var(--accent); }
.meta-val { color: var(--fg2); }

.timestamps { margin-top: 0.3rem; }

.count { color: var(--fg2); font-size: 0.85rem; margin-bottom: 1rem; }

.no-results {
  text-align: center;
  color: var(--fg2);
  padding: 3rem 1rem;
  font-style: italic;
}

@media (max-width: 600px) {
  body { padding: 1rem; }
  .controls { flex-direction: column; }
  .search-box { min-width: 100%; }
}
"""

# ---------------------------------------------------------------------------
# JavaScript (client-side search + filter)
# ---------------------------------------------------------------------------

_JS = """
(function() {
  var searchBox = document.getElementById('search');
  var filterBtns = document.querySelectorAll('.filter-btn');
  var cards = document.querySelectorAll('.card');
  var countEl = document.getElementById('count');
  var currentScope = 'all';

  function update() {
    var q = searchBox.value.toLowerCase();
    var visible = 0;
    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      var matchScope = (currentScope === 'all' || card.dataset.scope === currentScope);
      var matchText = (!q || card.dataset.text.indexOf(q) !== -1);
      card.style.display = (matchScope && matchText) ? '' : 'none';
      if (matchScope && matchText) visible++;
    }
    countEl.textContent = 'Showing ' + visible + ' of ' + cards.length + ' memories';
  }

  searchBox.addEventListener('input', update);

  for (var i = 0; i < filterBtns.length; i++) {
    filterBtns[i].addEventListener('click', function() {
      for (var j = 0; j < filterBtns.length; j++) filterBtns[j].classList.remove('active');
      this.classList.add('active');
      currentScope = this.dataset.scope;
      update();
    });
  }
})();
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_html(
    memories: list[Memory],
    title: str = "MemoryMesh Export",
    project_path: str | None = None,
    global_path: str | None = None,
) -> str:
    """Generate a self-contained HTML page displaying the given memories.

    The output contains inline CSS and JavaScript with no external
    dependencies.  All memory content is HTML-escaped to prevent XSS.

    Args:
        memories: List of :class:`Memory` objects to display.
        title: Page title.
        project_path: Path to the project database (for display only).
        global_path: Path to the global database (for display only).

    Returns:
        A complete HTML document as a string.
    """
    # Count by scope
    proj_count = sum(1 for m in memories if m.scope == "project")
    glob_count = sum(1 for m in memories if m.scope == "global")
    total = len(memories)

    # Subtitle
    paths_info = []
    if project_path:
        paths_info.append(f"Project: {_escape(project_path)}")
    if global_path:
        paths_info.append(f"Global: {_escape(global_path)}")
    subtitle = " &middot; ".join(paths_info) if paths_info else ""

    # Build memory cards
    cards_html = "\n".join(_memory_card(m) for m in memories)
    if not memories:
        cards_html = '<div class="no-results">No memories stored yet.</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_escape(title)}</title>
<style>{_CSS}</style>
</head>
<body>
<h1>{_escape(title)}</h1>
<div class="subtitle">{subtitle}</div>

<div class="controls">
  <input type="text" id="search" class="search-box" placeholder="Search memories...">
  <button class="filter-btn active" data-scope="all">All ({total})</button>
  <button class="filter-btn" data-scope="project">Project ({proj_count})</button>
  <button class="filter-btn" data-scope="global">Global ({glob_count})</button>
</div>

<div id="count" class="count">Showing {total} of {total} memories</div>

{cards_html}

<script>{_JS}</script>
</body>
</html>"""
