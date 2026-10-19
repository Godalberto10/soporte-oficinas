---
description: Milestone 7b — fix what my evaluation found (rejection, slow computer, simulated model)
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(uv run pytest:*), Bash(uv run python -m office_support.evaluation:*)
---
# Milestone 7b — Fixes after the evaluation

Read CLAUDE.md, `tests/test_evaluation.py` (the `xfail` marks and their reasons) and the
"Milestone 7" entry in `worklog.md`.
In this milestone the evaluation cases and their expected values, rules
R1–R5 and the web are NOT changed. No dependencies are added.

## Goal
Make the 5 known failures of my evaluation pass because their cause has been
fixed, not because the test was changed.

## Expected files
- `src/office_support/orchestrator.py` (rejection without priority)
- `docs/kb-hardware-03.md` (new)
- `src/office_support/model.py` (`SimulatedModel`)
- `tests/test_evaluation.py` (remove the fixed `xfail` marks), and new tests
  in `tests/test_orchestrator.py` and `tests/test_model.py`

## Decisions (mine)
- **D1 — A rejection has no priority.** What is not processed is not prioritized:
  with `final="rejected"`, `Result.priority` is `None` (the
  `out_of_scope` type is kept).
- **Article `kb-hardware-03.md` "The computer is slow"**, with `## Symptoms`
  (employee phrases: "my computer is slow", "the PC freezes"…),
  `## Cause` and `## Steps`: restart the computer, close unused programs
  and, if nothing changes, contact the technical team (escalate).
- **SimulatedModel** (it is the one the public web will use):
  - more hardware keywords: computer, pc, device, slow, mouse…;
  - if it fits no type: `other` only if it sounds like support (not working,
    error, failure, problem, I can't, program…); otherwise `out_of_scope`;
  - initial priority P4 for printer (there is usually another one available, D2) and P3
    for the rest; the orchestrator still raises it based on the data;
  - knowledge only cites `kb-<type>-NN.md` articles of its type; if there are
    none among the retrieved ones, it gives no procedure (and the incident is escalated).

## Acceptance criteria
1. Case 7 with the script: `rejected`, `out_of_scope`, no priority.
   Orchestrator test: a rejection does not keep the classifier's priority.
2. `kb-hardware-03.md` passes the tests in `test_data.py` (3 sections) and
   the search "my computer is slow" returns it first.
3. Simulated: "can you recommend a restaurant?" → `out_of_scope`;
   "my computer is slow" → `hardware`; "the printer is not printing" → P4;
   "I have no internet" is still `network` with P3.
4. Simulated: with fragments of another type only, `procedure` is `null`.
5. In `test_evaluation.py` the 5 `xfail` marks disappear and every case passes
   in both passes, without changing a single expected value.
6. `uv run pytest` green, no network and no `HF_TOKEN`.

## When done
Paste both evaluation tables and a criterion → test table. Do not commit.

## What I review
1. That the `xfail` marks disappear because the cause is fixed, not the test.
2. That no expected value of the evaluation has changed.
3. That "my computer is slow" gives the `kb-hardware-03` procedure.
