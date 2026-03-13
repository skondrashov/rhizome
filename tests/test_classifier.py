"""Tests for classify_hierarchy.py — hierarchy type classification."""
import os
import sys
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from classify_hierarchy import score_pattern, classify, HIERARCHY_TYPES


def test_score_returns_all_types():
    """score_pattern should return scores for all 8 types."""
    pattern = {
        "id": "test",
        "name": "Test Pattern",
        "tags": ["hierarchical"],
        "description": "A test pattern",
        "summary": "Test",
        "forums": [],
        "agents": []
    }
    scores = score_pattern(pattern)
    assert set(scores.keys()) == set(HIERARCHY_TYPES)


def test_military_chain_of_command():
    """A clearly hierarchical military pattern should classify as chain-of-command."""
    pattern = {
        "id": "test-military",
        "name": "Military Chain of Command",
        "tags": ["hierarchical", "strict", "top-down", "chain-of-command", "tree", "military"],
        "description": "Strict tree hierarchy where orders flow down and situation reports flow up",
        "summary": "Strict tree hierarchy",
        "category": "Military & Defense",
        "forums": [
            {"name": "Orders", "type": "top-down"},
            {"name": "Reports", "type": "bottom-up"}
        ],
        "agents": [
            {"role": "commander", "name": "Commander", "description": "Sets strategy", "count": 1},
            {"role": "officer", "name": "Officer", "description": "Leads", "count": 4},
            {"role": "soldier", "name": "Soldier", "description": "Executes", "count": 16}
        ]
    }
    primary, secondary, confidence, _ = classify(pattern)
    assert primary == "chain-of-command"


def test_ant_colony_swarm():
    """An ant colony pattern should classify as swarm."""
    pattern = {
        "id": "test-ants",
        "name": "Ant Colony",
        "tags": ["swarm", "stigmergy", "emergent", "decentralized", "pheromone"],
        "description": "Decentralized swarm where agents communicate indirectly through environmental signals",
        "summary": "Decentralized swarm intelligence",
        "category": "Nature-Inspired",
        "forums": [
            {"name": "Pheromone Map", "type": "broadcast"},
            {"name": "Resources", "type": "pub-sub"}
        ],
        "agents": [
            {"role": "scout", "name": "Scout", "description": "Explores", "memory": "ephemeral", "count": 10},
            {"role": "worker", "name": "Worker", "description": "Works", "memory": "ephemeral", "count": 40}
        ]
    }
    primary, secondary, confidence, _ = classify(pattern)
    assert primary == "swarm"


def test_jazz_ensemble_mesh():
    """A jazz ensemble should classify as mesh."""
    pattern = {
        "id": "test-jazz",
        "name": "Jazz Ensemble",
        "tags": ["improvisation", "peer-to-peer", "responsive", "creative", "flat"],
        "description": "Small group of peers improvising together",
        "summary": "Peer improvisation",
        "category": "Creative & Arts",
        "forums": [
            {"name": "Groove", "type": "broadcast"},
            {"name": "Nod", "type": "peer-to-peer"}
        ],
        "agents": [
            {"role": "rhythm", "name": "Rhythm", "description": "Foundation"},
            {"role": "soloist", "name": "Soloist", "description": "Melody"}
        ]
    }
    primary, secondary, confidence, _ = classify(pattern)
    assert primary == "mesh"


def test_overrides_take_precedence():
    """Manual overrides should override automatic classification."""
    pattern = {
        "id": "test-override",
        "name": "Test",
        "tags": ["swarm"],
        "description": "Swarm-like",
        "summary": "Test",
        "forums": [],
        "agents": []
    }
    overrides = {"test-override": ["pipeline", "mesh"]}
    primary, secondary, confidence, _ = classify(pattern, overrides)
    assert primary == "pipeline"
    assert secondary == ["mesh"]
    assert confidence == 1.0


def test_classifier_report_mode():
    """classify_hierarchy.py --report should exit 0 without modifying files."""
    result = subprocess.run(
        [sys.executable, os.path.join(ROOT, "classify_hierarchy.py"), "--report"],
        capture_output=True, text=True, cwd=ROOT
    )
    assert result.returncode == 0
    assert "Report only mode" in result.stdout
