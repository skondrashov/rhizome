"""Shared constants and utilities for the Rhizome project."""
import json
import glob
import os

VALID_HIERARCHY_TYPES = frozenset({
    "adversarial", "chain-of-command", "orchestrated", "swarm",
    "mesh", "pipeline", "consensus", "federated"
})

VALID_CATEGORIES = frozenset({
    "Military & Defense", "Corporate & Business", "Government & Political",
    "Academic & Research", "Creative & Arts", "Technology & Engineering",
    "Medical & Emergency", "Historical & Traditional", "Nature-Inspired",
    "Network Topologies", "Agile & Software", "Social & Community",
    "Novel & Experimental", "Religious & Spiritual", "Legal & Judicial",
    "Education & Training", "Intelligence & Espionage", "Maritime & Aviation",
    "Sports & Competition", "Media & Communications"
})


def load_patterns_from_dir(structure_dir):
    """Load all patterns from JSON files in a directory, normalizing list/object format."""
    patterns = []
    for fpath in sorted(glob.glob(os.path.join(structure_dir, "*.json"))):
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
        items = data if isinstance(data, list) else [data]
        patterns.extend(items)
    return patterns
