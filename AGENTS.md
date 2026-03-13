# Rhizome

Browsable taxonomy of 207 agent orchestration patterns. Live at https://thisminute.org/rhizome.

## Stack

- **Frontend**: Single `index.html` (dark-themed SPA, Mermaid.js for diagrams via CDN)
- **Data**: 13 JSON files in `structures/` → `build.py` aggregates them into `data.js`
- **API**: FastAPI + SQLite in `api/` — upvotes, comments, trending (optional; site degrades gracefully without it)
- **Deploy**: `deploy.sh` runs build, scp's to Google Cloud, optionally deploys API
- No package manager. No test suite.

## Commands

- **Build**: `python build.py` — deduplicates, validates, sorts, outputs `data.js`
- **Deploy**: `bash deploy.sh` — build + scp + verify (add `--api` to deploy API too)
- **Classify**: `python classify_hierarchy.py` — auto-classify patterns by hierarchy type
- **Init DB**: `python api/init_db.py` — create SQLite database for social features
- **Run API locally**: `uvicorn api.main:app --host 0.0.0.0 --port 8100`
- **Local dev**: open `index.html` in a browser (file:// works; social features need API)

## Key files

| File | What it does |
|------|-------------|
| `index.html` | Entire frontend — filtering, hierarchy types, votes, comments |
| `data.js` | Generated. 207 patterns as `window.STRUCTURES` array |
| `build.py` | Aggregates `structures/*.json`, merges structural classes, dedupes by ID, validates, sorts |
| `structural-classes.json` | 15 structural classes with mappings for all 207 patterns |
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

## Notes

- `build.py` validates hierarchy types and warns on missing/invalid entries
- Patterns span corporate, military, nature-inspired, AI-native, experimental, etc.
- Mermaid diagrams are embedded per-pattern and rendered client-side
- Deploy requires `gcloud` CLI configured with access to the target instance
- Social features degrade gracefully — if API is down, the site still works
- Systemd service: `rhizome-api` (managed by deploy.sh --api)
