---
description: Milestone 2 — shared state, ScriptedModel and tools with their registry
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(uv run pytest:*)
---
# Milestone 2 — State, scripted model and tools

Read CLAUDE.md (sections "Model contract", "Orchestration: handoff",
"Tools", "Data", "Services").
In this milestone NO agents, orchestrator, BM25 retrieval, `HFModel` or CLI
are written. No dependencies are added.

## Goal
Have the pieces the agents will be built on: the dataclasses of the shared
state, the scripted model for the tests and the tools that query and modify
the simulated state of the network.

## Expected files
- `src/office_support/state.py`
- `src/office_support/model.py`
- `src/office_support/tools.py`
- `tests/test_state.py`, `tests/test_model.py`, `tests/test_tools.py`

## Decisions for this milestone
- `HFModel` is left for milestone 6; here only `Model` (Protocol) and `ScriptedModel`.
- `search_docs` is registered in milestone 3, together with the BM25 index.
- The tools work on a `Network` class that loads the three JSON files
  from a path (`Network.from_directory(path)`, default `data/`). Changes
  (restarts, closures, escalations) are made **in memory**: the JSON files are
  never written. Each `Network` has its own copy of the data, so that every
  run of `orchestrate()` starts from the initial state.
- `create_tools(network) -> dict[str, Tool]` binds the functions to a
  `Network` and keeps the signatures from CLAUDE.md (e.g. `check_service(service, office)`).
- `execute(tools, name, arguments) -> dict` is the single call point: it turns
  a non-existent tool and arguments that do not match the signature (checked
  with `inspect.signature(...).bind`, not by catching any `TypeError`) into a
  `ToolError`. That way the orchestrator only catches one type of error (R4).
- Confirmation and the guardrail do NOT go in the tools: they belong to the
  orchestrator (milestone 5). The tools only validate arguments.

## Acceptance criteria
1. `state.py` defines `Step`, `Action`, `State` and `Result` as typed
   dataclasses with the fields from CLAUDE.md. `State.trace`,
   `State.actions` and `State.citations` start empty and are not shared
   between instances; `State.steps` starts at 0 and `State.final` at `None`.
   `Action` has `tool` and `arguments`.
   `Result` has `final`, `answer`, `citations`, `trace`, `type`,
   `priority` and `escalation` (escalation id or `None`).
2. `model.py` defines the `Model` `Protocol` with
   `generate(system, messages) -> str`. `ScriptedModel(responses)` returns the
   responses in order, stores the calls received (`system`, `messages`)
   so they can be inspected and raises `RuntimeError` when they run out.
3. `tools.py` defines `ToolError`, the `Tool` dataclass
   (`name`, `description`, `reversible`, `function`), `create_tools(network)`
   and `execute(tools, name, arguments)`. Every `description` is non-empty.
4. `check_service`, `check_device`, `search_tickets`, `create_escalation`,
   `restart_service` and `close_ticket` are registered.
   Only `restart_service` and `close_ticket` have `reversible=False`.
5. Every tool returns a `dict`:
   - `check_service("vpn", "MAD-01")` → `{"service": "vpn", "office": "MAD-01", "status": "down"}`.
   - `check_device("PC-VAL01-002")` returns the inventory record.
   - `search_tickets(office=None, symptom=None)` filters by office and/or by
     symptom (substring, case-insensitive); with no filters, all of them.
   - `create_escalation` returns an increasing `ESC-NNNN` id.
   - `restart_service` leaves the service `ok` (in memory).
   - `close_ticket` sets the ticket to `closed` and stores the resolution.
6. They raise `ToolError` with a readable message: non-existent office,
   service, device or ticket; priority outside P1–P4; empty summary or
   resolution; closing an already closed ticket.
7. `execute` raises `ToolError` (not `KeyError` or `TypeError`) with a
   non-existent tool, an extra argument or a missing one.
8. Isolation: restarting a service in one `Network` does not change another
   `Network` loaded from the same files, and `data/*.json` does not change
   after running the irreversible tools.
9. Code in English, typed, short functions. `uv run pytest` green,
   no network and no `HF_TOKEN` (including the tests in `test_data.py`).

## When done
Summarize in a table which test covers each criterion. Do not commit.

## What I review
1. That `data/*.json` does not change when restarting, closing or escalating (SHA-256 fingerprint in the tests).
2. That a non-existent tool or one with malformed arguments gives `ToolError` and no other error.
3. That two `Network` objects do not share data.
