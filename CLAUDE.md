# Technical support for an office network — multi-agent system

## Goal
Resolve employees' first-level incidents (no connection, printer, access to an
application…) with several diagnostic steps over a simulated state of
services, and escalate to the second level the ones that are not resolved.
Input: incident text + office + optional ticket id.
Output: `Result` with final status, answer to the employee with citations and trace.
Out of scope: requests that are not office support (they are rejected) and
physical repairs. If the incident is not resolved, the answer tells the
employee what happens next (escalation, its id and the response time).

## Environment and commands
- Python 3.12, uv. No agent frameworks (no LangGraph, no LangChain).
- Allowed dependencies: `huggingface-hub`, `python-dotenv`; dev: `pytest`;
  `streamlit` only for `app.py`, in the optional `web` group (milestone 8).
  The React console (milestone 9) adds no Python dependency: React 18.3.1 and
  htm 3.1.1 are loaded by the browser from a CDN, pinned. No Node, no build step.
  Any other one must be requested first (`uv add` is in ask).
- Run: `uv run office-support "<incident>" --office MAD-01 [--ticket T-0007] [--model simulated|hf|ollama]`
- Tests: `uv run pytest` — no network and no `HF_TOKEN`.
- The token is read from `.env` (`HF_TOKEN`) with python-dotenv. `.env` is never
  read, printed or copied; a key never appears in the code.

## Structure
```
src/office_support/
  domain/          state.py (State, Step, Action, Result) · policy.py (types, services,
                   priorities, response times, offices, business hours)
  agents/          contracts (JSON + validation), definitions (the 4 agents),
                   prompts, runner (common loop), specialists (apply output to State)
  orchestration/   orchestrator.py (orchestrate(): handoff flow, R1, R3, R4) ·
                   rules.py (input, priority, handoff rules, R2 guardrail, R5 citations)
  interfaces/      cli.py (office-support) · web.py (web logic without a UI) ·
                   server.py (office-support-web: stdlib HTTP + JSON API) · static/ (React)
  model.py         Model protocol, ScriptedModel, SimulatedModel, HFModel, OllamaModel
  tools.py         tools + registry with description and reversible
  retrieval.py     own BM25 index over docs/
  evaluation.py    my evaluation cases and the report table
app.py             Streamlit web (thin layer) · .streamlit/config.toml: themes
data/   services.json, inventory.json, tickets.json
docs/   knowledge base in Markdown (see "Documents")
tests/  pytest tests with ScriptedModel
```

## Model contract
```python
class Model(Protocol):
    def generate(self, system: str, messages: list[dict]) -> str: ...
```
- `ScriptedModel(responses: list[str])`: returns the responses in order;
  raises `RuntimeError` when they run out. Tests only.
- `SimulatedModel`: deterministic rules to use the program without a token
  (`--model simulated`, the default). It does not apply safety rules: the
  orchestrator always applies them.
- `HFModel`: `huggingface_hub.InferenceClient`, model in `HF_MODEL`
  (default `Qwen/Qwen2.5-72B-Instruct`, unverified: HF no longer gives free
  credits, 402), `temperature=0`, `max_tokens=512`.
  Retries once, only on transient failures (network, 429, 5xx); never shows the token.
- `OllamaModel`: same as `HFModel` but against a local Ollama
  (`OLLAMA_URL`, default `http://localhost:11434/v1`; `OLLAMA_MODEL`, default
  `qwen2.5:7b`, lightweight). No token, no credits. The report traces were
  produced with `OLLAMA_MODEL=qwen2.5:14b`.
- Every agent asks the model for **a single JSON object** with its contract keys.

## Agents (role · JSON output · allowed tools)
| Agent | Decides | Output | Tools |
|---|---|---|---|
| classifier | type and priority | `{"type", "priority", "reason"}` | `search_tickets` |
| diagnosis | probable cause | `{"cause", "service", "evidence": [..]}` | `check_service`, `check_device`, `search_tickets` |
| knowledge | procedure | `{"procedure", "citations": [..], "action": null \| {..}}` | `search_docs`, `restart_service`, `close_ticket` |
| escalation | handoff to level 2 | `{"summary", "tried": [..], "priority"}` | `create_escalation` |

- `type` ∈ {`network`, `printer`, `app_access`, `email`, `hardware`, `other`,
  `out_of_scope`}. `other` = support without a category; `out_of_scope` = not
  an office support incident.
- An agent can only call its own tools; any other call is an error
  observation and is not executed.

## Priorities (set by the classifier; validated by the code)
- **P1**: affects more than one office, or a critical service is `down`.
- **P2**: affects an entire office, or a critical service is `degraded`.
- **P3**: an employee cannot work and there is no alternative.
- **P4**: an inconvenience with an alternative (another printer, webmail…).
- If the model returns a lower priority than the data require
  (e.g. P3 with a critical service `down`), the code raises it and notes it in the trace.
- Safety hazard (the incident describes an explosion, fire, smoke, sparks or
  something burning): the code raises the priority to at least P2.

## Services
- Critical: `vpn`, `email`, `erp`, `files`, `intranet`.
- Non-critical: `printing`, `guest_wifi`.
- Business hours: Monday to Friday, 08:00 to 18:00 (local time, injectable clock).

