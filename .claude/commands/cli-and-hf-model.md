---
description: Milestone 6 — HFModel (Hugging Face), SimulatedModel and the office-support command
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(uv run pytest:*)
---
# Milestone 6 — Real model and command line

Read CLAUDE.md (sections "Environment and commands", "Model contract") and
`src/office_support/model.py`, `orchestrator.py`.
In this milestone the evaluation (milestone 7) and the web (milestone 8) are NOT
written. No dependencies are added (`huggingface-hub` and `python-dotenv` are already there).
**Never read, print or copy `.env`.** The tests use neither the network nor `HF_TOKEN`.

## Goal
Handle an incident from the terminal, with the real Hugging Face model or with
a simulated model that needs no token:
`uv run office-support "I have no internet" --office MAD-01 [--ticket T-0001] [--model simulated|hf]`

## Expected files
- `src/office_support/model.py` (add `HFModel` and `SimulatedModel`)
- `src/office_support/cli.py`
- `pyproject.toml`: the `office-support` script points to `office_support.cli:main`
- `tests/test_model_hf.py`, `tests/test_cli.py`

## Decisions for this milestone
- **`HFModel(model=None, client=None)`:**
  - loads `.env` with `load_dotenv()` and reads `HF_TOKEN` and `HF_MODEL` from
    `os.environ`; without `HF_TOKEN` it raises `RuntimeError` with a message
    explaining how to configure it (without showing any value);
  - uses `InferenceClient(model, token)`; `client` lets the tests inject a fake one;
  - `generate()` calls `chat_completion` with `[{"role": "system", ...}] +
    messages`, `temperature=0`, `max_tokens=512`, and returns the text;
  - a network or provider failure is retried once; if it fails again,
    `RuntimeError` with the reason (never with the token).
- **Default model (`HF_MODEL`):** set in this milestone. Candidate:
  `Qwen/Qwen2.5-72B-Instruct` (good JSON, available in Inference
  Providers). It is confirmed with a real run **that I launch** (the
  program is in `ask` because it spends my token); if it fails,
  `meta-llama/Llama-3.3-70B-Instruct` is tried. The chosen one is written in CLAUDE.md.
- **`SimulatedModel`** (it is not `ScriptedModel`): a deterministic rule-based
  model to demonstrate the system without a token. It identifies the agent by the
  system prompt (`«classifier»`, …) and answers:
  - classifier: type by keywords (internet/vpn → network, print → printer,
    ERP/password → app_access, email → email, laptop/monitor →
    hardware; otherwise other) and P3;
  - diagnosis: checks the service associated with the type and answers with what it observed;
  - knowledge: `search_docs` with the cause and cites the first fragment; proposes
    restarting the service only if it is `down` or `degraded`;
  - escalation: summary with the incident and the cause.
  It must let the orchestrator apply all the rules (it does not imitate them).
- **CLI (`cli.py`, `argparse`):**
  - arguments: incident, `--office` (required), `--ticket`,
    `--model` (`simulated` by default, or `hf`), `--trace` (shows the steps);
  - `confirm` asks in the terminal "Confirm <action>? [y/N]"; only
    "y"/"yes" is True; without an interactive terminal (EOF) it is False;
  - prints final, type, priority, escalation (if any) and the answer to the employee;
  - `main(argv=None, read=input) -> int`: returns 0, or 2 if the model fails
    (clear message on stderr, no Python traceback).

## Acceptance criteria
1. `HFModel` with a fake client: sends the system prompt as the first
   message followed by the messages, with `temperature=0` and `max_tokens=512`, and
   returns the text of `choices[0].message.content`.
2. Without `HF_TOKEN` (with `monkeypatch.delenv` and without reading the real `.env`:
   `load_dotenv` patched) → `RuntimeError` mentioning `HF_TOKEN`.
3. A client that fails once and then answers → returns the answer; one
   that always fails → `RuntimeError` after 2 attempts. The error message
   does not contain the token.
4. `HF_MODEL` from the environment takes precedence over the default value.
5. `SimulatedModel` + `orchestrate()` (fixed clock):
   - "I have no internet" in MAD-01, confirm True → `resolved`, vpn restarted;
   - "I have no internet" in MAD-01, confirm False → `escalated`;
   - "I can't log in to the ERP" in MAD-02 → `escalated` with P1 (multi-office);
   - "the printer is not printing" in MAD-02 with T-0007 → `escalated` (reopened).
6. CLI with `--model simulated`: prints final, type, priority and answer;
   with input "y" the restart runs and with "n" or EOF it does not; `--trace`
   shows the numbered steps; non-existent office → `rejected`.
7. `--model hf` without a token → exit code 2 and a message on stderr mentioning `HF_TOKEN`.
8. `pyproject.toml` points to `office_support.cli:main` and
   `uv run office-support --help` works.
9. No test makes network calls or reads `.env`. Code in English,
   typed, short functions. `uv run pytest` green.

## Manual check (I do it, not Claude Code)
`uv run office-support "I have no internet" --office MAD-01 --model hf --trace`
and I record in worklog.md the chosen model, the result and the trajectory.

## When done
Summarize in a table which test covers each criterion. Do not commit.

## What I review
1. That no test uses the network or reads `.env`.
2. That a model error comes out without the token and with exit code 2.
3. The real run with `--model hf --trace` (I launch it: it spends credits).
