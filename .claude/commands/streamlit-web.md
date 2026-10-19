---
description: Milestone 8 — Streamlit web as a thin layer over orchestrate()
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(uv run pytest:*), Bash(uv run --group web pytest:*), Bash(uv add --group web streamlit)
---
# Milestone 8 — Web interface

Read CLAUDE.md (sections "Web interface" and "Orchestration") and `orchestrate` in
`orchestrator.py`.
In this milestone the logic of agents, orchestrator, models and data is NOT changed,
and the web contains NO agent logic: it only calls `orchestrate()`.

## Goal
Let the lecturer try the system from the browser, without a terminal, with
the interesting cases one click away.

## Expected files
- `app.py` (Streamlit, at the root)
- `src/office_support/web.py` (page logic without Streamlit, tested)
- `tests/test_web.py` (without Streamlit) and `tests/test_app.py` (with
  `streamlit.testing`, skipped if Streamlit is not installed)
- `pyproject.toml` (optional `web` group), README and CLAUDE.md

## Decisions (mine)
- Free text for the incident, a dropdown with the 4 offices and an optional
  ticket. In a real company the office would come from the login.
- Example buttons with my cases: internet in MAD-01 (asks for confirmation),
  internet in VAL-01 (same phrase, different cause), ERP in MAD-02 (several
  offices), printer with T-0007 (reopened), slow computer and restaurant
  (out of scope).
- `confirm` is a button (Confirm / Reject): the first run stops when
  asking for confirmation and the page repeats it with my answer. With
  the simulated model and a new `Network` the path is identical and nothing irreversible
  runs before answering.
- Only `SimulatedModel`: the public web spends no credits and needs no token.
- Streamlit in an optional group (`uv add --group web streamlit`): `uv sync`
  and `uv run pytest` do not need it; the web is launched with
  `uv run --group web streamlit run app.py`.

## Acceptance criteria
1. `web.handle(incident, office, ticket, decision=None)` returns the pending
   `Action` if confirmation is needed, and the `Result` otherwise.
2. With the decision: "I have no internet" in MAD-01 → `resolved` if I confirm and
   `escalated` with the vpn not restarted if I reject (R1 from the web).
3. The examples give the final from my evaluation (cases 1, 3, 5, 4, 11 and 7).
4. An empty ticket is the same as no ticket; non-existent office or ticket →
   `rejected` with the reason.
5. `test_app.py`: the page loads, an example shows the result and in the
   MAD-01 case the buttons appear and "Confirm" ends in resolved.
6. `uv run pytest` stays green without Streamlit; with `--group web`, too.

## When done
Criterion → test table. Do not commit.

## What I review
1. That `app.py` decides nothing: it only displays and calls `web.py`/`orchestrate()`.
2. That with "Reject" the vpn stays down and the incident is escalated.
3. The page in the browser with the examples.