## Orchestration: handoff
`classifier → diagnosis → knowledge → (end "resolved" | escalation)`
Rationale: the support flow is sequential and each specialist receives the
conversation with what has already been found out; no supervisor is needed to replan.
Handoff rules (in code, not in the prompt):
- safety hazard → after diagnosis goes straight to escalation (physical repair).
- ticket with `reopenings >= 1` → after diagnosis goes straight to escalation.
- cause affecting more than one office → escalation with P1.
- knowledge without a cited procedure, or a rejected action → escalation.

```python
def orchestrate(incident: str, office: str, model: Model,
                confirm: Callable[[Action], bool],
                now: Callable[[], datetime] = datetime.now,
                ticket: str | None = None, max_steps: int = 12) -> Result
```
- Shared `State`: incident, office, ticket, type, priority, cause,
  service, procedure, citations, actions, trace: list[Step], steps, final.
- `Step`: n, agent, tool | None, arguments, observation.
- `final` ∈ {`resolved`, `escalated`, `step_limit_reached`, `rejected`}.
  `rejected` = invalid input (non-existent office or ticket) or
  `out_of_scope`. An action the user rejects is escalated, not `rejected`.

## Tools (name · arguments · reversible)
- `check_service(service, office)` → status `ok|degraded|down` · yes
- `check_device(device_id)` → inventory record · yes
- `search_tickets(office=None, symptom=None)` → matching tickets · yes
- `search_docs(query, k=3)` → `[{doc, section, text}]` · yes
- `create_escalation(ticket, summary, priority)` → escalation id · yes
- `restart_service(service, office)` · **NO** (irreversible)
- `close_ticket(ticket, resolution)` · **NO** (irreversible)
Every tool has a `description` in the registry; it returns a dict or raises
`ToolError`.

## Rules guaranteed by the code (not the prompt)
1. **Confirmation**: an irreversible tool only runs if
   `confirm(action)` returns True; if it returns False, it does not appear in
   the trace as executed and the final is `escalated` or `rejected`.
2. **Guardrail**: `restart_service` of a critical service during business
   hours also requires `service == state.service` (the diagnosed one) and that
   service being `down` or `degraded`; otherwise it is blocked without asking.
   At most 1 restart per service and run.
3. **Step limit**: 12 steps (each model response or tool call counts as
   one). When exceeded, `final = "step_limit_reached"`.
4. **Errors as observations**: `ToolError`, a disallowed tool and unreadable
   JSON are added to the trace as an observation and the agent carries on.
   2 consecutive unreadable responses from the same agent → escalation.
5. **Checked citations**: every citation `docs/<file>.md#<section>` must be
   among the fragments retrieved in that run; otherwise it is removed and
   noted. Without valid citations there is no "resolved".

## Data (`data/`)
- `services.json`: `{"<office>": {"<service>": "ok|degraded|down"}}`
- `inventory.json`: `[{"id", "type", "office", "model", "status"}]`
- `tickets.json`: `[{"id", "office", "symptom", "status", "reopenings"}]`
- Offices: `MAD-01`, `MAD-02`, `BCN-01`, `VAL-01`.
- Mandatory cases in the data: two incidents with the same symptom and a
  different cause; a reopened ticket; a multi-office outage.

## Documents (`docs/`, at least 12)
- 8 or more `kb-<type>-NN.md` articles with sections `## Symptoms`, `## Cause`,
  `## Steps`.
- `service-catalog.md` (response times by priority),
  `escalation-procedure.md`, `restart-policy.md`, `priority-guide.md`.

## Tests and evaluation
- Tests with `ScriptedModel` and `confirm` false or true; fixed clock.
- Each requirement R1–R5 has at least one test that would fail if the code failed.
- Evaluation (4+ cases) in `tests/test_evaluation.py`: expected result
  (`final`, type, priority) and expected trajectory (sequence of agents).
  I define the cases and their expected result without looking at the code
  (independent oracle).

## Web interface (milestone 8)
Streamlit in `app.py`: `uv run --group web streamlit run app.py`. It only calls
`web.py` and `orchestrate()`; no agent logic. `confirm` is a button: the run
happens in the background and waits for the answer (a single run, like the
terminal's [y/N]). Simulated model by default; Ollama models only appear if
Ollama works on the machine. Light and dark themes.
If published, only with the simulated model: never a token on the server or in the code.

## React console (milestone 9, main web)
`uv run office-support-web` → http://127.0.0.1:8000 (only listens on 127.0.0.1).
`orchestrate(..., on_step=)` streams each step; the page polls the JSON API,
replays the steps per agent, lights up R1–R5 when the orchestrator applies them
and asks the R1 confirmation in a modal. Same rule as the Streamlit web: the
page and the server decide nothing; tests cover web.py and the API.

## Way of working
- One milestone per command in `.claude/commands/`; no work from another milestone is done ahead of time.
- Authorship: the decisions in CLAUDE.md, permissions, commands and evaluation
  cases are mine. Claude Code drafts them from what we discuss (to save
  writing time), implements the code and points out risks; I review every
  change. The worklog says who drafted each thing.
- Git: one commit per milestone or per review block; I do the push.
- The real model (`--model hf`) is only used when I ask for it: it spends credits.
- Every code change comes with its test; `uv run pytest` green when closing.
- Code in English (names and docstrings), typed, short functions.
- Do not: read `.env`, add dependencies without asking, rely on the prompt
  alone for a safety rule, put logic in the web layer.
