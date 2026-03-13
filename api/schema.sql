-- Rhizome social features: upvotes and comments
-- SQLite schema

CREATE TABLE IF NOT EXISTS upvotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(pattern_id, fingerprint)
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT 'Anonymous',
    body TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    flagged INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS comment_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id INTEGER NOT NULL,
    fingerprint TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(comment_id, fingerprint),
    FOREIGN KEY (comment_id) REFERENCES comments(id)
);

CREATE INDEX IF NOT EXISTS idx_upvotes_pattern ON upvotes(pattern_id);
CREATE INDEX IF NOT EXISTS idx_upvotes_created ON upvotes(created_at);
CREATE INDEX IF NOT EXISTS idx_comments_pattern ON comments(pattern_id);
CREATE INDEX IF NOT EXISTS idx_comment_flags_comment ON comment_flags(comment_id);
