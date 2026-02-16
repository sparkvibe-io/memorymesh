#!/usr/bin/env python3
"""MemoryMesh Interactive Chat Demo -- memory persistence and token savings in action.

An interactive terminal chat that uses MemoryMesh + the Anthropic API (Claude)
to demonstrate:

  1. Memory persisting across conversation turns (and across sessions!)
  2. Automatic context injection from recalled memories into the LLM prompt
  3. Token savings metrics -- how many tokens memory saves vs. full history

Usage:
    python examples/demo_chat.py

Requirements:
    - An ANTHROPIC_API_KEY environment variable (or the ``anthropic`` package
      configured with a key).
    - No ML dependencies needed -- uses keyword matching by default.

Memories are stored at ``~/.memorymesh/demo.db`` and persist between runs.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure MemoryMesh is importable even without pip install.
# When running from the project root (``python examples/demo_chat.py``) or
# from the examples/ directory, add the ``src/`` folder to sys.path so that
# ``from memorymesh import ...`` resolves correctly.
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent
_SRC_DIR = _PROJECT_ROOT / "src"
if _SRC_DIR.is_dir() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from memorymesh import MemoryMesh  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL = "claude-haiku-4-5-20251001"
DB_PATH = Path.home() / ".memorymesh" / "demo.db"
SYSTEM_PROMPT = (
    "You are a helpful assistant. You have persistent memory about the user. "
    "When relevant memories are provided in the context block below, use them "
    "naturally in your response -- reference what you remember about the user "
    "without being awkward about it."
)
MAX_MEMORY_CONTEXT_TOKENS = 800  # rough cap on how many tokens of memory to inject
MAX_SUMMARY_LEN = 200  # max characters for auto-remembered summaries
RECALL_K = 5  # how many memories to recall per turn

# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token on average.

    This is a widely used heuristic. It is not exact, but it is good enough
    for a demo that shows relative savings.
    """
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Anthropic API helpers
# ---------------------------------------------------------------------------

# Try to import the official SDK; fall back to raw urllib if unavailable.
_anthropic_client = None

try:
    import anthropic as _anthropic_module

    _api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if _api_key:
        _anthropic_client = _anthropic_module.Anthropic(api_key=_api_key)
    else:
        # The SDK may pick up the key from its own config.
        _anthropic_client = _anthropic_module.Anthropic()
except Exception:
    _anthropic_client = None


def _call_claude_sdk(system: str, messages: list[dict]) -> str:
    """Call Claude using the official Anthropic Python SDK."""
    assert _anthropic_client is not None
    resp = _anthropic_client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system,
        messages=messages,
    )
    # Extract the text from the response content blocks.
    parts = []
    for block in resp.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "\n".join(parts) if parts else "(no response)"


