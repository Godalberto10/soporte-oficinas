---
description: Milestone 5 — orchestrator with handoff and rules R1–R5 guaranteed in code
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(uv run pytest:*)
---
# Milestone 5 — Orchestrator and safety rules

Read CLAUDE.md (sections "Priorities", "Services", "Orchestration: handoff",
"Rules guaranteed by the code") and `src/office_support/agents.py`.
In this milestone `HFModel`, the CLI and the web are NOT written. No dependencies are added.

## Goal
`orchestrate()` joins the 4 agents with the handoff from CLAUDE.md and
guarantees rules R1–R5 in code, not in the prompt. It returns a `Result` with
the answer to the employee, the valid citations and the full trace.

## Expected files
- `src/office_support/orchestrator.py`
- `tests/test_orchestrator.py`
- (if needed) a minimal adjustment in `agents.py`, with its test

## Decisions for this milestone
- **Signature:** the one in CLAUDE.md plus two optional keyword-only
  parameters for the tests: `network: Network | None = None` (by default, a new
  `Network` loaded from `data/`) and `index: BM25Index | None = None`.
- **`final="rejected"`** only in two cases:
  - invalid input (non-existent office or ticket), without calling the model;
  - the classifier returns `type="out_of_scope"` (the request is not office
    support): it stops after the classifier, without diagnosis.
  An action the user rejects or disagrees with does **not** give `rejected`:
  it is escalated to the second level so another solution is sought (handoff rule).
- **New type `out_of_scope`** (already in CLAUDE.md): added to `TYPES` in
  `agents.py` and to the classifier's instructions, distinguishing it from
  `other` (a support incident without a category).
- **Orchestrator notes** (priority raise, removed citations,
  guardrail, rejection, handoff) are `Step(agent="orchestrator")` and **do not
  count** towards the limit: only model responses and tools count.
  `Step.n` is the position in the trace.
- **Minimum priority** (`minimum_priority(network, office, service)`), applied
  after diagnosis with `state.service`:
  - the service is not `ok` in 2+ offices → **P1** (multi-office);
  - critical service `down` in the office → **P1**; `degraded` → **P2**;
  - otherwise there is no minimum. It is only raised, never lowered, and noted in the trace.
- **Business hours:** `in_business_hours(dt)` → Monday to Friday, 08:00 ≤ hour < 18:00.
- **Answer to the employee** (`Result.answer`) is written by the code:
  - resolved: procedure + "Sources:" with the valid citations;
  - escalated: `ESC-NNNN` id, priority and first response time from the
    catalog (P1 15 min, P2 30 min, P3 2 h, P4 1 business day);
  - rejected: why it is not processed (invalid input or out of scope);
  - limit: that it could not be completed and will be reviewed.

## Flow (in code)
1. Validate office and ticket → if they do not exist, `rejected`.
2. **classifier**. `unreadable` → escalation; `limit` → `step_limit_reached`;
   `type="out_of_scope"` → `rejected`.
3. **diagnosis**. Same. Afterwards, raise the priority if needed.
4. Handoff after diagnosis:
   - ticket with `reopenings >= 1` → **escalation**;
   - multi-office outage → **escalation** with priority P1.
5. **knowledge**. Check citations (R5). No procedure or no valid
   citations → **escalation**.
6. If there is an `action`: guardrail (R2) → if it blocks, note it and **escalation**
   without calling `confirm`. If it passes, `confirm(action)`:
   - `False` → note the rejection, do not execute, **escalation**;
   - `True` → execute; if it raises `ToolError`, **escalation**; if it works, `resolved`.
7. No `action` and valid citations → `resolved`.
8. **escalation**: if the agent ends `unreadable`, the code still creates an
   escalation with an automatic summary (incident, cause) and the state's
   priority (or P3), so there is always an id. If it ends at `limit` → `step_limit_reached`.

## Rules R1–R5 (each with a test that would fail if the code failed)
- **R1 Confirmation:** an irreversible tool only runs if `confirm` returns
  True. With False, the `Network` does not change and the trace has no step with
  `tool="restart_service"`/`"close_ticket"`; final `escalated`.
- **R2 Guardrail** (`guardrail(action, state, network, now) -> str | None`,
  returns the reason for blocking): `restart_service` of a critical service during
  business hours requires `service == state.service` and status `down` or
  `degraded` at that moment. Also, always: the action's office is the
  state's office and at most 1 restart per service and run. If it blocks,
  `confirm` is not called.
- **R3 Limit:** 12 global steps (the counter carries over between agents); when
  exceeded, `final="step_limit_reached"`.
- **R4 Errors as observations:** already in the loop (milestone 4); here, `unreadable`
  from any agent → escalation.
- **R5 Checked citations:** a citation is valid only if `docs/<file>.md#<section>`
  is among the fragments returned by `search_docs` **in this run**
  (read from the trace). Invalid ones are removed and which ones is noted. Without
  valid citations there is no `resolved`.

## Acceptance criteria
1. **Resolved with restart** (MAD-01, "I have no internet", Monday 10:00,
   `confirm` → True): trajectory classifier → diagnosis → knowledge;
   `final="resolved"`, `type="network"`, `priority="P1"`, vpn `ok`, citation
   `docs/kb-network-01.md#Steps` in the answer.
2. **R1:** same case with `confirm` → False: vpn still `down`, no executed
   `restart_service` step, trajectory ends in escalation,
   `final="escalated"` with id.
3. **R2:** during business hours it blocks without calling `confirm` (a
   `confirm` that fails if called): restarting `erp` when the diagnosed one
   is `vpn`; restarting a critical service that is `ok`; restarting in another office. Outside
   business hours (Saturday) the first case does ask for confirmation. `guardrail` blocks
   a second restart of the same service.
4. **R3:** a model that only calls tools → `step_limit_reached` and
   `state.steps` does not exceed 12; orchestrator notes do not count.
5. **R4:** 2 unreadable responses from the classifier → `final="escalated"`; if
   the escalation agent is also unreadable, there is still an escalation id.
6. **R5:** a made-up citation (not retrieved) is removed and noted; if it was
   the only one, the final is `escalated`, not `resolved`.
7. **Priority:** the classifier says P3 with `vpn` down → raised to P1 and
   noted in the trace; a higher priority is never lowered.
8. **Same symptom, different cause:** "I have no internet" in VAL-01 with a
   device diagnosis (`service=None`) → no priority raise and no
   restart; with a cited procedure from `kb-network-02.md` → `resolved`.
9. **Reopened ticket:** T-0007 → after diagnosis goes straight to escalation
   (knowledge does not run).
10. **Multi-office:** `erp` down in MAD-02 and BCN-01 → escalation with P1 even if
    the classifier said P2.
11. **Rejected:** office `SEV-01` or ticket `T-9999` → `rejected` and the model
    is not called. "Can you recommend a restaurant?" with the classifier returning
    `out_of_scope` → `rejected`, trajectory classifier only, no escalation.
    An action rejected by the user never gives `rejected` (criterion 2).
12. `in_business_hours`: Friday 17:59 yes; Friday 18:00 no; Saturday 10:00 no; Monday 08:00 yes.
13. Code in English, typed, short functions. `uv run pytest` green,
    no network and no `HF_TOKEN`.

## When done
Summarize in a table which test covers each criterion and each rule R1–R5. Do not commit.

## What I review
1. That each rule R1–R5 has a test that fails if the rule is broken (mutations).
2. That the trajectories of the three hard cases are the ones in CLAUDE.md.
3. That with `confirm` false the network does not change and the action does not appear in the trace.
