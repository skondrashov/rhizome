"""
One-time script to classify all 207 patterns by hierarchy type.

Scores each pattern against 8 hierarchy types using weighted signals:
  - Tag matching (weight 3)
  - Forum type matching (weight 2)
  - Agent structure heuristics (weight 2)
  - Description/name keyword matching (weight 1)

Assigns primary type (highest score) + secondary types (score >= 40% of primary).
Injects `hierarchyTypes` array into each source JSON file.

Usage:
  python classify_hierarchy.py              # Classify and inject
  python classify_hierarchy.py --report     # Print report only, don't modify files
  python classify_hierarchy.py --overrides overrides.json  # Apply manual overrides
"""

import json
import glob
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import VALID_HIERARCHY_TYPES

HIERARCHY_TYPES = list(VALID_HIERARCHY_TYPES)

# ─── Signal Definitions ──────────────────────────────────────

TAG_SIGNALS = {
    "adversarial": ["adversarial", "competitive", "red-team", "blue-team", "debate",
                     "tournament", "versus", "opposition", "contest", "duel",
                     "challenge", "rivalry", "sparring", "war-game", "wargame"],
    "chain-of-command": ["hierarchical", "strict", "top-down", "chain-of-command",
                          "tree", "military", "rank", "authority", "command",
                          "subordinate", "superior", "directive", "chain"],
    "orchestrated": ["orchestrator", "hub-and-spoke", "central", "coordinator",
                      "conductor", "master", "controller", "supervisor",
                      "centralized", "managed", "directed", "delegator"],
    "swarm": ["swarm", "stigmergy", "emergent", "decentralized", "pheromone",
              "ant", "flock", "hive", "colony", "self-organizing", "collective",
              "particle", "bee", "insect"],
    "mesh": ["peer-to-peer", "mesh", "gossip", "flat", "p2p", "network",
             "democratic", "equal", "lateral", "improvisation", "jam",
             "ensemble", "collaborative"],
    "pipeline": ["pipeline", "sequential", "chain", "stages", "relay",
                  "assembly", "waterfall", "linear", "handoff", "pass",
                  "step-by-step", "phased", "serial"],
    "consensus": ["consensus", "voting", "quorum", "deliberation", "jury",
                   "democratic", "collective-decision", "agreement", "council",
                   "committee", "senate", "parliament", "assembly",
                   "round-robin", "consent"],
    "federated": ["federated", "federation", "autonomous", "circles",
                   "distributed-authority", "holacracy", "subsidiary",
                   "chapter", "guild", "tribe", "cell", "compartment",
                   "nested", "sub-unit", "satellite", "regional"]
}

FORUM_TYPE_SIGNALS = {
    "adversarial": ["decision"],  # adversarial patterns often have judge decisions
    "chain-of-command": ["top-down", "bottom-up"],
    "orchestrated": ["broadcast", "per-agent"],
    "swarm": ["pub-sub", "broadcast"],
    "mesh": ["peer-to-peer", "round-robin"],
    "pipeline": ["queue", "log"],
    "consensus": ["decision", "round-robin", "threaded", "advisory"],
    "federated": ["peer-to-peer", "threaded"]
}

DESCRIPTION_KEYWORDS = {
    "adversarial": ["compete", "opponent", "versus", "red team", "blue team",
                     "debate", "challenge", "contest", "adversar", "tournament",
                     "judge", "winner", "loser", "attack", "defend against",
                     "sparring", "war game"],
    "chain-of-command": ["hierarchy", "chain of command", "orders flow",
                          "reports to", "subordinate", "superior officer",
                          "authority", "rank", "command structure",
                          "top-down", "bottom-up reporting", "military"],
    "orchestrated": ["orchestrat", "central coordinator", "hub",
                      "conductor", "dispatche", "assigns tasks",
                      "central", "oversees all", "delegates",
                      "master.*worker", "spawns.*agents"],
    "swarm": ["swarm", "emergent", "stigmergy", "pheromone",
              "no central", "decentralized", "self-organiz",
              "indirect communication", "environment",
              "ant colon", "collective behavior", "flock"],
    "mesh": ["peer-to-peer", "each.*talks.*to", "direct connection",
             "gossip protocol", "lateral", "flat structure",
             "improvise", "jam session", "ensemble",
             "every.*communicates.*every"],
    "pipeline": ["pipeline", "sequential", "stage", "assembly line",
                  "output.*feeds.*input", "next step", "relay",
                  "chain of.*processing", "waterfall", "pass.*along",
                  "one.*then.*next"],
    "consensus": ["consensus", "vote", "deliberat", "jury", "quorum",
                   "collective decision", "agreement", "all agree",
                   "democratic", "equal voice", "parliament",
                   "council.*decides"],
    "federated": ["federat", "autonomous.*group", "local authority",
                   "circles", "holacracy", "subsidiary",
                   "chapter", "guild", "nested.*team",
                   "independent.*unit", "bridge.*between",
                   "liaison", "sub-group", "regional"]
}


