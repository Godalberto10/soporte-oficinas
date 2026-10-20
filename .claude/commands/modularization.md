---
description: Milestone 10 — organize src/ into subpackages by responsibility, without changing behaviour
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(uv run pytest:*), Bash(git mv:*), Bash(git status), Bash(git diff:*)
---
# Milestone 10 — Modularization of src/

Read CLAUDE.md (sections "Structure", "Orchestration" and "Rules guaranteed by
the code") and every module of `src/office_support/`.
It is a pure refactor: NO behaviour, prompt text, trace or answer changes.

## Goal
The professor asked for the source code to be modularized. The flat package
becomes subpackages, so the architecture can be read from the folders and the
rules guaranteed by the code live in their own file.

## Decisions (mine)
- Four subpackages: `domain/`, `agents/`, `orchestration/`, `interfaces/`.
  `model.py`, `tools.py`, `retrieval.py` and `evaluation.py` stay as modules:
  they are small and have a single responsibility.
- One home for shared constants (`domain/policy.py`); no layer imports
  constants from the orchestrator.
- The rules (input, priority, handoff, R2, R5) go to `orchestration/rules.py`;
  the flow, R1, R3 and R4 stay in `orchestrator.py`.
- `__init__.py` re-exports the public names; no shims at the old paths.
- `git mv` for moved files, so the history follows them.

## Expected files
- `domain/state.py` (moved), `domain/policy.py`.
- `agents/contracts.py`, `definitions.py`, `prompts.py`, `runner.py`, `specialists.py`.
- `orchestration/orchestrator.py`, `orchestration/rules.py`.
- `interfaces/cli.py`, `web.py`, `server.py`, `static/`.
- `pyproject.toml`: entry points to `office_support.interfaces.cli:main` and
  `office_support.interfaces.server:main`. `app.py`, README and tests: imports only.

## Tests
No new tests: the existing suite is the oracle. Same number of tests, all green,
before and after; only import lines of the tests change.

## What I review
- `git diff` of the moved files only shows imports and the split, not logic.
- `uv run pytest` and `uv run --group web pytest tests/test_app.py` green.
- `office-support` and `office-support-web` start.
- "Structure" in CLAUDE.md and README match the folders.
