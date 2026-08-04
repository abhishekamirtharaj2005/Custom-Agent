from __future__ import annotations

import random
import sqlite3
import time
from pathlib import Path

from hermclaw.brain.memory.store import MemoryStore


def test_session_and_message_round_trip(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "state.db")
    sid = store.create_session(channel="cli", model="test-model", title="test")
    store.add_message(sid, "user", "hello")
    store.add_message(sid, "assistant", "hi there")

    session = store.get_session(sid)
    assert session.channel == "cli"
    assert session.title == "test"

    messages = store.get_session_messages(sid)
    assert [m.role for m in messages] == ["user", "assistant"]
    assert [m.content for m in messages] == ["hello", "hi there"]


def test_wal_mode_enabled(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    MemoryStore(db_path)
    conn = sqlite3.connect(str(db_path))
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_state_db_permissions_are_owner_only(tmp_path: Path) -> None:
    import stat

    db_path = tmp_path / "state.db"
    MemoryStore(db_path)
    mode = stat.S_IMODE(db_path.stat().st_mode)
    assert mode & ~0o600 == 0, f"state.db mode {oct(mode)} is wider than owner-only"


def test_session_search_finds_matches() -> None:
    import tempfile

    store = MemoryStore(Path(tempfile.mkdtemp()) / "state.db")
    sid = store.create_session(channel="cli", model="test-model")
    store.add_message(sid, "user", "How do I configure Postgres for high availability?")
    store.add_message(sid, "assistant", "You'll want streaming replication and a connection pooler.")
    store.add_message(sid, "user", "What about backups?")

    hits = store.session_search("Postgres replication")
    assert len(hits) >= 1
    assert any("Postgres" in h.content or "replication" in h.content for h in hits)


def test_session_search_handles_special_characters_safely() -> None:
    import tempfile

    store = MemoryStore(Path(tempfile.mkdtemp()) / "state.db")
    sid = store.create_session(channel="cli", model="test-model")
    store.add_message(sid, "user", "test message")
    # FTS5 special syntax characters shouldn't raise -- session_search
    # must sanitize rather than pass the raw query straight to MATCH.
    hits = store.session_search('weird "query" with: colons AND -dashes OR *')
    assert isinstance(hits, list)


def test_session_search_performance_under_500_messages() -> None:
    import tempfile

    store = MemoryStore(Path(tempfile.mkdtemp()) / "state.db")
    sid = store.create_session(channel="cli", model="test-model")
    words = ["database", "error", "postgres", "timeout", "migration", "index", "query", "schema", "deploy", "auth"]
    random.seed(42)
    for i in range(500):
        content = f"message {i} about " + " ".join(random.choices(words, k=6))
        store.add_message(sid, "user" if i % 2 == 0 else "assistant", content)

    start = time.perf_counter()
    hits = store.session_search("postgres timeout", limit=10)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 50, f"session_search took {elapsed_ms:.2f}ms, expected under 50ms"
    assert len(hits) > 0


def test_compressed_away_messages_excluded_when_requested() -> None:
    import tempfile

    store = MemoryStore(Path(tempfile.mkdtemp()) / "state.db")
    sid = store.create_session(channel="cli", model="test-model")
    ids = [store.add_message(sid, "user", f"msg {i}") for i in range(5)]
    store.mark_messages_compressed_away(ids[:3])

    all_msgs = store.get_session_messages(sid, include_compressed_away=True)
    active_msgs = store.get_session_messages(sid, include_compressed_away=False)
    assert len(all_msgs) == 5
    assert len(active_msgs) == 2


def test_compressed_away_messages_still_searchable() -> None:
    import tempfile

    store = MemoryStore(Path(tempfile.mkdtemp()) / "state.db")
    sid = store.create_session(channel="cli", model="test-model")
    mid = store.add_message(sid, "user", "a very specific searchable phrase about zebras")
    store.mark_messages_compressed_away([mid])

    hits = store.session_search("zebras")
    assert len(hits) == 1


def test_parent_session_id_lineage() -> None:
    import tempfile

    store = MemoryStore(Path(tempfile.mkdtemp()) / "state.db")
    sid1 = store.create_session(channel="cli", model="test-model")
    sid2 = store.create_session(channel="cli", model="test-model", parent_session_id=sid1)
    session2 = store.get_session(sid2)
    assert session2.parent_session_id == sid1


async def test_async_wrappers_delegate_correctly() -> None:
    import tempfile

    store = MemoryStore(Path(tempfile.mkdtemp()) / "state.db")
    sid = await store.a_create_session(channel="cli", model="test-model")
    await store.a_add_message(sid, "user", "async hello")
    messages = await store.a_get_session_messages(sid)
    assert messages[0].content == "async hello"
    hits = await store.a_session_search("async hello")
    assert len(hits) == 1