def score_pattern(pattern):
    """Score a pattern against all 8 hierarchy types."""
    scores = {t: 0.0 for t in HIERARCHY_TYPES}
    tags = [t.lower() for t in (pattern.get("tags") or [])]
    name = (pattern.get("name") or "").lower()
    desc = (pattern.get("description") or "").lower()
    summary = (pattern.get("summary") or "").lower()
    full_text = f"{name} {desc} {summary}"
    forums = pattern.get("forums") or []
    forum_types = [f.get("type", "").lower() for f in forums]
    agents = pattern.get("agents") or []
    category = (pattern.get("category") or "").lower()

    # 1. Tag matching (weight 3)
    for htype, signals in TAG_SIGNALS.items():
        for signal in signals:
            if signal in tags:
                scores[htype] += 3

    # 2. Forum type matching (weight 2)
    for htype, ftypes in FORUM_TYPE_SIGNALS.items():
        for ft in ftypes:
            if ft in forum_types:
                scores[htype] += 2

    # 3. Description/name keyword matching (weight 1.5)
    for htype, keywords in DESCRIPTION_KEYWORDS.items():
        for kw in keywords:
            if re.search(kw, full_text):
                scores[htype] += 1.5

    # 4. Agent structure heuristics (weight 2)
    agent_count = len(agents)
    total_instances = sum(a.get("count", 1) for a in agents)
    agent_roles = [a.get("role", "").lower() for a in agents]
    agent_names = [a.get("name", "").lower() for a in agents]
    agent_text = " ".join(agent_roles + agent_names)

    # Chain-of-command: multiple layers with increasing counts
    counts = [a.get("count", 1) for a in agents]
    if len(counts) >= 3 and all(a < b for a, b in zip(counts, counts[1:])):
        scores["chain-of-command"] += 2

    # Orchestrated: has an orchestrator/conductor/coordinator role
    orch_roles = ["orchestrator", "conductor", "coordinator", "master",
                  "controller", "dispatcher", "supervisor", "manager"]
    if any(r in agent_text for r in orch_roles):
        scores["orchestrated"] += 2

    # Swarm: many identical agents with ephemeral memory
    ephemeral_agents = [a for a in agents if a.get("memory") == "ephemeral"]
    high_count_agents = [a for a in agents if a.get("count", 1) >= 5]
    if len(high_count_agents) >= 1 and len(ephemeral_agents) >= 1:
        scores["swarm"] += 2

    # Pipeline: agents with sequential-sounding roles
    pipeline_roles = ["stage", "step", "phase", "processor", "transformer",
                      "filter", "validator", "reviewer"]
    if any(r in agent_text for r in pipeline_roles):
        scores["pipeline"] += 1.5

    # Adversarial: has judge/critic + competing agents
    adversarial_roles = ["judge", "critic", "evaluator", "referee",
                          "challenger", "defender", "attacker",
                          "red", "blue", "opponent"]
    if any(r in agent_text for r in adversarial_roles):
        scores["adversarial"] += 2

    # Consensus: equal agents with decision forums
    if "decision" in forum_types and total_instances <= agent_count * 2:
        scores["consensus"] += 1.5

    # Federated: has lead-link / rep-link / liaison / bridge roles
    fed_roles = ["lead-link", "rep-link", "liaison", "ambassador",
                  "bridge", "delegate", "representative"]
    if any(r in agent_text for r in fed_roles):
        scores["federated"] += 2

    # Mesh: peer-to-peer forums + small flat teams
    if "peer-to-peer" in forum_types and total_instances <= 10:
        scores["mesh"] += 1.5

    # 5. Category-based hints (weight 1)
    if "military" in category:
        scores["chain-of-command"] += 1
    if "nature" in category:
        scores["swarm"] += 1
    if "creative" in category:
        scores["mesh"] += 0.5
    if "network" in category:
        scores["mesh"] += 0.5
        scores["swarm"] += 0.5

    return scores


