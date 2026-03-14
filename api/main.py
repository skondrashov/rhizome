"""
Rhizome Social API — upvotes, trending, and comments.

Thin FastAPI app backed by SQLite. Designed to degrade gracefully:
if this API is down, the static SPA still works, just without social features.

Run: uvicorn api.main:app --host 0.0.0.0 --port 8100
"""

import hashlib
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ─── Config ──────────────────────────────────────────────────

DB_PATH = os.environ.get(
    "RHIZOME_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "rhizome.db"),
)

VOTE_RATE_LIMIT = 30       # per hour per fingerprint
COMMENT_RATE_LIMIT = 5     # per hour per fingerprint
COMMENT_MAX_LENGTH = 2000
FLAG_HIDE_THRESHOLD = 3
TRENDING_RECENT_MIN = 3
TRENDING_RATIO = 0.3
HOT_THRESHOLD = 5
RECENT_WINDOW_DAYS = 7

app = FastAPI(title="Rhizome API", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://thisminute.org", "http://localhost:8080", "null"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ─── Database ────────────────────────────────────────────────

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


def init_db():
    """Create tables if they don't exist."""
    if not os.path.exists(SCHEMA_PATH):
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.close()


init_db()


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ─── Helpers ─────────────────────────────────────────────────

def get_fingerprint(request: Request) -> str:
    """SHA-256 of IP + User-Agent for anonymous identity."""
    ip = request.client.host if request.client else "unknown"
    # Check X-Forwarded-For for reverse proxy
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    ua = request.headers.get("user-agent", "")
    raw = f"{ip}:{ua}"
    return hashlib.sha256(raw.encode()).hexdigest()


_RATE_LIMIT_TABLES = {"upvotes", "comments"}


def check_rate_limit(conn: sqlite3.Connection, fingerprint: str, table: str, limit: int):
    """Raise 429 if fingerprint exceeds rate limit in the last hour."""
    if table not in _RATE_LIMIT_TABLES:
        raise ValueError(f"Invalid rate limit table: {table}")
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = conn.execute(
        f"SELECT COUNT(*) as cnt FROM {table} WHERE fingerprint = ? AND created_at > ?",
        (fingerprint, cutoff),
    ).fetchone()
    if row and row["cnt"] >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


def strip_html(text: str) -> str:
    """Remove HTML tags."""
    return re.sub(r"<[^>]+>", "", text)


def time_ago(iso_str: str) -> str:
    """Convert ISO timestamp to human-readable time-ago string."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        diff = datetime.now(timezone.utc) - dt
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days < 30:
            return f"{days}d ago"
        months = days // 30
        return f"{months}mo ago"
    except Exception:
        return iso_str


# ─── Models ──────────────────────────────────────────────────

class CommentCreate(BaseModel):
    display_name: str = Field(default="Anonymous", max_length=50)
    body: str = Field(max_length=COMMENT_MAX_LENGTH)
    honeypot: str = Field(default="")  # should always be empty


# ─── Endpoints ───────────────────────────────────────────────

@app.get("/rhizome/api/votes")
def get_all_votes():
    """All patterns' vote counts, recent counts, and seriousness scores."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RECENT_WINDOW_DAYS)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT
                pattern_id,
                COUNT(*) as total,
                SUM(CASE WHEN created_at > ? THEN 1 ELSE 0 END) as recent
            FROM upvotes
            GROUP BY pattern_id
            """,
            (cutoff,),
        ).fetchall()

    result = {}
    for row in rows:
        total = row["total"]
        recent = row["recent"]
        seriousness = total + (recent * 3)

        rate_label = None
        if recent >= HOT_THRESHOLD:
            rate_label = "hot"
        elif recent >= TRENDING_RECENT_MIN and total > 0 and (recent / total) >= TRENDING_RATIO:
            rate_label = "trending"

        result[row["pattern_id"]] = {
            "total": total,
            "recent": recent,
            "seriousness": seriousness,
            "rate_label": rate_label,
        }

    return result


@app.post("/rhizome/api/vote/{pattern_id}")
def cast_vote(pattern_id: str, request: Request):
    """Cast an upvote. Returns 409 if already voted."""
    fingerprint = get_fingerprint(request)
    with get_db() as conn:
        check_rate_limit(conn, fingerprint, "upvotes", VOTE_RATE_LIMIT)
        try:
            conn.execute(
                "INSERT INTO upvotes (pattern_id, fingerprint) VALUES (?, ?)",
                (pattern_id, fingerprint),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Already voted") from None
    return {"ok": True, "pattern_id": pattern_id}


@app.get("/rhizome/api/comments/{pattern_id}")
def get_comments(pattern_id: str):
    """Get non-flagged comments for a pattern."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.display_name, c.body, c.created_at,
                   (SELECT COUNT(*) FROM comment_flags WHERE comment_id = c.id) as flag_count
            FROM comments c
            WHERE c.pattern_id = ? AND c.flagged = 0
            ORDER BY c.created_at DESC, c.id DESC
            """,
            (pattern_id,),
        ).fetchall()

    return [
        {
            "id": row["id"],
            "display_name": row["display_name"],
            "body": row["body"],
            "created_at": row["created_at"],
            "time_ago": time_ago(row["created_at"]),
            "flag_count": row["flag_count"],
            "hidden": row["flag_count"] >= FLAG_HIDE_THRESHOLD,
        }
        for row in rows
    ]


@app.post("/rhizome/api/comments/{pattern_id}")
def post_comment(pattern_id: str, comment: CommentCreate, request: Request):
    """Post a comment. Honeypot field must be empty."""
    if comment.honeypot:
        # Bot detected — return success but don't save
        return {"ok": True, "id": 0}

    fingerprint = get_fingerprint(request)
    body = strip_html(comment.body.strip())
    display_name = strip_html(comment.display_name.strip()) or "Anonymous"

    if not body:
        raise HTTPException(status_code=400, detail="Comment body required")
    if len(body) > COMMENT_MAX_LENGTH:
        raise HTTPException(status_code=400, detail="Comment too long")

    with get_db() as conn:
        check_rate_limit(conn, fingerprint, "comments", COMMENT_RATE_LIMIT)
        cursor = conn.execute(
            "INSERT INTO comments (pattern_id, fingerprint, display_name, body) VALUES (?, ?, ?, ?)",
            (pattern_id, fingerprint, display_name, body),
        )
        comment_id = cursor.lastrowid

    return {"ok": True, "id": comment_id}


@app.post("/rhizome/api/comments/{comment_id}/flag")
def flag_comment(comment_id: int, request: Request):
    """Flag a comment. Auto-hides at threshold."""
    fingerprint = get_fingerprint(request)
    with get_db() as conn:
        # Verify comment exists
        comment = conn.execute(
            "SELECT id FROM comments WHERE id = ?", (comment_id,)
        ).fetchone()
        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")

        try:
            conn.execute(
                "INSERT INTO comment_flags (comment_id, fingerprint) VALUES (?, ?)",
                (comment_id, fingerprint),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Already flagged") from None

        # Check if should auto-hide
        flag_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM comment_flags WHERE comment_id = ?",
            (comment_id,),
        ).fetchone()["cnt"]

        if flag_count >= FLAG_HIDE_THRESHOLD:
            conn.execute(
                "UPDATE comments SET flagged = 1 WHERE id = ?", (comment_id,)
            )

    return {"ok": True, "flag_count": flag_count}


@app.get("/rhizome/api/health")
def health():
    return {"status": "ok"}
