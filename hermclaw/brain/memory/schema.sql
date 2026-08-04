-- Hermclaw Brain memory schema. One SQLite file per profile at
-- ~/.hermclaw/profiles/<profile>/state.db, opened in WAL mode so a
-- concurrent reader (e.g. `hermclaw status`) never blocks an
-- in-progress agent turn's writes. Ported field-for-field from Hermes
-- Agent's ~/.hermes/state.db shape (C.2.3).

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    channel TEXT,
    model TEXT,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    token_count INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0,
    title TEXT,
    -- Extension beyond the spec's literal schema: nullable lineage link so
    -- the ContextCompressor (C.2.4) can start a "continuation session"
    -- linked to the session it compressed away from. Documented in
    -- MERGE_DECISIONS.md as a necessary, additive extension.
    parent_session_id TEXT REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT REFERENCES sessions(id),
    role TEXT,
    content TEXT,
    tool_calls TEXT,  -- JSON
    reasoning_tokens INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Extension: messages excluded from the live prompt by compression are
    -- flagged rather than deleted, so session_search still finds them.
    compressed_away INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_parent ON sessions(parent_session_id);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,
    content='messages',
    content_rowid='id'
);

-- Triggers to keep messages_fts in sync with messages on insert/update/delete.
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;
