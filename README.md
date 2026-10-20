# office-support

Technical support for an office network. Its goal is to resolve employees'
first-level incidents (no connection, printer, access to an application) with
several diagnostic steps over a simulated state of services, and to escalate
the ones that are not resolved.

Four agents work in a chain (classifier → diagnosis → knowledge → resolved or
escalated). The safety rules (confirmation of irreversible actions, guardrail,
step limit, errors as observations and checked citations) live in the code,
not in the prompt, and so does the priority check: the code raises the priority
when the data require it, and a safety hazard (explosion, fire, smoke, sparks)
is at least P2 and goes straight to second level.

The GitHub repository is named `soporte-oficinas`.

## Requirements
- [uv](https://docs.astral.sh/uv/) (installs Python 3.12 if it is missing).
- No token is needed for the tests or for the simulated model.

## Installation
```
uv sync
```

## Tests
```
uv run pytest
```
No network and no token: they use a model with scripted responses (`ScriptedModel`)
(341 tests; the Streamlit page tests are skipped unless you run
`uv run --group web pytest`).

## Running
```
uv run office-support "<incident>" --office <MAD-01|MAD-02|BCN-01|VAL-01> [--ticket T-NNNN] [--model simulated|ollama|hf] [--trace]
```
It uses the simulated model by default (no token). `--trace` shows every step
of every agent. If a service has to be restarted, the program asks `[y/N]`.

### Examples (the hard cases from the assignment)
```
# 1. Asks for confirmation: the MAD-01 vpn is down (P1). Answer "y" or "n".
uv run office-support "I have no internet" --office MAD-01 --trace

# 2. Same symptom, different cause: in VAL-01 the services are fine; the
#    computer has a faulty network card. Nothing is restarted.
uv run office-support "I have no internet" --office VAL-01 --ticket T-0002 --trace

# 3. Multi-office outage: the ERP is down in MAD-02 and BCN-01 → escalated with P1.
uv run office-support "I can't log in to the ERP" --office MAD-02 --trace

# 4. Reopened ticket: T-0007 has already been reopened twice → escalated directly.
uv run office-support "the printer is not printing" --office MAD-02 --ticket T-0007 --trace

# 5. Safety hazard: physical repair → at least P2 and escalated directly.
uv run office-support "The printer has exploded" --office MAD-02 --trace
```
Incidents must be written in English: the simulated model recognises English
keywords.

## Web console (React)
```
uv run office-support-web
```
It opens http://127.0.0.1:8000 in the browser (`--port N` to change it,
`--no-browser` not to open it). You watch the four agents work live: each
model response, tool call and orchestrator rule appears step by step, the
pipeline lights up the active agent, the R1–R5 badges light up when a rule
acts and an irreversible action is confirmed or rejected in a modal. Example
cases in one click (also as links: `http://127.0.0.1:8000/?example=0` … `6`),
network status, light and dark themes, and the Ollama models if Ollama is
running. It needs no extra Python package; the browser loads React from a CDN,
so it needs an internet connection the first time.

## Web (Streamlit, optional alternative)
```
uv run --group web streamlit run app.py
```
It opens at http://localhost:8501. One-click example cases, buttons to
confirm or reject the irreversible action, the trace of every agent and a
priority guide. It uses the simulated model (no token); if Ollama works on the
machine, a real model can also be chosen. Light or dark mode in the
⋮ → Settings menu. `uv sync` does not install Streamlit: only `--group web` does.

## Evaluation
```
uv run python -m office_support.evaluation                     # scripted
uv run python -m office_support.evaluation --model simulated   # with the simulated model
```
Prints the table of cases (expected versus obtained result and trajectory).

## Real local model (Ollama), optional
Free, no token and no credits. The report traces were made with
`qwen2.5:14b` (9 GB); the default `qwen2.5:7b` is lighter.
1. Install [Ollama](https://ollama.com/download) and download a model:
   ```
   ollama pull qwen2.5:7b
   ```
2. With Ollama running, use `--model ollama`, for example:
   ```
   uv run office-support "I have no internet" --office MAD-01 --model ollama --trace
   ```
   Optional: `OLLAMA_MODEL=<model>` (e.g. `qwen2.5:14b`) and `OLLAMA_URL=<url>` in the
   environment or in `.env`. In the web console, the installed Ollama models appear
   in the "Model" selector.

## Real model (Hugging Face), optional
1. Create a Hugging Face token with the "Make calls to Inference Providers" permission.
2. Create a `.env` file in the project root (it is not pushed to git or
   submitted) with:
   ```
   HF_TOKEN=your_token
   ```
   Optional: `HF_MODEL=<model>` (default `Qwen/Qwen2.5-72B-Instruct`).
3. Use `--model hf`, for example:
   ```
   uv run office-support "I have no internet" --office MAD-01 --model hf --trace
   ```
Each incident makes about 5–10 model calls and spends the account's credits.

## Structure
```
src/office_support/
  domain/               state (State, Step, Action, Result) and policy (services,
                        priorities, response times, business hours)
  agents/               contracts (JSON + validation), definitions, prompts,
                        runner (common loop) and specialists (the four agents)
  orchestration/        orchestrator (handoff flow) and rules (priority,
                        handoff, R2 guardrail, R5 citations)
  interfaces/           cli, web (logic without a UI), server (web console)
                        and static/ (React page)
  model.py, tools.py, retrieval.py (BM25), evaluation.py
app.py                  Streamlit web (optional alternative)
data/                   simulated state: services, inventory, tickets
docs/                   knowledge base (kb-* articles and policies)
tests/                  pytest tests
report/, report.pdf     report and its generator (report/generate.py)
CLAUDE.md, .claude/     specification, permissions and one command per milestone
                        (/data-and-docs … /modularization)
worklog.md              decision log
```
