"""Second Brain & Knowledge Vault: Obsidian and Markdown Knowledge Base Sync.

Allows Hermclaw to:
- sync_vault: Synchronize agent memories, learned concepts, and task insights into an Obsidian vault.
- create_note: Create interconnected notes with YAML frontmatter and [[wikilinks]].
- query_vault: Search across local Markdown notes and documents.
- list_notes: Overview all notes, tags, and connections in the vault.
"""

from __future__ import annotations

import datetime
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

import structlog

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

logger = structlog.get_logger(__name__)


def _get_default_vault_path() -> Path:
    """Determine default vault path."""
    custom = os.environ.get("HERMCLAW_VAULT_PATH")
    if custom:
        return Path(custom)
    return Path.home() / ".hermclaw" / "vault"


class KnowledgeVaultTool(ToolABC):
    """Sync and manage an Obsidian-compatible Second Brain knowledge vault."""

    def __init__(self, default_vault_dir: Optional[Path] = None) -> None:
        self._vault_dir = default_vault_dir or _get_default_vault_path()

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="knowledge_vault",
            description=(
                "Second Brain & Obsidian vault manager. Synchronizes AI discoveries, notes, and task summaries "
                "into an interconnected Markdown knowledge base with [[wikilinks]] and frontmatter tags. "
                "Actions: sync_vault, create_note, query_vault, list_notes."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["sync_vault", "create_note", "query_vault", "list_notes"],
                        "description": "Vault action to execute.",
                    },
                    "title": {"type": "string", "description": "Title of the note (for create_note)."},
                    "content": {"type": "string", "description": "Content of the note (for create_note)."},
                    "tags": {"type": "string", "description": "Comma-separated tags (e.g. 'ai, research, python')."},
                    "links": {"type": "string", "description": "Comma-separated topics to link as [[Topic]] (for create_note)."},
                    "query": {"type": "string", "description": "Search query for query_vault."},
                    "vault_path": {"type": "string", "description": "Optional custom vault directory path."},
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args["action"]
        vault_dir = Path(args["vault_path"]) if args.get("vault_path") else self._vault_dir
        vault_dir.mkdir(parents=True, exist_ok=True)

        try:
            if action == "sync_vault":
                return self._sync_vault(vault_dir)
            elif action == "create_note":
                return self._create_note(
                    vault_dir,
                    args.get("title", ""),
                    args.get("content", ""),
                    args.get("tags", ""),
                    args.get("links", ""),
                )
            elif action == "query_vault":
                return self._query_vault(vault_dir, args.get("query", ""))
            elif action == "list_notes":
                return self._list_notes(vault_dir)
            else:
                return ToolResult(ok=False, output="", error=f"Unknown vault action: {action}")
        except Exception as exc:
            logger.error("vault.error", action=action, exc_info=exc)
            return ToolResult(ok=False, output="", error=f"Knowledge vault error: {exc}")

    def _sync_vault(self, vault_dir: Path) -> ToolResult:
        """Export learned concepts, goals, and task memories into the Obsidian vault."""
        notes_created = 0
        now = datetime.datetime.now().strftime("%Y-%m-%d")

        # 1. Sync Learning Graph concepts
        try:
            lg_file = Path.home() / ".hermclaw" / "learning_graph.json"
            if lg_file.exists():
                data = json.loads(lg_file.read_text(encoding="utf-8"))
                concepts_dir = vault_dir / "Concepts"
                concepts_dir.mkdir(exist_ok=True)

                for node in data.get("nodes", []):
                    title = node.get("title") or node.get("name") or node.get("id")
                    if not title:
                        continue
                    clean_title = re.sub(r'[\\/*?:"<>|]', "", title)
                    note_path = concepts_dir / f"{clean_title}.md"

                    related = [f"[[{r}]]" for r in node.get("related", [])]
                    note_body = f"""---
title: "{title}"
date: {now}
tags: [concept, learning-graph, ai]
confidence: {node.get('confidence', 1.0)}
---

# {title}

{node.get('description', node.get('summary', 'Learned concept.'))}

## Connections
{', '.join(related) if related else "No linked concepts yet."}

---
*Generated by Hermclaw Second Brain Sync*
"""
                    note_path.write_text(note_body, encoding="utf-8")
                    notes_created += 1
        except Exception as e:
            logger.debug("vault.sync_learning_graph_error", exc_info=e)

        # 2. Sync Goals
        try:
            goals_file = Path.home() / ".hermclaw" / "goals.json"
            if goals_file.exists():
                g_data = json.loads(goals_file.read_text(encoding="utf-8"))
                goals_dir = vault_dir / "Goals"
                goals_dir.mkdir(exist_ok=True)

                for g in g_data.get("goals", []):
                    title = g.get("title", "Goal")
                    clean_title = re.sub(r'[\\/*?:"<>|]', "", title)
                    note_path = goals_dir / f"{clean_title}.md"
                    note_body = f"""---
title: "{title}"
date: {now}
tags: [goal, strategy, status-{g.get('status', 'active')}]
---

# 🎯 {title}

**Status**: `{g.get('status', 'active')}`
**Created**: {g.get('created_at', now)}

{g.get('description', '')}

---
*Generated by Hermclaw Second Brain Sync*
"""
                    note_path.write_text(note_body, encoding="utf-8")
                    notes_created += 1
        except Exception as e:
            logger.debug("vault.sync_goals_error", exc_info=e)

        # 3. Create or update Map of Content (MOC) index
        index_file = vault_dir / "000_Index.md"
        all_md_files = list(vault_dir.rglob("*.md"))
        links_list = []
        for f in all_md_files:
            if f.name != "000_Index.md":
                links_list.append(f"- [[{f.stem}]]")

        index_content = f"""---
title: "Hermclaw Second Brain Index"
date: {now}
tags: [index, moc, dashboard]
---

# 🧠 Hermclaw Second Brain (Map of Content)

Welcome to your synchronized Obsidian knowledge vault.

## All Vault Notes ({len(links_list)} total):
{chr(10).join(links_list) if links_list else "No notes found yet."}

---
*Updated automatically by Hermclaw Knowledge Vault Tool*
"""
        index_file.write_text(index_content, encoding="utf-8")

        return ToolResult(
            ok=True,
            output=f"Vault sync complete! Synced {notes_created} notes to '{vault_dir}'. Index updated at '{index_file}'.",
            metadata={"vault_dir": str(vault_dir), "notes_synced": notes_created},
        )

    def _create_note(
        self,
        vault_dir: Path,
        title: str,
        content: str,
        tags_str: str,
        links_str: str,
    ) -> ToolResult:
        """Create a structured Markdown note in the vault."""
        if not title:
            return ToolResult(ok=False, output="", error="'title' is required to create a note.")

        clean_title = re.sub(r'[\\/*?:"<>|]', "", title.strip())
        note_file = vault_dir / f"{clean_title}.md"

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tags = [f'"{t.strip()}"' for t in tags_str.split(",") if t.strip()]
        if not tags:
            tags = ['"knowledge"', '"hermclaw"']

        links = [f"[[{l.strip()}]]" for l in links_str.split(",") if l.strip()]

        wikilinks_section = ""
        if links:
            wikilinks_section = "\n\n## Related Topics\n" + ", ".join(links)

        note_text = f"""---
title: "{title}"
date: {now}
tags: [{', '.join(tags)}]
---

# {title}

{content}{wikilinks_section}

---
*Created by Hermclaw Knowledge Vault*
"""
        note_file.write_text(note_text, encoding="utf-8")
        return ToolResult(
            ok=True,
            output=f"Created note '{title}' at {note_file}.",
            metadata={"path": str(note_file)},
        )

    def _query_vault(self, vault_dir: Path, query: str) -> ToolResult:
        """Search across all markdown notes in the vault."""
        if not query:
            return ToolResult(ok=False, output="", error="'query' is required for search.")

        query_lower = query.lower().strip()
        matches: list[dict[str, Any]] = []

        for md_file in vault_dir.rglob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8", errors="replace")
                if query_lower in text.lower():
                    # Extract snippet
                    lines = text.splitlines()
                    matched_lines = [l.strip() for l in lines if query_lower in l.lower()][:3]
                    matches.append({
                        "file": md_file.name,
                        "title": md_file.stem,
                        "path": str(md_file),
                        "snippet": " ... ".join(matched_lines),
                    })
            except Exception:
                pass

        if not matches:
            return ToolResult(ok=True, output=f"No notes matching '{query}' found in vault '{vault_dir}'.")

        out_lines = [f"Found {len(matches)} matching note(s) for '{query}':"]
        for m in matches[:10]:
            out_lines.append(f"- **[[{m['title']}]]** (`{m['file']}`): {m['snippet']}")

        return ToolResult(ok=True, output="\n".join(out_lines), metadata={"matches": matches})

    def _list_notes(self, vault_dir: Path) -> ToolResult:
        """List all notes in the vault."""
        files = list(vault_dir.rglob("*.md"))
        if not files:
            return ToolResult(ok=True, output=f"Vault '{vault_dir}' is currently empty. Run action='sync_vault' to populate it.")

        lines = [f"📁 **Knowledge Vault Notes** ({len(files)} total in `{vault_dir}`):"]
        for f in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[:25]:
            lines.append(f"  • [[{f.stem}]] (modified {datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M')})")

        return ToolResult(ok=True, output="\n".join(lines))
