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


def load_patterns_from_dir(structure_dir, dedup=True, warn=False):
    """Load all patterns from JSON files in a directory, normalizing list/object format.

    Args:
        structure_dir: Path to directory containing JSON files.
        dedup: If True, skip patterns with duplicate IDs (first wins).
        warn: If True, print warnings for missing IDs and read errors.

    Returns:
        (patterns, file_count) tuple.
    """
    patterns = []
    seen_ids = set()
    file_count = 0
    for fpath in sorted(glob.glob(os.path.join(structure_dir, "*.json"))):
        file_count += 1
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            items = data if isinstance(data, list) else [data]
            for item in items:
                pid = item.get("id")
                if not pid:
                    if warn:
                        print(f"  WARNING: structure in {os.path.basename(fpath)} missing 'id' field, skipping")
                    continue
                if dedup and pid in seen_ids:
                    if warn:
                        print(f"  WARNING: duplicate id '{pid}' in {os.path.basename(fpath)}, skipping")
                    continue
                seen_ids.add(pid)
                patterns.append(item)
        except (json.JSONDecodeError, OSError) as e:
            if warn:
                print(f"  ERROR reading {os.path.basename(fpath)}: {e}")
    return patterns, file_count