def classify(pattern, overrides=None):
    """Return (primary_type, secondary_types, confidence, scores) for a pattern."""
    pid = pattern.get("id", "")

    # Check overrides first
    if overrides and pid in overrides:
        ov = overrides[pid]
        if isinstance(ov, list):
            return ov[0], ov[1:], 1.0, {}
        elif isinstance(ov, str):
            return ov, [], 1.0, {}

    scores = score_pattern(pattern)
    ranked = sorted(scores.items(), key=lambda x: -x[1])

    if ranked[0][1] == 0:
        # No signal at all — default to orchestrated
        return "orchestrated", [], 0.0, scores

    primary = ranked[0][0]
    primary_score = ranked[0][1]

    # Secondary: anything with score >= 40% of primary and > 0
    threshold = primary_score * 0.4
    secondary = [t for t, s in ranked[1:] if s >= threshold and s > 0]

    # Confidence: based on gap between primary and second
    if len(ranked) > 1 and ranked[1][1] > 0:
        confidence = (primary_score - ranked[1][1]) / primary_score
    else:
        confidence = 1.0

    return primary, secondary, round(confidence, 2), scores


def main():
    report_only = "--report" in sys.argv
    overrides_file = None
    if "--overrides" in sys.argv:
        idx = sys.argv.index("--overrides")
        if idx + 1 < len(sys.argv):
            overrides_file = sys.argv[idx + 1]

    overrides = {}
    if overrides_file and os.path.exists(overrides_file):
        with open(overrides_file, encoding="utf-8") as f:
            overrides = json.load(f)
        print(f"Loaded {len(overrides)} overrides from {overrides_file}")

    structure_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "structures")
    files = sorted(glob.glob(os.path.join(structure_dir, "*.json")))

    all_patterns = []
    file_map = {}  # pattern_id -> (file_path, index_in_file)

    for fpath in files:
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
        items = data if isinstance(data, list) else [data]
        for i, item in enumerate(items):
            pid = item.get("id")
            if pid:
                all_patterns.append(item)
                file_map[pid] = (fpath, i, isinstance(data, list))

    print(f"Loaded {len(all_patterns)} patterns from {len(files)} files\n")

    # Classify all
    results = []
    type_counts = {t: 0 for t in HIERARCHY_TYPES}
    low_confidence = []

    for pattern in all_patterns:
        primary, secondary, confidence, scores = classify(pattern, overrides)
        hierarchy_types = [primary] + secondary
        results.append({
            "id": pattern["id"],
            "name": pattern.get("name", ""),
            "primary": primary,
            "secondary": secondary,
            "confidence": confidence,
            "hierarchy_types": hierarchy_types
        })
        type_counts[primary] += 1
        if confidence < 0.2:
            low_confidence.append(pattern["id"])

    # Report
    print(f"{'ID':<45} {'Primary':<20} {'Secondary':<35} {'Conf':>5}")
    print("-" * 110)
    for r in results:
        sec = ", ".join(r["secondary"]) if r["secondary"] else "-"
        conf_marker = " !!" if r["confidence"] < 0.2 else ""
        print(f"{r['id']:<45} {r['primary']:<20} {sec:<35} {r['confidence']:>5}{conf_marker}")

    print(f"\n{'-' * 50}")
    print("Type distribution:")
    for t in sorted(type_counts, key=lambda x: -type_counts[x]):
        bar = "#" * type_counts[t]
        print(f"  {t:<20} {type_counts[t]:>3}  {bar}")

    print(f"\nLow confidence ({len(low_confidence)}): {', '.join(low_confidence[:10])}")
    if len(low_confidence) > 10:
        print(f"  ... and {len(low_confidence) - 10} more")

    if report_only:
        print("\n(Report only mode — no files modified)")
        return

    # Inject into source files
    print("\nInjecting hierarchyTypes into source files...")
    result_map = {r["id"]: r["hierarchy_types"] for r in results}
    modified_files = set()

    for fpath in files:
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)

        is_list = isinstance(data, list)
        items = data if is_list else [data]
        changed = False

        for item in items:
            pid = item.get("id")
            if pid and pid in result_map:
                item["hierarchyTypes"] = result_map[pid]
                changed = True

        if changed:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(data if is_list else items[0], f, indent=2, ensure_ascii=False)
                f.write("\n")
            modified_files.add(os.path.basename(fpath))

    print(f"Modified {len(modified_files)} files: {', '.join(sorted(modified_files))}")
    print("Done! Run `python build.py` to rebuild data.js")


if __name__ == "__main__":
    main()
