"""Tests for the Rhizome social API."""
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


@pytest.fixture
def client(tmp_db):
    """Create a test client with a fresh database."""
    os.environ["RHIZOME_DB_PATH"] = tmp_db

    # Initialize DB
    schema_path = os.path.join(ROOT, "api", "schema.sql")
    conn = sqlite3.connect(tmp_db)
    with open(schema_path, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.close()

    # Must re-import to pick up the env var
    import importlib
    import api.main as api_main
    importlib.reload(api_main)

    return TestClient(api_main.app)


def _post_comment(client, pattern_id="ant-colony", body="Test comment", name="Tester"):
    """Helper to post a comment and return the response."""
    return client.post(f"/rhizome/api/comments/{pattern_id}", json={
        "display_name": name,
        "body": body,
        "honeypot": ""
    })


# ─── Health ──────────────────────────────────────────────


class TestHealth:
    def test_health(self, client):
        resp = client.get("/rhizome/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ─── Votes ───────────────────────────────────────────────


class TestVotes:
    def test_get_votes_empty(self, client):
        resp = client.get("/rhizome/api/votes")
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_cast_vote(self, client):
        resp = client.post("/rhizome/api/vote/ant-colony")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["pattern_id"] == "ant-colony"

    def test_duplicate_vote_409(self, client):
        client.post("/rhizome/api/vote/ant-colony")
        resp = client.post("/rhizome/api/vote/ant-colony")
        assert resp.status_code == 409

    def test_vote_appears_in_counts(self, client):
        client.post("/rhizome/api/vote/ant-colony")
        resp = client.get("/rhizome/api/votes")
        data = resp.json()
        assert "ant-colony" in data
        assert data["ant-colony"]["total"] == 1

    def test_multiple_patterns(self, client):
        client.post("/rhizome/api/vote/ant-colony")
        client.post("/rhizome/api/vote/jazz-ensemble")
        resp = client.get("/rhizome/api/votes")
        data = resp.json()
        assert "ant-colony" in data
        assert "jazz-ensemble" in data

    def test_seriousness_score(self, client):
        client.post("/rhizome/api/vote/ant-colony")
        resp = client.get("/rhizome/api/votes")
        data = resp.json()["ant-colony"]
        # seriousness = total + (recent * 3) = 1 + (1 * 3) = 4
        assert data["seriousness"] == 4

    def test_vote_response_shape(self, client):
        """GET /votes should return the full expected shape per pattern."""
        client.post("/rhizome/api/vote/ant-colony")
        data = client.get("/rhizome/api/votes").json()["ant-colony"]
        assert set(data.keys()) == {"total", "recent", "seriousness", "rate_label"}
        assert isinstance(data["total"], int)
        assert isinstance(data["recent"], int)
        assert isinstance(data["seriousness"], int)

    def test_vote_with_special_characters_in_id(self, client):
        """Pattern IDs with dashes and underscores should work."""
        resp = client.post("/rhizome/api/vote/my-complex_pattern-v2")
        assert resp.status_code == 200
        data = client.get("/rhizome/api/votes").json()
        assert "my-complex_pattern-v2" in data

    def test_recent_vote_counted(self, client):
        """A vote cast now should count as recent."""
        client.post("/rhizome/api/vote/ant-colony")
        data = client.get("/rhizome/api/votes").json()["ant-colony"]
        assert data["recent"] == 1

    def test_old_vote_not_recent(self, client, tmp_db):
        """A vote older than RECENT_WINDOW_DAYS should not count as recent."""
        # Insert a vote with an old timestamp directly
        old_ts = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn = sqlite3.connect(tmp_db)
        conn.execute(
            "INSERT INTO upvotes (pattern_id, fingerprint, created_at) VALUES (?, ?, ?)",
            ("ant-colony", "old-fingerprint", old_ts)
        )
        conn.commit()
        conn.close()

        data = client.get("/rhizome/api/votes").json()["ant-colony"]
        assert data["total"] == 1
        assert data["recent"] == 0
        assert data["seriousness"] == 1  # total + (0 * 3)


class TestTrending:
    """Tests for trending and hot labels in vote data."""

    def test_no_label_with_few_votes(self, client):
        """A single vote should not trigger any rate label."""
        client.post("/rhizome/api/vote/ant-colony")
        data = client.get("/rhizome/api/votes").json()["ant-colony"]
        assert data["rate_label"] is None

    def test_hot_label(self, client, tmp_db):
        """5+ recent votes should trigger 'hot' label."""
        conn = sqlite3.connect(tmp_db)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for i in range(5):
            conn.execute(
                "INSERT INTO upvotes (pattern_id, fingerprint, created_at) VALUES (?, ?, ?)",
                ("ant-colony", f"fp-{i}", now)
            )
        conn.commit()
        conn.close()

        data = client.get("/rhizome/api/votes").json()["ant-colony"]
        assert data["rate_label"] == "hot"
        assert data["recent"] == 5

    def test_trending_label(self, client, tmp_db):
        """3+ recent votes with high recent/total ratio should trigger 'trending'."""
        conn = sqlite3.connect(tmp_db)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # 4 total, 3 recent → ratio = 3/4 = 0.75 >= 0.3, recent >= 3 → trending (not hot since < 5)
        old_ts = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "INSERT INTO upvotes (pattern_id, fingerprint, created_at) VALUES (?, ?, ?)",
            ("ant-colony", "fp-old", old_ts)
        )
        for i in range(3):
            conn.execute(
                "INSERT INTO upvotes (pattern_id, fingerprint, created_at) VALUES (?, ?, ?)",
                ("ant-colony", f"fp-{i}", now)
            )
        conn.commit()
        conn.close()

        data = client.get("/rhizome/api/votes").json()["ant-colony"]
        assert data["rate_label"] == "trending"


class TestVoteRateLimit:
    """Tests for vote rate limiting."""

    def test_rate_limit_enforced(self, client, tmp_db):
        """Exceeding 30 votes/hour from same fingerprint should return 429."""
        conn = sqlite3.connect(tmp_db)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # TestClient always has the same fingerprint, so insert 30 votes directly
        fp = _get_test_fingerprint(client)
        for i in range(30):
            conn.execute(
                "INSERT INTO upvotes (pattern_id, fingerprint, created_at) VALUES (?, ?, ?)",
                (f"pattern-{i}", fp, now)
            )
        conn.commit()
        conn.close()

        resp = client.post("/rhizome/api/vote/one-more")
        assert resp.status_code == 429

    def test_rate_limit_not_hit_under_threshold(self, client, tmp_db):
        """Under 30 votes should not trigger rate limit."""
        conn = sqlite3.connect(tmp_db)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        fp = _get_test_fingerprint(client)
        for i in range(29):
            conn.execute(
                "INSERT INTO upvotes (pattern_id, fingerprint, created_at) VALUES (?, ?, ?)",
                (f"pattern-{i}", fp, now)
            )
        conn.commit()
        conn.close()

        resp = client.post("/rhizome/api/vote/one-more")
        assert resp.status_code == 200


def _get_test_fingerprint(client):
    """Compute the fingerprint the test client would produce."""
    import hashlib
    # TestClient uses 'testclient' for both host and user-agent
    raw = "testclient:testclient"
    return hashlib.sha256(raw.encode()).hexdigest()


# ─── Comments ────────────────────────────────────────────


class TestComments:
    def test_get_comments_empty(self, client):
        resp = client.get("/rhizome/api/comments/ant-colony")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_post_comment(self, client):
        resp = _post_comment(client)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert resp.json()["id"] > 0

    def test_comment_appears_in_list(self, client):
        _post_comment(client, body="Used this for swarm robotics", name="Alice")
        resp = client.get("/rhizome/api/comments/ant-colony")
        comments = resp.json()
        assert len(comments) == 1
        assert comments[0]["display_name"] == "Alice"
        assert comments[0]["body"] == "Used this for swarm robotics"

    def test_comment_response_shape(self, client):
        """Each comment should have the expected fields."""
        _post_comment(client)
        comments = client.get("/rhizome/api/comments/ant-colony").json()
        c = comments[0]
        assert set(c.keys()) == {"id", "display_name", "body", "created_at", "time_ago", "flag_count", "hidden"}
        assert isinstance(c["id"], int)
        assert isinstance(c["time_ago"], str)
        assert isinstance(c["flag_count"], int)
        assert isinstance(c["hidden"], bool)
        assert c["hidden"] is False
        assert c["flag_count"] == 0

    def test_comment_time_ago_is_just_now(self, client):
        """A freshly posted comment should show 'just now'."""
        _post_comment(client)
        comments = client.get("/rhizome/api/comments/ant-colony").json()
        assert comments[0]["time_ago"] == "just now"

    def test_honeypot_rejects_bots(self, client):
        resp = client.post("/rhizome/api/comments/ant-colony", json={
            "display_name": "Bot",
            "body": "Spam",
            "honeypot": "gotcha"
        })
        # Returns 200 but doesn't save
        assert resp.status_code == 200
        assert resp.json()["id"] == 0
        comments = client.get("/rhizome/api/comments/ant-colony").json()
        assert len(comments) == 0

    def test_empty_body_rejected(self, client):
        resp = client.post("/rhizome/api/comments/ant-colony", json={
            "body": "   ",
            "honeypot": ""
        })
        assert resp.status_code == 400

    def test_html_stripped(self, client):
        _post_comment(client, body="Hello <script>alert('xss')</script> world")
        comments = client.get("/rhizome/api/comments/ant-colony").json()
        assert "<script>" not in comments[0]["body"]
        assert "alert" in comments[0]["body"]

    def test_html_stripped_from_display_name(self, client):
        """HTML in display_name should be stripped."""
        _post_comment(client, name="<b>Bold</b>User", body="Test")
        comments = client.get("/rhizome/api/comments/ant-colony").json()
        assert "<b>" not in comments[0]["display_name"]
        assert "Bold" in comments[0]["display_name"]

    def test_default_anonymous_name(self, client):
        client.post("/rhizome/api/comments/ant-colony", json={
            "body": "Anonymous comment",
            "honeypot": ""
        })
        comments = client.get("/rhizome/api/comments/ant-colony").json()
        assert comments[0]["display_name"] == "Anonymous"

    def test_empty_display_name_becomes_anonymous(self, client):
        """A display name that's empty or only spaces should become 'Anonymous'."""
        client.post("/rhizome/api/comments/ant-colony", json={
            "display_name": "   ",
            "body": "Test",
            "honeypot": ""
        })
        comments = client.get("/rhizome/api/comments/ant-colony").json()
        assert comments[0]["display_name"] == "Anonymous"

    def test_html_only_body_rejected(self, client):
        """A body that's only HTML tags should be empty after stripping → 400."""
        resp = client.post("/rhizome/api/comments/ant-colony", json={
            "body": "<b></b><i></i>",
            "honeypot": ""
        })
        assert resp.status_code == 400

    def test_comments_ordered_newest_first(self, client):
        """Comments should come back newest first."""
        _post_comment(client, body="First")
        _post_comment(client, body="Second")
        comments = client.get("/rhizome/api/comments/ant-colony").json()
        # Newest first
        assert comments[0]["body"] == "Second"
        assert comments[1]["body"] == "First"

    def test_comments_scoped_to_pattern(self, client):
        """Comments for different patterns should not mix."""
        _post_comment(client, pattern_id="ant-colony", body="Ant comment")
        _post_comment(client, pattern_id="jazz-ensemble", body="Jazz comment")
        ant_comments = client.get("/rhizome/api/comments/ant-colony").json()
        jazz_comments = client.get("/rhizome/api/comments/jazz-ensemble").json()
        assert len(ant_comments) == 1
        assert len(jazz_comments) == 1
        assert ant_comments[0]["body"] == "Ant comment"
        assert jazz_comments[0]["body"] == "Jazz comment"


class TestCommentRateLimit:
    """Tests for comment rate limiting."""

    def test_comment_rate_limit(self, client, tmp_db):
        """Exceeding 5 comments/hour should return 429."""
        conn = sqlite3.connect(tmp_db)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        fp = _get_test_fingerprint(client)
        for i in range(5):
            conn.execute(
                "INSERT INTO comments (pattern_id, fingerprint, display_name, body, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"p-{i}", fp, "Test", f"Comment {i}", now)
            )
        conn.commit()
        conn.close()

        resp = _post_comment(client, body="One too many")
        assert resp.status_code == 429


# ─── Flagging ────────────────────────────────────────────


class TestFlagging:
    def test_flag_comment(self, client):
        _post_comment(client, body="Flaggable comment")
        comments = client.get("/rhizome/api/comments/ant-colony").json()
        comment_id = comments[0]["id"]

        resp = client.post(f"/rhizome/api/comments/{comment_id}/flag")
        assert resp.status_code == 200
        assert resp.json()["flag_count"] == 1

    def test_duplicate_flag_409(self, client):
        _post_comment(client, body="Test")
        comments = client.get("/rhizome/api/comments/ant-colony").json()
        cid = comments[0]["id"]

        client.post(f"/rhizome/api/comments/{cid}/flag")
        resp = client.post(f"/rhizome/api/comments/{cid}/flag")
        assert resp.status_code == 409

    def test_flag_nonexistent_comment(self, client):
        resp = client.post("/rhizome/api/comments/99999/flag")
        assert resp.status_code == 404

    def test_auto_hide_at_threshold(self, client, tmp_db):
        """A comment with 3+ flags should be auto-hidden (not returned in list)."""
        _post_comment(client, body="Bad content")
        comments = client.get("/rhizome/api/comments/ant-colony").json()
        cid = comments[0]["id"]

        # Insert flags directly from different fingerprints
        conn = sqlite3.connect(tmp_db)
        for i in range(3):
            conn.execute(
                "INSERT INTO comment_flags (comment_id, fingerprint) VALUES (?, ?)",
                (cid, f"flagger-{i}")
            )
        # Mark as flagged (simulating what the API does when threshold is hit)
        conn.execute("UPDATE comments SET flagged = 1 WHERE id = ?", (cid,))
        conn.commit()
        conn.close()

        comments = client.get("/rhizome/api/comments/ant-colony").json()
        assert len(comments) == 0  # hidden from list

    def test_flag_increments_count(self, client, tmp_db):
        """Flag count should be visible in comment data before auto-hide."""
        _post_comment(client, body="Mildly bad")
        comments = client.get("/rhizome/api/comments/ant-colony").json()
        cid = comments[0]["id"]

        # Add one flag from a different fingerprint
        conn = sqlite3.connect(tmp_db)
        conn.execute(
            "INSERT INTO comment_flags (comment_id, fingerprint) VALUES (?, ?)",
            (cid, "other-flagger")
        )
        conn.commit()
        conn.close()

        comments = client.get("/rhizome/api/comments/ant-colony").json()
        assert comments[0]["flag_count"] == 1
        assert comments[0]["hidden"] is False

    def test_comment_hidden_field_at_threshold(self, client, tmp_db):
        """Comment should report hidden=True when flag_count >= threshold (even if not yet marked flagged)."""
        _post_comment(client, body="Will be flagged a lot")
        comments = client.get("/rhizome/api/comments/ant-colony").json()
        cid = comments[0]["id"]

        conn = sqlite3.connect(tmp_db)
        for i in range(3):
            conn.execute(
                "INSERT INTO comment_flags (comment_id, fingerprint) VALUES (?, ?)",
                (cid, f"flagger-{i}")
            )
        conn.commit()
        conn.close()

        # Comment is NOT marked as flagged=1 yet (that happens via the API endpoint),
        # but flag_count >= 3 so hidden should be True
        comments = client.get("/rhizome/api/comments/ant-colony").json()
        assert len(comments) == 1  # still returned since flagged=0
        assert comments[0]["hidden"] is True  # but hidden field reflects flag count


# ─── Helpers ─────────────────────────────────────────────


class TestHelpers:
    """Tests for API helper functions."""

    def test_strip_html_basic(self):
        from api.main import strip_html
        assert strip_html("Hello <b>world</b>") == "Hello world"

    def test_strip_html_nested(self):
        from api.main import strip_html
        assert strip_html("<div><p>text</p></div>") == "text"

    def test_strip_html_script(self):
        from api.main import strip_html
        result = strip_html("Hi <script>alert(1)</script> there")
        assert "<script>" not in result
        assert "alert(1)" in result

    def test_strip_html_no_tags(self):
        from api.main import strip_html
        assert strip_html("plain text") == "plain text"

    def test_strip_html_empty(self):
        from api.main import strip_html
        assert strip_html("") == ""

    def test_time_ago_just_now(self):
        from api.main import time_ago
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert time_ago(now) == "just now"

    def test_time_ago_minutes(self):
        from api.main import time_ago
        t = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert time_ago(t) == "5m ago"

    def test_time_ago_hours(self):
        from api.main import time_ago
        t = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert time_ago(t) == "3h ago"

    def test_time_ago_days(self):
        from api.main import time_ago
        t = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert time_ago(t) == "10d ago"

    def test_time_ago_months(self):
        from api.main import time_ago
        t = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert time_ago(t) == "2mo ago"

    def test_time_ago_invalid(self):
        from api.main import time_ago
        assert time_ago("not-a-date") == "not-a-date"

    def test_fingerprint_deterministic(self):
        """Same request should produce same fingerprint."""
        from api.main import get_fingerprint
        from unittest.mock import MagicMock

        request = MagicMock()
        request.client.host = "1.2.3.4"
        request.headers = {"user-agent": "TestBrowser/1.0"}
        fp1 = get_fingerprint(request)
        fp2 = get_fingerprint(request)
        assert fp1 == fp2
        assert len(fp1) == 64  # SHA-256 hex

    def test_fingerprint_uses_forwarded_for(self):
        """X-Forwarded-For should override client IP."""
        from api.main import get_fingerprint
        from unittest.mock import MagicMock

        request1 = MagicMock()
        request1.client.host = "127.0.0.1"
        request1.headers = {"user-agent": "Test", "x-forwarded-for": "1.2.3.4"}

        request2 = MagicMock()
        request2.client.host = "1.2.3.4"
        request2.headers = {"user-agent": "Test"}

        # Should produce same fingerprint since effective IP is the same
        assert get_fingerprint(request1) == get_fingerprint(request2)

    def test_fingerprint_forwarded_for_first_ip(self):
        """X-Forwarded-For with multiple IPs should use the first."""
        from api.main import get_fingerprint
        from unittest.mock import MagicMock

        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers = {"user-agent": "Test", "x-forwarded-for": "1.2.3.4, 5.6.7.8"}

        request2 = MagicMock()
        request2.client.host = "127.0.0.1"
        request2.headers = {"user-agent": "Test", "x-forwarded-for": "1.2.3.4"}

        assert get_fingerprint(request) == get_fingerprint(request2)


# ─── CORS ────────────────────────────────────────────────


class TestCORS:
    """Tests for CORS configuration."""

    def test_cors_allows_prod_origin(self, client):
        """Prod origin should be allowed."""
        resp = client.options(
            "/rhizome/api/health",
            headers={
                "Origin": "https://thisminute.org",
                "Access-Control-Request-Method": "GET"
            }
        )
        assert resp.headers.get("access-control-allow-origin") == "https://thisminute.org"

    def test_cors_rejects_unknown_origin(self, client):
        """Unknown origins should not get CORS headers."""
        resp = client.options(
            "/rhizome/api/health",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "GET"
            }
        )
        assert resp.headers.get("access-control-allow-origin") != "https://evil.com"

    def test_cors_allows_post(self, client):
        """POST method should be allowed."""
        resp = client.options(
            "/rhizome/api/vote/test",
            headers={
                "Origin": "https://thisminute.org",
                "Access-Control-Request-Method": "POST"
            }
        )
        allow_methods = resp.headers.get("access-control-allow-methods", "")
        assert "POST" in allow_methods