def _call_claude_urllib(system: str, messages: list[dict]) -> str:
    """Call Claude using raw urllib (no SDK needed)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return (
            "[ERROR] No ANTHROPIC_API_KEY found.  Set it in your environment:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-..."
        )

    url = "https://api.anthropic.com/v1/messages"
    payload = json.dumps({
        "model": MODEL,
        "max_tokens": 1024,
        "system": system,
        "messages": messages,
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() if exc.fp else ""
        return f"[API Error {exc.code}] {body[:300]}"
    except urllib.error.URLError as exc:
        return f"[Connection Error] {exc}"

    # Parse the response.
    content_blocks = data.get("content", [])
    parts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
    return "\n".join(parts) if parts else "(no response)"


def call_claude(system: str, messages: list[dict]) -> str:
    """Call Claude, preferring the SDK but falling back to urllib."""
    if _anthropic_client is not None:
        return _call_claude_sdk(system, messages)
    return _call_claude_urllib(system, messages)


# ---------------------------------------------------------------------------
# Memory context formatting
# ---------------------------------------------------------------------------


def format_memory_context(memories: list) -> str:
    """Format recalled memories into a context block for the system prompt.

    Args:
        memories: List of Memory objects from MemoryMesh.recall().

    Returns:
        A formatted string ready to append to the system prompt.
    """
    if not memories:
        return ""

    lines = ["", "=== Persistent Memory (recalled from previous interactions) ==="]
    for i, mem in enumerate(memories, 1):
        # Truncate very long memories for the context window.
        text = mem.text if len(mem.text) <= 300 else mem.text[:297] + "..."
        lines.append(f"  {i}. {text}")
    lines.append("=== End of Memory ===")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Token tracking
# ---------------------------------------------------------------------------


class TokenTracker:
    """Tracks token usage with and without memory to show savings.

    The tracker compares two approaches:
    - WITH memory: system prompt + recalled memories + current user message
    - WITHOUT memory: full conversation history (all user + assistant turns)

    The difference demonstrates why persistent memory is more efficient
    than stuffing the entire history into every LLM call.
    """

    def __init__(self) -> None:
        self.total_with_memory: int = 0
        self.total_without_memory: int = 0
        self.turn_count: int = 0
        # Full conversation history (what you would send without memory).
        self.full_history: list[dict] = []

    def record_turn(
        self,
        system_with_memory: str,
        user_message: str,
        assistant_response: str,
    ) -> dict:
        """Record a conversation turn and return token stats for this turn.

        Args:
            system_with_memory: The system prompt including injected memories.
            user_message: The user's message for this turn.
            assistant_response: Claude's response.

        Returns:
            A dict with keys: with_memory, without_memory, saved, saved_pct
        """
        self.turn_count += 1

        # -- Tokens WITH memory (what we actually sent) --------------------
        # System prompt (with memories) + just the current user message.
        tokens_with = (
            estimate_tokens(system_with_memory) + estimate_tokens(user_message)
        )
        self.total_with_memory += tokens_with

        # -- Tokens WITHOUT memory (what you'd need without MemoryMesh) ----
        # Accumulate the full history.
        self.full_history.append({"role": "user", "content": user_message})
        self.full_history.append({"role": "assistant", "content": assistant_response})

        # Without memory you'd send: base system prompt + ALL history.
        base_system_tokens = estimate_tokens(SYSTEM_PROMPT)
        history_tokens = sum(
            estimate_tokens(msg["content"]) for msg in self.full_history
        )
        tokens_without = base_system_tokens + history_tokens
        self.total_without_memory += tokens_without

        # -- Savings -------------------------------------------------------
        saved = max(0, tokens_without - tokens_with)
        saved_pct = (saved / tokens_without * 100) if tokens_without > 0 else 0.0

        return {
            "with_memory": tokens_with,
            "without_memory": tokens_without,
            "saved": saved,
            "saved_pct": saved_pct,
        }

    def summary(self) -> str:
        """Return a formatted summary of cumulative token savings."""
        if self.turn_count == 0:
            return "No turns recorded yet."
        total_saved = max(0, self.total_without_memory - self.total_with_memory)
        pct = (
            (total_saved / self.total_without_memory * 100)
            if self.total_without_memory > 0
            else 0.0
        )
        return (
            f"Turns: {self.turn_count}  |  "
            f"With memory: ~{self.total_with_memory:,} tokens  |  "
            f"Without memory: ~{self.total_without_memory:,} tokens  |  "
            f"Saved: ~{total_saved:,} tokens ({pct:.0f}%)"
        )


# ---------------------------------------------------------------------------
# ANSI colour helpers (for a polished terminal experience)
# ---------------------------------------------------------------------------

# Detect whether the terminal supports colour.
_COLOUR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _dim(text: str) -> str:
    return f"\033[2m{text}\033[0m" if _COLOUR else text


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m" if _COLOUR else text


def _green(text: str) -> str:
    return f"\033[32m{text}\033[0m" if _COLOUR else text


def _cyan(text: str) -> str:
    return f"\033[36m{text}\033[0m" if _COLOUR else text


def _yellow(text: str) -> str:
    return f"\033[33m{text}\033[0m" if _COLOUR else text


# ---------------------------------------------------------------------------
# Main interactive loop
# ---------------------------------------------------------------------------


def print_welcome(memory: MemoryMesh) -> None:
    """Print the welcome banner and instructions."""
    count = memory.count()

    print()
    print(f"  {_bold('MemoryMesh Interactive Demo')}")
    print(f"  {'=' * 42}")
    print()
    print("  This demo shows how MemoryMesh gives LLMs persistent memory.")
    print(f"  Memories are stored in SQLite at: {_dim(str(DB_PATH))}")
    if count > 0:
        print(f"  Loaded {_green(str(count))} memories from previous sessions.")
    print()
    print(f"  {_bold('How it works:')}")
    print("    1. Before each LLM call, relevant memories are recalled and")
    print("       injected into the system prompt as context.")
    print("    2. After each response, key facts from your message are")
    print("       automatically saved to memory.")
    print("    3. Token savings are tracked -- memory replaces full chat")
    print("       history, dramatically reducing token usage over time.")
    print()
    print(f"  {_bold('Commands:')}")
    print(f"    {_cyan('/remember <text>')}  - Manually store a memory")
    print(f"    {_cyan('/recall <query>')}   - Search memories")
    print(f"    {_cyan('/memories')}         - List all stored memories")
    print(f"    {_cyan('/stats')}            - Show token savings statistics")
    print(f"    {_cyan('/clear')}            - Clear all memories")
    print(f"    {_cyan('/quit')}             - Exit")
    print()


def handle_command(cmd: str, memory: MemoryMesh, tracker: TokenTracker) -> bool:
    """Handle a slash command.

    Args:
        cmd: The full command string (including the leading /).
        memory: The MemoryMesh instance.
        tracker: The TokenTracker instance.

    Returns:
        True if the command was handled (caller should skip LLM call).
    """
    parts = cmd.strip().split(None, 1)
    command = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if command == "/quit":
        count = memory.count()
        print(
            f"\n{_dim(f'[{count} memories saved to {DB_PATH}. They will be here next time.]')}"
        )
        print(f"\n{tracker.summary()}")
        print(f"\n{_bold('Goodbye!')}\n")
        sys.exit(0)

    elif command == "/remember":
        if not arg:
            print(f"  {_yellow('Usage: /remember <text to remember>')}")
            return True
        mid = memory.remember(arg)
        msg = '[Stored memory: {}... -> "{}"]'.format(mid[:8], arg)  # noqa: UP032
        print(f"  {_dim(msg)}")
        return True

    elif command == "/recall":
        if not arg:
            print(f"  {_yellow('Usage: /recall <search query>')}")
            return True
        results = memory.recall(arg, k=5)
        if not results:
            print(f"  {_dim('[No matching memories found.]')}")
        else:
            print(f"  {_dim(f'[Found {len(results)} matching memories:]')}")
            for i, m in enumerate(results, 1):
                preview = m.text if len(m.text) <= 80 else m.text[:77] + "..."
                print(f"    {i}. {preview}")
        return True

    elif command == "/memories":
        total = memory.count()
        if total == 0:
            print(f"  {_dim('[No memories stored yet.]')}")
            return True
        print(f"  {_dim(f'[{total} memories stored:]')}")
        # Paginate through all memories.
        offset = 0
        while offset < total:
            batch = memory.list(limit=20, offset=offset)
            if not batch:
                break
            for m in batch:
                preview = m.text if len(m.text) <= 70 else m.text[:67] + "..."
                age = ""
                if hasattr(m, "access_count"):
                    age = f" (accessed {m.access_count}x)"
                print(f"    - {preview}{_dim(age)}")
            offset += len(batch)
        return True

    elif command == "/stats":
        print(f"\n  {_bold('Token Savings Statistics')}")
        print(f"  {'-' * 40}")
        print(f"  {tracker.summary()}")
        print(f"  Memories in database: {memory.count()}")
        print()
        return True

    elif command == "/clear":
        count = memory.forget_all()
        print(f"  {_dim(f'[Cleared {count} memories.]')}")
        return True

    else:
        print(f"  {_yellow(f'Unknown command: {command}')}")
        print(f"  {_dim('Type /quit to exit, or just type a message to chat.')}")
        return True


def main() -> None:
    """Run the interactive chat demo."""
    # ------------------------------------------------------------------
    # Initialise MemoryMesh
    # ------------------------------------------------------------------
    # Use embedding="none" so the demo works without any ML dependencies.
    # Keyword matching is plenty good for demonstrating the concept.
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    memory = MemoryMesh(path=str(DB_PATH), embedding="none")
    tracker = TokenTracker()

    print_welcome(memory)

    # Check for API key early so we can warn the user.
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key and _anthropic_client is None:
        print(
            _yellow(
                "  WARNING: No ANTHROPIC_API_KEY found.\n"
                "  Set it with: export ANTHROPIC_API_KEY=sk-ant-...\n"
                "  The demo will still show memory operations, but LLM\n"
                "  responses will show an error message.\n"
            )
        )

    # ------------------------------------------------------------------
    # Chat loop
    # ------------------------------------------------------------------
    while True:
        try:
            user_input = input(f"{_bold('You:')} ").strip()
        except (KeyboardInterrupt, EOFError):
            # Graceful exit on Ctrl+C or Ctrl+D.
            print()
            count = memory.count()
            print(
                _dim(f"\n[{count} memories saved to {DB_PATH}. They will be here next time.]")
            )
            print(f"\n{tracker.summary()}")
            print(f"\n{_bold('Goodbye!')}\n")
            break

        if not user_input:
            continue

        # Handle slash commands.
        if user_input.startswith("/"):
            handle_command(user_input, memory, tracker)
            continue

        # ==============================================================
        # STEP 1: Recall relevant memories
        # ==============================================================
        recalled = memory.recall(user_input, k=RECALL_K)

        # Filter to stay within our token budget for memory context.
        injected_memories = []
        injected_tokens = 0
        for mem in recalled:
            mem_tokens = estimate_tokens(mem.text)
            if injected_tokens + mem_tokens > MAX_MEMORY_CONTEXT_TOKENS:
                break
            injected_memories.append(mem)
            injected_tokens += mem_tokens

        # Show what was recalled.
        if injected_memories:
            print(
                _dim(
                    f"  [Recalled {len(injected_memories)} "
                    f"{'memory' if len(injected_memories) == 1 else 'memories'}, "
                    f"~{injected_tokens} tokens injected]"
                )
            )

        # ==============================================================
        # STEP 2: Build the system prompt with memory context
        # ==============================================================
        memory_context = format_memory_context(injected_memories)
        system_with_memory = SYSTEM_PROMPT + memory_context

        # We send only the current user message (not the full history).
        # This is the key insight: memory replaces history.
        messages = [{"role": "user", "content": user_input}]

        # ==============================================================
        # STEP 3: Call Claude
        # ==============================================================
        print()
        response = call_claude(system_with_memory, messages)
        print(f"{_bold('Claude:')} {response}")
        print()

        # ==============================================================
        # STEP 4: Auto-remember the user's message
        # ==============================================================
        # Store a summary of what the user said. In a production system
        # you might use the LLM itself to extract key facts, but for
        # this demo we simply store the user's message (truncated).
        summary = user_input[:MAX_SUMMARY_LEN]
        if len(user_input) > MAX_SUMMARY_LEN:
            summary = summary.rsplit(" ", 1)[0] + "..."
        memory.remember(
            summary,
            metadata={"source": "auto", "turn": tracker.turn_count + 1},
            importance=0.5,
        )
        print(
            _dim(f'  [Auto-remembered: "{summary[:60]}{"..." if len(summary) > 60 else ""}"]')
        )

        # ==============================================================
        # STEP 5: Track token savings
        # ==============================================================
        turn_stats = tracker.record_turn(system_with_memory, user_input, response)

        # Only show savings after the first turn (turn 1 usually shows no savings).
        if tracker.turn_count >= 2:
            print(
                _dim(
                    f"  [Session tokens: ~{tracker.total_with_memory:,} | "
                    f"Without memory: ~{tracker.total_without_memory:,} | "
                    f"Saved: ~{turn_stats['saved_pct']:.0f}%]"
                )
            )
        else:
            print(
                _dim(
                    f"  [Turn tokens: ~{turn_stats['with_memory']:,} | "
                    f"Savings grow as conversation gets longer]"
                )
            )
        print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
