"""Vector memory: semantic search over the agent's long-term memory.

Uses a local SQLite-based vector store (no external dependencies) with
cosine similarity search. Embeddings come from either:
- Ollama (local, free)
- OpenAI (api key required)

Falls back to keyword search (FTS5) if no embedding provider is available.
"""

from __future__ import annotations

import json
import math
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx
import structlog

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

logger = structlog.get_logger(__name__)

_VECTOR_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_vectors (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    embedding TEXT,
    category TEXT DEFAULT 'general',
    metadata TEXT DEFAULT '{}',
    created_at REAL NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    id, content, category,
    content='memory_vectors',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS memory_vectors_ai AFTER INSERT ON memory_vectors BEGIN
    INSERT INTO memory_fts(rowid, id, content, category)
    VALUES (new.rowid, new.id, new.content, new.category);
END;

CREATE TRIGGER IF NOT EXISTS memory_vectors_ad AFTER DELETE ON memory_vectors BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, id, content, category)
    VALUES ('delete', old.rowid, old.id, old.content, old.category);
END;
"""


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class VectorMemory:
    """Semantic memory store with vector similarity search."""

    def __init__(self, db_path: Path, embedding_provider: str = "ollama", chat_model_name: str = "gemma4:12b") -> None:
        self._db = sqlite3.connect(str(db_path))
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_VECTOR_SCHEMA)
        self._embedding_provider = embedding_provider
        self._embedding_model = "nomic-embed-text" if embedding_provider == "ollama" else "text-embedding-3-small"
        self._chat_model_name = chat_model_name  # fallback model for embeddings
        self._embed_warned = False  # only warn once about embedding failures

    def close(self) -> None:
        self._db.close()

    async def _get_embedding(self, text: str) -> Optional[list[float]]:
        """Get embedding vector for text."""
        try:
            if self._embedding_provider == "ollama":
                return await self._ollama_embed(text)
            elif self._embedding_provider == "openai":
                return await self._openai_embed(text)
        except Exception as exc:
            if not self._embed_warned:
                logger.info("vector_memory.using_keyword_fallback", reason=str(exc)[:100])
                self._embed_warned = True
        return None

    async def _ollama_embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try /api/embeddings first (standard Ollama API)
            for endpoint, payload_key, response_key in [
                ("/api/embeddings", "prompt", "embedding"),
                ("/api/embed", "input", "embeddings"),
            ]:
                try:
                    resp = await client.post(
                        f"http://localhost:11434{endpoint}",
                        json={"model": self._embedding_model, payload_key: text},
                    )
                    if resp.status_code == 404:
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    result = data.get(response_key, [])
                    if isinstance(result, list) and result:
                        return result if isinstance(result[0], float) else result[0]
                except httpx.HTTPStatusError:
                    continue

            # Last resort: try using the user's chat model for embeddings
            for endpoint, payload_key, response_key in [
                ("/api/embeddings", "prompt", "embedding"),
                ("/api/embed", "input", "embeddings"),
            ]:
                try:
                    resp = await client.post(
                        f"http://localhost:11434{endpoint}",
                        json={"model": self._chat_model_name, payload_key: text},
                    )
                    if resp.status_code == 404:
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    result = data.get(response_key, [])
                    if isinstance(result, list) and result:
                        return result if isinstance(result[0], float) else result[0]
                except httpx.HTTPStatusError:
                    continue

            raise RuntimeError("No Ollama embedding endpoint available")

    async def _openai_embed(self, text: str) -> list[float]:
        import os
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": self._embedding_model, "input": text},
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]

    async def store(self, content: str, category: str = "general", metadata: Optional[dict] = None) -> str:
        """Store a memory with optional embedding."""
        mid = uuid.uuid4().hex[:12]
        embedding = await self._get_embedding(content)
        embedding_json = json.dumps(embedding) if embedding else None

        self._db.execute(
            "INSERT INTO memory_vectors (id, content, embedding, category, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (mid, content, embedding_json, category, json.dumps(metadata or {}), time.time()),
        )
        self._db.commit()
        return mid

    async def search(self, query: str, limit: int = 5, category: Optional[str] = None) -> list[dict]:
        """Search memories semantically (vector) or by keyword (FTS5 fallback)."""
        query_embedding = await self._get_embedding(query)

        if query_embedding:
            return self._vector_search(query_embedding, limit, category)
        else:
            return self._keyword_search(query, limit, category)

    def _vector_search(self, query_embedding: list[float], limit: int, category: Optional[str]) -> list[dict]:
        """Search by cosine similarity."""
        if category:
            rows = self._db.execute(
                "SELECT * FROM memory_vectors WHERE embedding IS NOT NULL AND category = ?",
                (category,),
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT * FROM memory_vectors WHERE embedding IS NOT NULL"
            ).fetchall()

        scored = []
        for row in rows:
            try:
                stored_emb = json.loads(row["embedding"])
                score = _cosine_similarity(query_embedding, stored_emb)
                scored.append((score, dict(row)))
            except (json.JSONDecodeError, TypeError):
                continue

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, item in scored[:limit]:
            item["similarity"] = round(score, 4)
            item.pop("embedding", None)  # Don't return raw vectors
            results.append(item)
        return results

    def _keyword_search(self, query: str, limit: int, category: Optional[str]) -> list[dict]:
        """Fallback: FTS5 keyword search, with LIKE fallback if FTS fails."""
        # Sanitize query for FTS5 — extract individual words
        import re
        words = re.findall(r'\w+', query)
        if not words:
            return []

        # Try FTS5 first with OR-joined words
        fts_query = " OR ".join(words[:10])  # cap at 10 terms
        try:
            if category:
                rows = self._db.execute(
                    "SELECT mv.* FROM memory_fts mf JOIN memory_vectors mv ON mf.id = mv.id "
                    "WHERE mf.content MATCH ? AND mv.category = ? ORDER BY rank LIMIT ?",
                    (fts_query, category, limit),
                ).fetchall()
            else:
                rows = self._db.execute(
                    "SELECT mv.* FROM memory_fts mf JOIN memory_vectors mv ON mf.id = mv.id "
                    "WHERE mf.content MATCH ? ORDER BY rank LIMIT ?",
                    (fts_query, limit),
                ).fetchall()
        except Exception:
            # FTS5 failed — fall back to LIKE
            rows = []
            for word in words[:5]:
                if category:
                    found = self._db.execute(
                        "SELECT * FROM memory_vectors WHERE content LIKE ? AND category = ? LIMIT ?",
                        (f"%{word}%", category, limit),
                    ).fetchall()
                else:
                    found = self._db.execute(
                        "SELECT * FROM memory_vectors WHERE content LIKE ? LIMIT ?",
                        (f"%{word}%", limit),
                    ).fetchall()
                rows.extend(found)
            # Deduplicate by id
            seen = set()
            deduped = []
            for r in rows:
                rid = r["id"]
                if rid not in seen:
                    seen.add(rid)
                    deduped.append(r)
            rows = deduped[:limit]

        results = []
        for row in rows:
            item = dict(row)
            item.pop("embedding", None)
            item["similarity"] = 0.5  # moderate relevance for keyword matches
            results.append(item)
        return results

    def list_memories(self, category: Optional[str] = None, limit: int = 20) -> list[dict]:
        """List stored memories."""
        if category:
            rows = self._db.execute(
                "SELECT id, content, category, metadata, created_at FROM memory_vectors WHERE category = ? ORDER BY created_at DESC LIMIT ?",
                (category, limit),
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT id, content, category, metadata, created_at FROM memory_vectors ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete(self, memory_id: str) -> bool:
        cur = self._db.execute("DELETE FROM memory_vectors WHERE id = ?", (memory_id,))
        self._db.commit()
        return cur.rowcount > 0

    def stats(self) -> dict:
        total = self._db.execute("SELECT COUNT(*) as n FROM memory_vectors").fetchone()["n"]
        with_vectors = self._db.execute("SELECT COUNT(*) as n FROM memory_vectors WHERE embedding IS NOT NULL").fetchone()["n"]
        categories = self._db.execute("SELECT DISTINCT category FROM memory_vectors").fetchall()
        return {
            "total_memories": total,
            "with_embeddings": with_vectors,
            "categories": [r["category"] for r in categories],
        }


class MemoryManageTool(ToolABC):
    """Tool for managing the agent's long-term vector memory."""

    def __init__(self, vector_memory: VectorMemory) -> None:
        self._vm = vector_memory

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="memory",
            description=(
                "Manage your long-term memory. Actions: store (save information), "
                "search (find relevant memories semantically), list (browse memories), "
                "delete (remove a memory), stats (memory statistics). "
                "Use this to remember important facts, user preferences, and learnings."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["store", "search", "list", "delete", "stats"],
                        "description": "Memory action.",
                    },
                    "content": {"type": "string", "description": "Content to store or query to search."},
                    "category": {
                        "type": "string",
                        "description": "Category: general, user_preference, fact, skill, conversation.",
                    },
                    "memory_id": {"type": "string", "description": "Memory ID for delete."},
                    "limit": {"type": "integer", "description": "Max results (default 5)."},
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "")

        try:
            if action == "store":
                content = args.get("content", "")
                if not content:
                    return ToolResult(ok=False, output="", error="'content' required for store.")
                mid = await self._vm.store(
                    content,
                    category=args.get("category", "general"),
                )
                return ToolResult(ok=True, output=f"Stored memory [{mid}]: {content[:100]}")

            elif action == "search":
                content = args.get("content", "")
                if not content:
                    return ToolResult(ok=False, output="", error="'content' (query) required for search.")
                results = await self._vm.search(
                    content,
                    limit=args.get("limit", 5),
                    category=args.get("category"),
                )
                if not results:
                    return ToolResult(ok=True, output="No matching memories found.")
                lines = [f"Found {len(results)} memories:"]
                for r in results:
                    sim = r.get("similarity", 0)
                    lines.append(f"  [{r['id']}] (sim:{sim:.2f}) [{r['category']}] {r['content'][:120]}")
                return ToolResult(ok=True, output="\n".join(lines))

            elif action == "list":
                memories = self._vm.list_memories(
                    category=args.get("category"),
                    limit=args.get("limit", 20),
                )
                if not memories:
                    return ToolResult(ok=True, output="No memories stored yet.")
                lines = [f"Memories ({len(memories)}):"]
                for m in memories:
                    lines.append(f"  [{m['id']}] [{m['category']}] {m['content'][:100]}")
                return ToolResult(ok=True, output="\n".join(lines))

            elif action == "delete":
                mid = args.get("memory_id", "")
                if not mid:
                    return ToolResult(ok=False, output="", error="'memory_id' required for delete.")
                ok = self._vm.delete(mid)
                return ToolResult(ok=ok, output=f"Deleted memory {mid}" if ok else "", error="Memory not found." if not ok else None)

            elif action == "stats":
                stats = self._vm.stats()
                return ToolResult(ok=True, output=json.dumps(stats, indent=2))

            else:
                return ToolResult(ok=False, output="", error=f"Unknown action: {action}")

        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Memory error: {exc}")