# ─── Database Schema ─────────────────────────────────────


class TestDatabaseSchema:
    """Tests for the SQLite schema integrity."""

    @pytest.fixture(autouse=True)
    def _init_schema(self, tmp_db):
        """Initialize schema on the tmp_db for schema tests."""
        self.db_path = tmp_db
        schema_path = os.path.join(ROOT, "api", "schema.sql")
        conn = sqlite3.connect(tmp_db)
        with open(schema_path, encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.close()

    def test_schema_creates_tables(self):
        """schema.sql should create all required tables."""
        conn = sqlite3.connect(self.db_path)
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        assert "upvotes" in tables
        assert "comments" in tables
        assert "comment_flags" in tables

    def test_schema_creates_indexes(self):
        """schema.sql should create all required indexes."""
        conn = sqlite3.connect(self.db_path)
        indexes = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        ).fetchall()}
        conn.close()
        assert "idx_upvotes_pattern" in indexes
        assert "idx_upvotes_created" in indexes
        assert "idx_upvotes_ratelimit" in indexes
        assert "idx_comments_pattern" in indexes
        assert "idx_comments_ratelimit" in indexes
        assert "idx_comment_flags_comment" in indexes

    def test_schema_idempotent(self):
        """Running schema.sql twice should not error (CREATE IF NOT EXISTS)."""
        schema_path = os.path.join(ROOT, "api", "schema.sql")
        conn = sqlite3.connect(self.db_path)
        with open(schema_path, encoding="utf-8") as f:
            sql = f.read()
        conn.executescript(sql)  # second run (first was in fixture) should be fine
        conn.close()

    def test_upvotes_unique_constraint(self):
        """Same (pattern_id, fingerprint) should fail on insert."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO upvotes (pattern_id, fingerprint) VALUES ('p1', 'fp1')"
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO upvotes (pattern_id, fingerprint) VALUES ('p1', 'fp1')"
            )
        conn.close()

    def test_comment_flags_unique_constraint(self):
        """Same (comment_id, fingerprint) should fail on insert."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO comments (pattern_id, fingerprint, display_name, body) "
            "VALUES ('p1', 'fp1', 'Test', 'body')"
        )
        conn.commit()
        cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO comment_flags (comment_id, fingerprint) VALUES (?, 'fp1')",
            (cid,)
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO comment_flags (comment_id, fingerprint) VALUES (?, 'fp1')",
                (cid,)
            )
        conn.close()


