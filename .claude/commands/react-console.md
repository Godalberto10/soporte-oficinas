---
description: Milestone 9 — React web console that shows the agents working live
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(uv run pytest:*), Bash(node --check:*)
---
# Milestone 9 — React web console

Read CLAUDE.md (sections "React console", "Web interface" and "Orchestration"),
`orchestrate` in `orchestrator.py` and `web.py`.
The logic of agents, orchestrator, models and data is NOT changed beyond the
`on_step` hook; the page and the server contain NO agent logic.

## Goal
A more professional web than the Streamlit one, as the professor suggested:
the four agents are visible while they work, step by step, with the rules the
orchestrator applies and the R1 confirmation as a modal.

## Decisions (mine)
- React 18 with htm, loaded from a pinned CDN: no Node, no build step, no new
  Python dependency. Server with the standard library (`http.server`), bound to
  127.0.0.1 only. The Streamlit web stays as an optional alternative.
- Live steps through an optional `on_step` callback of `orchestrate()`, not by
  re-running anything: the run is the same single background run as in milestone 8.
- The page polls a small JSON API and replays the steps at a readable pace,
  so the instant simulated model can also be followed.

## Expected files
- `src/office_support/state.py`: `Trace(list)` that calls `on_step` on append.
- `src/office_support/orchestrator.py`: `orchestrate(..., on_step=None)`.
- `src/office_support/web.py`: `Execution.steps`, `snapshot(since)`, `step_view`
  (kind: note | tool | blocked | invalid | call | output, and the rule R1–R5,
  priority, handoff or input), `result_view`, `meta()`.
- `src/office_support/server.py` and the `office-support-web` script.
- `src/office_support/static/`: `index.html`, `app.js`, `styles.css`.

## API
`GET /api/meta` · `POST /api/runs` → id · `GET /api/runs/<id>?since=N` ·
`POST /api/runs/<id>/answer {"yes": bool}`. Static files cannot leave `static/`.

## Tests
1. `on_step` receives every step, in order, notes included.
2. When `confirm()` is asked, the restart is not in the streamed trace (R1).
3. `snapshot` streams kinds and rules; `since` returns only new steps.
4. `note_rule` maps each orchestrator note to its rule.
5. Server over real HTTP on a free port: page and static files, path traversal
   blocked, meta, run → question → confirm → resolved; reject → escalated;
   bad requests 400; unknown run 404.

## What I review
- The page decides nothing: every final, priority and escalation comes from the API.
- The modal only appears when the run is really waiting in `confirm()`.
- `uv run pytest` green; the page opens with `uv run office-support-web`.
