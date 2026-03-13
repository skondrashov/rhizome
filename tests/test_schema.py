"""Tests for schema.json and pattern data validity."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import VALID_HIERARCHY_TYPES, VALID_CATEGORIES


def test_schema_has_hierarchy_types(schema):
    """Schema should define hierarchyTypes field."""
    props = schema["properties"]
    assert "hierarchyTypes" in props
    assert props["hierarchyTypes"]["type"] == "array"
    enum_vals = set(props["hierarchyTypes"]["items"]["enum"])
    assert enum_vals == VALID_HIERARCHY_TYPES


def test_hierarchy_types_required(schema):
    """hierarchyTypes should be in the required list."""
    assert "hierarchyTypes" in schema["required"]


def test_all_patterns_have_valid_hierarchy_types(all_patterns):
    """Every pattern should have at least one valid hierarchy type."""
    for p in all_patterns:
        pid = p.get("id", "?")
        ht = p.get("hierarchyTypes")
        assert ht, f"{pid} missing hierarchyTypes"
        assert isinstance(ht, list), f"{pid} hierarchyTypes is not a list"
        assert len(ht) >= 1, f"{pid} has empty hierarchyTypes"
        for t in ht:
            assert t in VALID_HIERARCHY_TYPES, f"{pid} has invalid type '{t}'"


def test_all_patterns_have_valid_category(all_patterns):
    """Every pattern should have a valid category."""
    for p in all_patterns:
        assert p.get("category") in VALID_CATEGORIES, \
            f"{p.get('id', '?')} has invalid category '{p.get('category')}'"


def test_all_patterns_have_agents(all_patterns):
    """Every pattern should have at least one agent."""
    for p in all_patterns:
        agents = p.get("agents", [])
        assert len(agents) >= 1, f"{p.get('id', '?')} has no agents"
        for a in agents:
            assert "role" in a, f"{p.get('id')}: agent missing 'role'"
            assert "name" in a, f"{p.get('id')}: agent missing 'name'"


def test_all_patterns_have_forums(all_patterns):
    """Every pattern should have at least one forum."""
    for p in all_patterns:
        forums = p.get("forums", [])
        assert len(forums) >= 1, f"{p.get('id', '?')} has no forums"
        for f in forums:
            assert "name" in f, f"{p.get('id')}: forum missing 'name'"
            assert "type" in f, f"{p.get('id')}: forum missing 'type'"


def test_pattern_count(all_patterns):
    """Should have exactly 207 patterns."""
    ids = [p["id"] for p in all_patterns if "id" in p]
    unique_ids = set(ids)
    assert len(unique_ids) == 207, f"Expected 207, got {len(unique_ids)} unique patterns"
