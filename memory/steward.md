# Steward Memory

Persistent learnings across sessions. Update after each session. Remove stale info.

## Session 2026-03-14: Audit, bug fixes, evolution page

### What was done
- Fixed localStorage reads crashing in private browsing (init reads now wrapped in try/catch)
- Fixed keyboard shortcuts (j/k/s) firing when detail drawer is open — now only detail-specific keys (arrows, h/l, t, Escape) work in drawer
- Fixed shortcuts overlay closing on modifier keys (Shift, Ctrl, Alt) — now only closes on non-modifier keys
- Enriched 3 short realWorldExample values (meta-learning-zoo, military-chain-of-command, holacracy)
- Removed duplicate left/right arrow handler (consolidated into detail-open guard block)
- Full data quality audit: all 200 patterns complete, no missing fields, no placeholders, no duplicates
- Refined about/intro copy for tone (cut thesis-statement opener, removed hedging from origin line)
- Created evolution.html — timeline of organizational evolution across 3 projects (agi, thisminute, rhizome)
- Added "case" link in header actions to evolution page
- Deploy queue updated, includes note about agent-forge gh-pages link needed

### Known remaining lower-priority items
- No `popstate` listener — hash routing is write-only (browser back/forward doesn't work)
- Filter panel headers (collapse/expand sections) are not keyboard-accessible
- Field notes and shortcuts overlays have `aria-modal="true"` but no focus trap / initial focus management
- Agent `count` field inconsistently present (83% of agents lack it — fine since 1 is the default)
- `history.replaceState` means detail-to-detail nav is not back-button traversable
- Mermaid SVG innerHTML injection relies on Mermaid v10's built-in DOMPurify
- Mobile: search input scrolls away with no replacement in mobile filter bar
- Agent-forge gh-pages needs link to evolution page added (separate deploy)

### Observations
- All 200 patterns structurally complete — no missing required fields
- 92 tests cover build, schema, API, classifier, and frontend smoke tests
- Large uncommitted diff spans multiple sessions: rebranding, 2-col detail layout, field notes overlay, accessibility, DRY refactors, data consolidation, evolution page
