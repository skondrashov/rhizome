# Rhizome

If told to go, start, or begin — you are the **steward**. See `agents/steward.md`.

Browsable taxonomy of 200 agent orchestration patterns. Live at https://thisminute.org/rhizome.

## Forge Notes

Observations from operating agent systems across 6 projects (thisminute, mainmenu, rhizome, ops, sts2, agent-forge). These are field notes, not theory — maintained by the forge that manages all of them.

- **Stigmergy has a hard ceiling.** Forum-based coordination (agents read/write a shared file) is the most natural pattern that emerges. But it fails via unbounded growth — one project's forum went from 51 to 621 lines in a single session, another hit 904 across 7 cycles. Every shared-context pattern needs a maintenance agent. The pattern and its maintenance cost are inseparable.
- **Fitness beats compliance.** A game mod project is effective at Structured+ using checkpoints and a section index instead of memory/ and forum. A catalog (this project) is effective with one steward. A news platform needs 10 agents because it has 10 genuinely different concerns. The right question is "is this working?" not "does this match a checklist?"
- **Premature structure costs more than no structure.** This project proved it. A single steward handled bug fixes, accessibility, data quality, and maintained meaningful memory without ever needing a role split. Scaffolding 5 roles on day one would have been empty ceremony.
- **Memory is the lagging indicator.** Projects adopt role files and protocols quickly. Memory files are the last thing used consistently. One project has 10 agents but only 3 memory files — 7 agents re-learn things every session.
- **Reflection loops need a consumer.** Asking agents to evaluate their context at shutdown produces great signal. But without a keeper to process it, reflections pile up and nothing changes. The loop is only as good as its feedback processing.
- **Domain adaptation > pattern conformance.** The most effective agent systems adapted conventions to fit their domain (30-second build-test-fix loops, single-page catalogs, async news pipelines) rather than conforming to a template. The forge's job is recognizing that, not flattening it.

## Stack

- **Frontend**: Single `index.html` (dark-themed SPA, Mermaid.js for diagrams via CDN)
- **Data**: 13 JSON files in `structures/` → `build.py` aggregates them into `data.js`
- **API**: FastAPI + SQLite in `api/` — upvotes, comments, trending (optional; site degrades gracefully without it)
- **Deploy**: `deploy.sh` runs build, scp's to Google Cloud, optionally deploys API
- **Tests**: pytest suite in `tests/` — API endpoints, build pipeline, classifier, schema validation (92 tests)
- No package manager.

## Commands

- **Build**: `python build.py` — deduplicates, validates, sorts, outputs `data.js`
- **Deploy**: `bash deploy.sh` — build + scp + verify (add `--api` to deploy API too)
- **Classify**: `python classify_hierarchy.py` — auto-classify patterns by hierarchy type
- **Init DB**: `python api/init_db.py` — create SQLite database for social features
- **Run API locally**: `uvicorn api.main:app --host 0.0.0.0 --port 8100`
- **Test**: `python -m pytest tests/ -v` — run all 92 tests
- **Local dev**: open `index.html` in a browser (file:// works; social features need API)

## Key files

| File | What it does |
|------|-------------|
| `index.html` | Entire frontend — filtering, hierarchy types, votes, comments |
| `data.js` | Generated. 200 patterns as `window.STRUCTURES` array |
| `build.py` | Aggregates `structures/*.json`, merges structural classes, dedupes by ID, validates, sorts |
| `structural-classes.json` | 15 structural classes with mappings for all 200 patterns |
| `schema.json` | JSON Schema (draft-07) defining pattern shape including `hierarchyTypes` |
| `deploy.sh` | Build + scp to GCloud + HTTP verify + optional API deploy |
| `structures/` | 13 source JSON files, ~14K lines total |
| `classify_hierarchy.py` | One-time script to auto-classify patterns by structural topology |
| `overrides.json` | Manual hierarchy type overrides for the classifier |
| `api/main.py` | FastAPI app — upvotes, comments, trending (~200 lines) |
| `api/schema.sql` | SQLite schema for upvotes, comments, flags |
| `api/init_db.py` | Database initialization script |
| `api/requirements.txt` | Python dependencies: fastapi, uvicorn |

## Pattern schema (abbreviated)

Each pattern has: `id`, `name`, `category` (20 categories), `hierarchyTypes` (array of structural topologies), `tags`, `summary`, `description`, `realWorldExample`, `whenToUse`, `strengths[]`, `weaknesses[]`, `agents[]` (role/name/description/memory/count), `forums[]` (name/type/participants), `memoryArchitecture`, `diagram` (Mermaid).

## Hierarchy Types (8)

Structural topologies orthogonal to domain categories. Each pattern has 1+ types (first is primary):

| Type | Description |
|------|-------------|
| `adversarial` | Competing agents, judge picks winner. Red-team/blue-team, debates, tournaments. |
| `chain-of-command` | Strict tree hierarchy. Authority top-down, reporting bottom-up. |
| `orchestrated` | Central orchestrator with full visibility. Hub-and-spoke. |
| `swarm` | Decentralized, indirect coordination via environment. Emergent behavior. |
| `mesh` | Peer-to-peer direct connections without central coordination. |
| `pipeline` | Sequential stages — output feeds into next agent. |
| `consensus` | Agents deliberate as equals to reach collective agreement. |
| `federated` | Autonomous subgroups with local authority, connected by bridges. |

## API Endpoints

All under `/rhizome/api/`. Nginx proxies to FastAPI on port 8100.

| Method | Path | What |
|--------|------|------|
| `GET` | `/votes` | All patterns' vote counts + trending info |
| `POST` | `/vote/{pattern_id}` | Cast upvote (409 if duplicate) |
| `GET` | `/comments/{pattern_id}` | Get comments for a pattern |
| `POST` | `/comments/{pattern_id}` | Post a comment |
| `POST` | `/comments/{comment_id}/flag` | Flag a comment (auto-hides at 3) |
| `GET` | `/health` | Health check |

Spam prevention: fingerprint-based dedup, rate limiting (30 votes/hr, 5 comments/hr), honeypot field, community flagging.

## Nginx config addition (for API proxy)

```nginx
location /rhizome/api/ {
    proxy_pass http://127.0.0.1:8100;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

## Deploying & Pushing

**Deploys and git pushes are handled by the ops steward** (see `../ops/agents/steward.md`). Do not deploy or push directly.

To request a deploy: add an entry to `../ops/DEPLOY_QUEUE.md` with scope (push/deploy/both), changed files, and any notes. The steward runs tests, pushes to GitHub, deploys via `bash deploy.sh`, cache-busts `?v=` on `data.js`, and verifies health — on a 60-minute cycle.

## Notes

- `build.py` validates hierarchy types and warns on missing/invalid entries
- Patterns span corporate, military, nature-inspired, AI-native, experimental, etc.
- Mermaid diagrams are embedded per-pattern and rendered client-side
- Social features degrade gracefully — if API is down, the site still works
- Systemd service: `rhizome-api` (managed by deploy.sh --api)
