"""Combines all structure JSON files into a single data.js for the UI."""
import json
import glob
import os

structures = []
seen_ids = set()
structure_dir = os.path.join(os.path.dirname(__file__), 'structures')

# Also read from agent-forge's exports (agent-forge owns deployed system data)
agent_forge_export = os.path.expanduser('~/agent-forge/exports/rhizome.json')

source_files = sorted(glob.glob(os.path.join(structure_dir, '*.json')))
if os.path.exists(agent_forge_export):
    source_files.append(agent_forge_export)

for fpath in source_files:
    try:
        with open(fpath, encoding='utf-8') as f:
            data = json.load(f)
        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get('id') and item['id'] not in seen_ids:
                seen_ids.add(item['id'])
                structures.append(item)
            elif not item.get('id'):
                print(f"  WARNING: structure in {os.path.basename(fpath)} missing 'id' field, skipping")
    except Exception as e:
        print(f"  ERROR reading {os.path.basename(fpath)}: {e}")

# Read structural classes from agent-forge (agent-forge owns this data)
structural_classes_path = os.path.expanduser('~/agent-forge/exports/structural-classes.json')
structural_classes = {}
structural_mappings = {}
if os.path.exists(structural_classes_path):
    with open(structural_classes_path, encoding='utf-8') as f:
        sc_data = json.load(f)
    structural_classes = sc_data.get('classes', {})
    structural_mappings = sc_data.get('mappings', {})
    print(f"Loaded {len(structural_mappings)} structural class mappings")
else:
    print("  WARNING: structural-classes.json not found")

# Merge structuralClass into each pattern
sc_assigned = 0
sc_missing = []
for s in structures:
    pid = s.get('id', '')
    if pid in structural_mappings:
        s['structuralClass'] = structural_mappings[pid]
        sc_assigned += 1
    else:
        sc_missing.append(pid)

if sc_missing:
    print(f"  WARNING: {len(sc_missing)} patterns missing structuralClass: {', '.join(sc_missing[:5])}")
else:
    print(f"All {sc_assigned} patterns have structuralClass")

# Sort by category then name
structures.sort(key=lambda s: (s.get('category', ''), s.get('name', '')))

out_path = os.path.join(os.path.dirname(__file__), 'data.js')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('window.STRUCTURES = ')
    json.dump(structures, f, indent=2, ensure_ascii=False)
    f.write(';\n')

    # Write structural classes data for the UI
    if structural_classes:
        f.write('\nwindow.STRUCTURAL_CLASSES = ')
        json.dump(structural_classes, f, indent=2, ensure_ascii=False)
        f.write(';\n')

print(f"\nBuilt data.js with {len(structures)} structures from {len(glob.glob(os.path.join(structure_dir, '*.json')))} files")


def count_by(items, key, default='Uncategorized'):
    """Count items grouped by a field value, sorted by frequency descending."""
    counts = {}
    for item in items:
        val = item.get(key, default)
        if val:
            counts[val] = counts.get(val, 0) + 1
    return sorted(counts.items(), key=lambda x: -x[1])


def print_breakdown(title, counted, label_fn=None):
    """Print a named frequency breakdown."""
    print(f"\n{title}:")
    for key, count in counted:
        label = label_fn(key) if label_fn else key
        print(f"  {label}: {count}")


print_breakdown("Category breakdown",
                count_by(structures, 'category'))

# Hierarchy type validation and breakdown
VALID_TYPES = {"adversarial", "chain-of-command", "orchestrated", "swarm",
               "mesh", "pipeline", "consensus", "federated"}
missing_ht = []
htypes = {}
for s in structures:
    ht = s.get('hierarchyTypes')
    if not ht:
        missing_ht.append(s.get('id', '?'))
    else:
        primary = ht[0]
        htypes[primary] = htypes.get(primary, 0) + 1
        for t in ht:
            if t not in VALID_TYPES:
                print(f"  WARNING: {s.get('id')} has invalid hierarchy type '{t}'")

if missing_ht:
    print(f"\n  WARNING: {len(missing_ht)} patterns missing hierarchyTypes: {', '.join(missing_ht[:5])}")
else:
    print(f"\nAll {len(structures)} patterns have hierarchyTypes")

print_breakdown("Hierarchy type breakdown (primary)",
                sorted(htypes.items(), key=lambda x: -x[1]))

if structural_classes:
    print_breakdown("Structural class breakdown",
                    count_by(structures, 'structuralClass'),
                    label_fn=lambda c: structural_classes.get(c, {}).get('label', c))
