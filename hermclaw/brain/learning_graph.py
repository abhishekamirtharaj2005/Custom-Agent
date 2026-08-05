"""Learning Graph: builds a concept relationship graph from interactions.

Tracks concepts the agent has learned, how they connect, and their
confidence levels. Provides visualization and traversal capabilities.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import structlog

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

logger = structlog.get_logger(__name__)

_GRAPH_SCHEMA = """
CREATE TABLE IF NOT EXISTS concepts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT DEFAULT 'general',
    description TEXT DEFAULT '',
    confidence REAL DEFAULT 0.5,
    usage_count INTEGER DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS relationships (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES concepts(id),
    target_id TEXT NOT NULL REFERENCES concepts(id),
    relation_type TEXT NOT NULL DEFAULT 'related_to',
    strength REAL DEFAULT 0.5,
    created_at REAL NOT NULL,
    UNIQUE(source_id, target_id, relation_type)
);

CREATE TABLE IF NOT EXISTS learning_events (
    id TEXT PRIMARY KEY,
    concept_id TEXT NOT NULL REFERENCES concepts(id),
    event_type TEXT NOT NULL,
    details TEXT DEFAULT '{}',
    created_at REAL NOT NULL
);
"""

RELATION_TYPES = [
    "related_to", "is_a", "has_a", "part_of", "used_by", "depends_on",
    "similar_to", "opposite_of", "causes", "prerequisite_for", "example_of",
]


class LearningGraph:
    """SQLite-backed concept relationship graph."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            db_path = Path.home() / ".hermclaw" / "learning_graph.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db_path))
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_GRAPH_SCHEMA)

    def close(self) -> None:
        self._db.close()

    def add_concept(self, name: str, category: str = "general",
                    description: str = "", confidence: float = 0.5) -> str:
        now = time.time()
        cid = uuid.uuid4().hex[:8]
        existing = self._db.execute(
            "SELECT id FROM concepts WHERE name = ?", (name.lower(),)
        ).fetchone()
        if existing:
            self._db.execute(
                "UPDATE concepts SET usage_count = usage_count + 1, confidence = MIN(1.0, confidence + 0.1), updated_at = ? WHERE id = ?",
                (now, existing["id"]),
            )
            self._db.commit()
            return existing["id"]

        self._db.execute(
            "INSERT INTO concepts (id, name, category, description, confidence, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (cid, name.lower(), category, description, confidence, now, now),
        )
        self._db.commit()
        return cid

    def add_relationship(self, source: str, target: str,
                         relation_type: str = "related_to", strength: float = 0.5) -> str:
        source_id = self.add_concept(source)
        target_id = self.add_concept(target)

        rid = uuid.uuid4().hex[:8]
        try:
            self._db.execute(
                "INSERT INTO relationships (id, source_id, target_id, relation_type, strength, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (rid, source_id, target_id, relation_type, strength, time.time()),
            )
            self._db.commit()
        except sqlite3.IntegrityError:
            self._db.execute(
                "UPDATE relationships SET strength = MIN(1.0, strength + 0.1) "
                "WHERE source_id = ? AND target_id = ? AND relation_type = ?",
                (source_id, target_id, relation_type),
            )
            self._db.commit()
        return rid

    def get_neighbors(self, concept_name: str, depth: int = 1) -> dict:
        concept = self._db.execute(
            "SELECT * FROM concepts WHERE name = ?", (concept_name.lower(),)
        ).fetchone()
        if not concept:
            return {"error": f"Concept '{concept_name}' not found."}

        result = {"concept": dict(concept), "relationships": []}
        rels = self._db.execute(
            """SELECT r.*, cs.name as source_name, ct.name as target_name
               FROM relationships r
               JOIN concepts cs ON r.source_id = cs.id
               JOIN concepts ct ON r.target_id = ct.id
               WHERE r.source_id = ? OR r.target_id = ?""",
            (concept["id"], concept["id"]),
        ).fetchall()
        result["relationships"] = [dict(r) for r in rels]
        return result

    def stats(self) -> dict:
        concepts = self._db.execute("SELECT COUNT(*) as n FROM concepts").fetchone()["n"]
        rels = self._db.execute("SELECT COUNT(*) as n FROM relationships").fetchone()["n"]
        top = self._db.execute(
            "SELECT name, usage_count, confidence FROM concepts ORDER BY usage_count DESC LIMIT 10"
        ).fetchall()
        categories = self._db.execute(
            "SELECT category, COUNT(*) as n FROM concepts GROUP BY category ORDER BY n DESC"
        ).fetchall()
        return {
            "total_concepts": concepts,
            "total_relationships": rels,
            "top_concepts": [dict(t) for t in top],
            "categories": {r["category"]: r["n"] for r in categories},
        }

    def visualize_ascii(self, concept_name: Optional[str] = None, max_nodes: int = 15) -> str:
        """Generate an ASCII visualization of the graph."""
        if concept_name:
            neighbors = self.get_neighbors(concept_name)
            if "error" in neighbors:
                return neighbors["error"]
            lines = [f"=== Learning Graph: {concept_name} ===", ""]
            concept = neighbors["concept"]
            lines.append(f"  [{concept['name']}] (conf: {concept['confidence']:.1f}, used: {concept['usage_count']}x)")
            lines.append("")
            for r in neighbors["relationships"]:
                if r["source_name"] == concept_name.lower():
                    lines.append(f"    --[{r['relation_type']}]--> {r['target_name']} (str: {r['strength']:.1f})")
                else:
                    lines.append(f"    <--[{r['relation_type']}]-- {r['source_name']} (str: {r['strength']:.1f})")
            return "\n".join(lines)
        else:
            concepts = self._db.execute(
                "SELECT * FROM concepts ORDER BY usage_count DESC LIMIT ?", (max_nodes,)
            ).fetchall()
            if not concepts:
                return "Learning graph is empty."
            lines = ["=== Learning Graph Overview ===", ""]
            for c in concepts:
                bar = "#" * int(c["confidence"] * 10)
                lines.append(f"  [{c['name']}] [{bar:<10}] {c['category']} (used: {c['usage_count']}x)")
            return "\n".join(lines)

    def search(self, query: str) -> list[dict]:
        rows = self._db.execute(
            "SELECT * FROM concepts WHERE name LIKE ? OR description LIKE ? ORDER BY usage_count DESC LIMIT 20",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
        return [dict(r) for r in rows]


class LearningGraphTool(ToolABC):
    """Tool for managing the concept learning graph."""

    def __init__(self, graph: Optional[LearningGraph] = None) -> None:
        self._graph = graph or LearningGraph()

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="learning_graph",
            description=(
                "Manage your concept learning graph. Use to record what you've learned "
                "and how concepts relate. Actions: learn (add concept), connect (add relationship), "
                "explore (view connections), search, visualize (ASCII graph), stats."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["learn", "connect", "explore", "search", "visualize", "stats"],
                    },
                    "concept": {"type": "string", "description": "Concept name."},
                    "category": {"type": "string", "description": "Concept category."},
                    "description": {"type": "string", "description": "What you learned."},
                    "target": {"type": "string", "description": "Target concept (for connect)."},
                    "relation": {
                        "type": "string",
                        "enum": RELATION_TYPES,
                        "description": "Relationship type (for connect).",
                    },
                    "query": {"type": "string", "description": "Search query."},
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "")
        try:
            if action == "learn":
                name = args.get("concept", "")
                if not name:
                    return ToolResult(ok=False, output="", error="'concept' required.")
                cid = self._graph.add_concept(
                    name, args.get("category", "general"), args.get("description", ""),
                )
                return ToolResult(ok=True, output=f"Learned concept '{name}' [{cid}]")

            elif action == "connect":
                source = args.get("concept", "")
                target = args.get("target", "")
                if not source or not target:
                    return ToolResult(ok=False, output="", error="'concept' and 'target' required.")
                rel = args.get("relation", "related_to")
                self._graph.add_relationship(source, target, rel)
                return ToolResult(ok=True, output=f"Connected: {source} --[{rel}]--> {target}")

            elif action == "explore":
                name = args.get("concept", "")
                if not name:
                    return ToolResult(ok=False, output="", error="'concept' required.")
                result = self._graph.get_neighbors(name)
                if "error" in result:
                    return ToolResult(ok=False, output="", error=result["error"])
                return ToolResult(ok=True, output=json.dumps(result, indent=2, default=str))

            elif action == "search":
                q = args.get("query", "")
                results = self._graph.search(q)
                if not results:
                    return ToolResult(ok=True, output="No concepts found.")
                lines = [f"Found {len(results)} concept(s):"]
                for r in results:
                    lines.append(f"  [{r['id']}] {r['name']} ({r['category']}) - used {r['usage_count']}x")
                return ToolResult(ok=True, output="\n".join(lines))

            elif action == "visualize":
                viz = self._graph.visualize_ascii(args.get("concept"))
                return ToolResult(ok=True, output=viz)

            elif action == "stats":
                s = self._graph.stats()
                return ToolResult(ok=True, output=json.dumps(s, indent=2, default=str))

            else:
                return ToolResult(ok=False, output="", error=f"Unknown action: {action}")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Learning graph error: {exc}")
