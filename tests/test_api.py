"""Tests for the Rhizome social API."""
import os
import sqlite3
import sys

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


class TestHealth:
    def test_health(self, client):
        resp = client.get("/rhizome/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestVotes:
    def test_get_votes_empty(self, client):
        resp = client.get("/rhizome/api/votes")
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_cast_vote(self, client):
        resp = client.post("/rhizome/api/vote/ant-colony")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

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


class TestComments:
    def test_get_comments_empty(self, client):
        resp = client.get("/rhizome/api/comments/ant-colony")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_post_comment(self, client):
        resp = client.post("/rhizome/api/comments/ant-colony", json={
            "display_name": "Tester",
            "body": "Great pattern!",
            "honeypot": ""
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert resp.json()["id"] > 0

    def test_comment_appears_in_list(self, client):
        client.post("/rhizome/api/comments/ant-colony", json={
            "display_name": "Alice",
            "body": "Used this for swarm robotics",
            "honeypot": ""
        })
        resp = client.get("/rhizome/api/comments/ant-colony")
        comments = resp.json()
        assert len(comments) == 1
        assert comments[0]["display_name"] == "Alice"
        assert comments[0]["body"] == "Used this for swarm robotics"

    def test_honeypot_rejects_bots(self, client):
        resp = client.post("/rhizome/api/comments/ant-colony", json={
            "display_name": "Bot",
            "body": "Spam",
            "honeypot": "gotcha"
        })
        # Returns 200 but doesn't save
        assert resp.status_code == 200
        comments = client.get("/rhizome/api/comments/ant-colony").json()
        assert len(comments) == 0

    def test_empty_body_rejected(self, client):
        resp = client.post("/rhizome/api/comments/ant-colony", json={
            "body": "   ",
            "honeypot": ""
        })
        assert resp.status_code == 400

    def test_html_stripped(self, client):
        client.post("/rhizome/api/comments/ant-colony", json={
            "body": "Hello <script>alert('xss')</script> world",
            "honeypot": ""
        })
        comments = client.get("/rhizome/api/comments/ant-colony").json()
        assert "<script>" not in comments[0]["body"]
        assert "alert" in comments[0]["body"]

    def test_default_anonymous_name(self, client):
        client.post("/rhizome/api/comments/ant-colony", json={
            "body": "Anonymous comment",
            "honeypot": ""
        })
        comments = client.get("/rhizome/api/comments/ant-colony").json()
        assert comments[0]["display_name"] == "Anonymous"


class TestFlagging:
    def test_flag_comment(self, client):
        client.post("/rhizome/api/comments/ant-colony", json={
            "body": "Flaggable comment",
            "honeypot": ""
        })
        comments = client.get("/rhizome/api/comments/ant-colony").json()
        comment_id = comments[0]["id"]

        resp = client.post(f"/rhizome/api/comments/{comment_id}/flag")
        assert resp.status_code == 200
        assert resp.json()["flag_count"] == 1

    def test_duplicate_flag_409(self, client):
        client.post("/rhizome/api/comments/ant-colony", json={
            "body": "Test",
            "honeypot": ""
        })
        comments = client.get("/rhizome/api/comments/ant-colony").json()
        cid = comments[0]["id"]

        client.post(f"/rhizome/api/comments/{cid}/flag")
        resp = client.post(f"/rhizome/api/comments/{cid}/flag")
        assert resp.status_code == 409

    def test_flag_nonexistent_comment(self, client):
        resp = client.post("/rhizome/api/comments/99999/flag")
        assert resp.status_code == 404


class TestFrontendSmoke:
    """Basic checks that index.html has the expected structure."""

    def test_index_html_has_structure_tiles(self):
        with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
            html = f.read()
        assert 'id="structure-tiles"' in html
        assert 'id="structure-panel"' in html
        assert "SC_COLORS" in html
        assert "SC_LABELS" in html
        assert "renderStructureTiles" in html

    def test_index_html_has_vote_ui(self):
        with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
            html = f.read()
        assert "upvote-btn" in html
        assert "castVote" in html
        assert "loadVoteData" in html
        assert "sort-votes" in html
        assert "sort-trending" in html

    def test_index_html_has_comment_ui(self):
        with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
            html = f.read()
        assert "comment-form" in html
        assert "comment-list" in html
        assert "postComment" in html
        assert "flagComment" in html

    def test_index_html_has_sort_options(self):
        with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
            html = f.read()
        assert "sort-structure" in html
        assert "sort-votes" in html
        assert "sort-trending" in html

    def test_data_js_patterns_have_hierarchy_types(self, data_js_patterns):
        for p in data_js_patterns:
            assert "hierarchyTypes" in p, f"{p['id']} missing hierarchyTypes"
            assert len(p["hierarchyTypes"]) >= 1