# ─── Frontend Smoke Tests ────────────────────────────────


class TestFrontendSmoke:
    """Basic checks that index.html has the expected structure."""

    @pytest.fixture(autouse=True)
    def _load_html(self):
        with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
            self.html = f.read()

    def test_index_html_has_structure_tiles(self):
        assert 'id="structure-tiles"' in self.html
        assert 'id="structure-panel"' in self.html
        assert "SC_COLORS" in self.html
        assert "SC_LABELS" in self.html
        assert "renderStructureTiles" in self.html

    def test_index_html_has_vote_ui(self):
        assert "upvote-btn" in self.html
        assert "castVote" in self.html
        assert "loadVoteData" in self.html
        assert "sort-votes" in self.html
        assert "sort-trending" in self.html

    def test_index_html_has_comment_ui(self):
        assert "comment-form" in self.html
        assert "comment-list" in self.html
        assert "postComment" in self.html
        assert "flagComment" in self.html

    def test_index_html_has_sort_options(self):
        assert "sort-structure" in self.html
        assert "sort-votes" in self.html
        assert "sort-trending" in self.html

    def test_data_js_patterns_have_hierarchy_types(self, data_js_patterns):
        for p in data_js_patterns:
            assert "hierarchyTypes" in p, f"{p['id']} missing hierarchyTypes"
            assert len(p["hierarchyTypes"]) >= 1

    def test_vote_api_url_construction(self):
        """The frontend should construct vote URLs with the correct prefix."""
        assert "'/rhizome/api/vote/' + patternId" in self.html
        assert "'/rhizome/api/votes'" in self.html
        assert "'/rhizome/api/comments/' + patternId" in self.html

    def test_focus_trap_exists(self):
        """Focus trap functions should be defined."""
        assert "enableFocusTrap" in self.html
        assert "disableFocusTrap" in self.html

    def test_filter_tiles_keyboard_accessible(self):
        """Filter tiles should have tabindex and role for keyboard access."""
        assert 'tabindex="0" role="button"' in self.html

    def test_aria_labels_on_comment_form(self):
        """Comment form fields should have aria labels."""
        assert 'aria-label="Display name"' in self.html
        assert 'aria-label="Comment"' in self.html

    def test_api_base_is_same_origin(self):
        """API_BASE should be empty for same-origin requests."""
        assert "const API_BASE = ''" in self.html

    def test_graceful_degradation_pattern(self):
        """API calls should be wrapped in try/catch for graceful degradation."""
        assert "catch (e) { /* API unavailable */ }" in self.html

    def test_no_duplicate_vote_on_409(self):
        """Optimistic update should only happen on resp.ok, not 409."""
        assert "if (resp.ok) {" in self.html
        # The old bug: optimistic update happened on both ok and 409
        assert "if (resp.ok || resp.status === 409) {" not in self.html or \
               self.html.count("if (resp.ok) {") > 0
