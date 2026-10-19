---
description: Milestone 1 — simulated data (data/) and knowledge base (docs/)
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(uv run pytest:*)
---

# Milestone 1 — Data and documents

Read CLAUDE.md (sections "Data", "Documents", "Services", "Priorities").
In this milestone NO package code is written except `tests/test_data.py`.

## Goal
Create the simulated state of the network and the knowledge base the agents
will work on, with the three hard cases from the assignment present.

## Expected files
- `data/services.json`, `data/inventory.json`, `data/tickets.json`
- `docs/`: 8+ `kb-<type>-NN.md` articles + `service-catalog.md`,
  `escalation-procedure.md`, `restart-policy.md`, `priority-guide.md`
- `tests/test_data.py`

## Acceptance criteria (all checkable in test_data.py)
1. `services.json` has the 4 offices (MAD-01, MAD-02, BCN-01, VAL-01) and,
   in each one, the 7 services from CLAUDE.md with value `ok|degraded|down`.
2. At least one critical service `down` in 2+ offices at the same time
   (multi-office outage) and at least one `degraded`.
3. `inventory.json`: 12+ devices; each with `id`, `type`, `office`,
   `model`, `status`; every `office` exists in services.json.
4. `tickets.json`: 8+ tickets with `id` (`T-NNNN`), `office`, `symptom`,
   `status` (`open|closed|reopened`), `reopenings` (integer ≥ 0).
   - At least 1 ticket with `reopenings >= 1`.
   - At least 2 tickets with the **same** `symptom` in offices whose service
     status leads to different causes (e.g. "I have no internet": one because
     the `vpn` is down, another because of a device with a faulty network card).
5. Every `kb-*.md` article has exactly the sections `## Symptoms`,
   `## Cause` and `## Steps`; together they cover the 5 types from CLAUDE.md.
6. The 4 policy documents are consistent with CLAUDE.md:
   same list of critical services, same hours (Mon–Fri 08:00–18:00), same P1–P4 rules.
7. Realistic content in English; no real personal data.
8. `uv run pytest` green, no network.

## When done
Summarize in a table which file covers each criterion. Do not commit.

## What I review
1. That the three hard cases are in the data: same symptom with a different cause (T-0001/T-0002), reopened ticket (T-0007) and ERP down in MAD-02 and BCN-01.
2. That the policies in `docs/` say the same as CLAUDE.md (critical services, hours, P1–P4); `test_data.py` checks it.
3. That the data are simulated and there is no real personal data.
