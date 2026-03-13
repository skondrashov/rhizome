"""Shared fixtures for Rhizome tests."""
import json
import glob
import os
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRUCTURES_DIR = os.path.join(ROOT, "structures")


@pytest.fixture
def all_patterns():
    """Load all patterns from structure JSON files."""
    patterns = []
    for fpath in sorted(glob.glob(os.path.join(STRUCTURES_DIR, "*.json"))):
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
        items = data if isinstance(data, list) else [data]
        patterns.extend(items)
    return patterns


@pytest.fixture
def schema():
    """Load the JSON schema."""
    with open(os.path.join(ROOT, "schema.json"), encoding="utf-8") as f:
        return json.load(f)


def _parse_data_js():
    """Parse data.js and return (patterns, structural_classes)."""
    data_js = os.path.join(ROOT, "data.js")
    with open(data_js, encoding="utf-8") as f:
        content = f.read()
    # Split on window.STRUCTURAL_CLASSES assignment
    parts = content.split("\nwindow.STRUCTURAL_CLASSES = ")
    structures_json = parts[0].replace("window.STRUCTURES = ", "").rstrip(";\n")
    patterns = json.loads(structures_json)
    sc = {}
    if len(parts) > 1:
        sc_json = parts[1].rstrip(";\n")
        sc = json.loads(sc_json)
    return patterns, sc


@pytest.fixture
def data_js_patterns():
    """Load patterns from the built data.js."""
    patterns, _ = _parse_data_js()
    return patterns


@pytest.fixture
def data_js_structural_classes():
    """Load structural classes from the built data.js."""
    _, sc = _parse_data_js()
    return sc


@pytest.fixture
def tmp_db():
    """Create a temporary SQLite database for API testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)
