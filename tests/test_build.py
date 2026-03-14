"""Tests for build.py — data aggregation and validation."""
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_build_runs_successfully():
    """build.py should exit 0 and produce data.js."""
    result = subprocess.run(
        [sys.executable, os.path.join(ROOT, "build.py")],
        capture_output=True, text=True, cwd=ROOT
    )
    assert result.returncode == 0, f"build.py failed:\n{result.stderr}"
    assert "Built data.js with" in result.stdout


def test_data_js_is_valid_json(data_js_patterns):
    """data.js should contain a valid JSON array."""
    assert isinstance(data_js_patterns, list)
    assert len(data_js_patterns) >= 200


def test_no_duplicate_ids(data_js_patterns):
    """All pattern IDs should be unique."""
    ids = [p["id"] for p in data_js_patterns]
    assert len(ids) == len(set(ids)), f"Duplicate IDs: {[x for x in ids if ids.count(x) > 1]}"


def test_sorted_by_category_then_name(data_js_patterns):
    """Patterns should be sorted by (category, name)."""
    keys = [(p.get("category", ""), p.get("name", "")) for p in data_js_patterns]
    assert keys == sorted(keys)


def test_all_have_required_fields(data_js_patterns):
    """Every pattern should have the required schema fields."""
    required = ["id", "name", "category", "hierarchyTypes", "tags",
                "summary", "description", "agents", "forums"]
    for p in data_js_patterns:
        for field in required:
            assert field in p, f"Pattern {p.get('id', '?')} missing '{field}'"


def test_all_have_structural_class(data_js_patterns, data_js_structural_classes):
    """Every pattern should have a structuralClass field."""
    if not data_js_structural_classes:
        pytest.skip("structural-classes.json not available")
    for p in data_js_patterns:
        assert "structuralClass" in p, f"Pattern {p['id']} missing 'structuralClass'"
        assert p["structuralClass"], f"Pattern {p['id']} has empty structuralClass"


def test_structural_classes_written_to_data_js(data_js_structural_classes):
    """data.js should contain window.STRUCTURAL_CLASSES with class definitions."""
    if not data_js_structural_classes:
        pytest.skip("structural-classes.json not available")
    assert isinstance(data_js_structural_classes, dict)
    assert len(data_js_structural_classes) >= 12
    for key, val in data_js_structural_classes.items():
        assert "label" in val, f"Structural class '{key}' missing 'label'"
        assert "description" in val, f"Structural class '{key}' missing 'description'"
        assert "color" in val, f"Structural class '{key}' missing 'color'"


def test_structural_class_values_are_valid(data_js_patterns, data_js_structural_classes):
    """Every pattern's structuralClass should reference a defined class."""
    if not data_js_structural_classes:
        pytest.skip("structural-classes.json not available")
    valid_classes = set(data_js_structural_classes.keys())
    for p in data_js_patterns:
        sc = p.get("structuralClass")
        if sc:
            assert sc in valid_classes, f"Pattern {p['id']} has unknown structuralClass '{sc}'"
