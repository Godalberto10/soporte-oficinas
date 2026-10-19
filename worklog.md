# Worklog

## Milestone 0 — Project skeleton
**What was done:** `uv init --package` (office_support, Python 3.12); dependencies
huggingface-hub and python-dotenv; pytest as a dev dependency;
folders data/, docs/, tests/, .claude/commands/.
**Decisions:** Python without an agent framework; handoff orchestration;
Streamlit web as the last milestone (8), only as a layer on top of `orchestrate()`.
**Problem:** `uv add --dev pytest` failed (os error 396) because the folder is
on OneDrive and does not support hardlinks.
**Solution:** `link-mode = "copy"` in `[tool.uv]` of pyproject.toml.
**Rejected:** —

## Milestone 0b — Permissions (.claude/settings.json)
**What was done:** least-privilege permissions.
- allow: `uv run pytest`, `git status`, `git diff` (they only read or test).
- ask: `uv add/remove` (I decide every dependency), `uv run python` and the
  program (they can call the real model with my token), `git add/commit`.
- deny: reading or editing `.env` (the token never enters the model's context),
  `git push`, `rm`, `curl`, `WebFetch` (no publishing, deleting or exfiltrating data).
**Check:** Claude Code was denied reading .env and running git push (two
real attempts blocked by settings.json).
**GitHub:** private repository Godalberto10/soporte-oficinas; one commit per
milestone; I do the push.
**Rejected:** —

## Milestone 0c — Hugging Face token
**What was done:** fine-grained token ("Make calls to Inference Providers") in
`.env` as `HF_TOKEN`; `.env` ignored by git.
**Check:** `whoami()` returns the user without showing the token; the token
was never pasted into the chat.
**Rejected:** —

## Milestone 0d — CLAUDE.md
**Command launched:** I asked Claude Code for a draft of CLAUDE.md based on my
decisions: 5 types (network, printer, app_access, email, hardware + other),
priority by scope (P1–P4), critical vpn/email/erp/files, hours Mon–Fri 08–18.
**Accepted differences:** JSON contracts of the 4 agents; signature of `orchestrate()`
with injectable `confirm` and `now`; guardrail (a critical service during business
hours only if it is the diagnosed service and is down or degraded; max. 1 restart per service);
reopened ticket → direct escalation; offices MAD-01, MAD-02, BCN-01, VAL-01;
limit of 12 steps; 2 unreadable responses in a row → escalation.
**Rejected differences:** none in this version (147 lines, < 200).

## Milestone 1 — Data and documents
**Command launched:** `/data-and-docs` (.claude/commands/data-and-docs.md).
**What was done:** `data/services.json` (4 offices × 7 services),
`data/inventory.json` (14 devices), `data/tickets.json` (10 tickets);
`docs/` with 10 articles `kb-<type>-NN.md` (2 per type) and the 4 policies;
`tests/test_data.py` (45 tests, one or more per acceptance criterion).
**Hard cases in the data:**
- Same symptom, different cause: "I have no internet" in T-0001 (MAD-01, `vpn`
  down) and T-0002 (VAL-01, services ok, PC-VAL01-002 with a faulty network card).
- Reopened ticket: T-0007 (MAD-02, printer, 2 reopenings).
- Multi-office outage: `erp` down in MAD-02 and BCN-01.
**Decision — intranet becomes critical:** the draft had it as non-critical.
I changed it because password self-service goes through the intranet and it is a
sensitive point for the security of the internal network. Consequences: intranet
down → P1, degraded → P2; during business hours it is only restarted if it is the
diagnosed service and is down or degraded. Updated CLAUDE.md, the 4
policies, `CRITICAL` in the test and the VAL-01 intranet (from `degraded` to
`ok`, so that VAL-01 remains the device-failure case).
**Check:** when the list changed, `test_same_symptom_different_causes`
failed as expected; after fixing the data, `uv run pytest` green (45).
**Consistency:** the tests read the P1–P4 rules and the list of critical services from
CLAUDE.md and require them to match the policies.
**Rejected:** —

## Milestone 2 — Command `/state-and-tools`
**Command launched:** I asked Claude Code for a draft of `.claude/commands/state-and-tools.md`
(state.py, model.py, tools.py and their tests) following the format of data-and-docs.
**Draft decisions I accepted:** `HFModel` is left for milestone 6 and
`search_docs` for milestone 3 (no getting ahead of milestones); a `Network` class that loads the JSON
from a path and applies changes only in memory (tests do not dirty
`data/`); confirmation and guardrail outside the tools (they belong to the orchestrator).
**Improvements Claude proposed and I accepted after reviewing them:**
1. `create_tools(network)` keeps the CLAUDE.md signatures, and `execute(...)`
   is the only call point: nonexistent tool or malformed arguments
   → `ToolError`, checking the signature with `inspect.signature().bind` so as
   not to hide internal failures. Reason: the orchestrator only catches one error type (R4).
2. Fields of `Result` fixed (`final`, `answer`, `citations`, `trace`, `type`,
   `priority`, `escalation`), because CLAUDE.md did not list them and the evaluation of
   milestone 7 checks `final`, type and priority.
3. Each `Network` with its own copy of the data and an isolation test, so that
   the maximum of 1 restart per service does not leak between runs.
**Rejected / postponed:** `parameters` in the registry (to be seen in milestone 4, when
writing the prompts) and `Literal` types (minor improvement).

## Milestone 2 — State, simulated model and tools
**Command launched:** `/state-and-tools`.
**What was done:** `state.py` (Step, Action, State, Result), `model.py`
(`Model` Protocol and `ScriptedModel`, which stores the calls it receives),
`tools.py` (`Network`, `ToolError`, `Tool`,
`create_tools`, `execute` and the 6 tools; `search_docs` is left
for milestone 3). Tests: `test_state.py`, `test_model.py`, `test_tools.py`.
**Implementation decisions:** each tool is bound to its `Network` with
`functools.partial` and keeps the CLAUDE.md signature; arguments are
validated as text, so that a list or a number sent by the model gives
`ToolError`; `create_escalation` accepts `ticket=None` (the ticket is
optional); every tool returns a `dict` (`search_tickets` →
`{"tickets": [...]}`).
**Check:** `uv run pytest` green (84 tests, 45 from test_data).
Key tests: `execute` turns a nonexistent tool and extra or missing
arguments into `ToolError`, but does not hide an internal `TypeError`;
two `Network`s do not share data; the SHA-256 fingerprint of `data/*.json` does not change
after restarting, closing and escalating.
**Rejected:** —

## Milestone 3 — BM25 retrieval and `search_docs`
**Command launched:** draft of `.claude/commands/bm25-retrieval.md` written by Claude
Code at my request; I reviewed it (what BM25 is, what the milestone is for, why
an agent is not brought forward) and launched `/bm25-retrieval` unchanged.
**What was done:** `retrieval.py` (tokenize, chunk by `## ` sections,
hand-written `BM25Index`, `citation`), `search_docs` as the 7th tool in the
registry (`{"fragments": [...]}`, reversible, k between 1 and 10) and an index
injectable into `create_tools(network, index)`. Tests in
`test_retrieval.py` and an extension of `test_tools.py`.
**Decisions:** retrieval unit = section, with the document title
to tell apart sections with the same name; citation `docs/<file>.md#<section>`;
no accents and no stop words; k1=1.5, b=0.75; ties broken by doc and section.
Why BM25 and not embeddings: no dependencies or network, deterministic and explainable.
**Problem:** "restart a critical service during business hours" hit
`restart-policy.md` by a very small margin (×1.02 against `kb-printer-02.md`,
which also talks about restarting during business hours) and "restart" (noun) ≠ "restart" (verb).
**Solution:** light stemming (no plural or final vowel, 6 letters) and
title with weight 3. Claude tried 12 combinations (stem length × weight) over
12 queries and I accepted the one with the largest minimum margin: now ×1.27 and ×1.46. New test
`test_restart_policy_margin` (requires ≥ 1.2; it failed with the previous code).
**Accepted cost:** "response times by priority" drops from ×2.3 to ×1.17
because "time" matches `escalation-procedure.md`; it still hits.
**Known limitation:** BM25 does not understand synonyms ("offline" ≠ "I
have no internet"); mitigated with the employees' expressions in `## Symptoms`.
**Check:** `uv run pytest` green (124 tests).
**Rejected:** bringing the knowledge agent forward to this milestone (it is done at the
start of milestone 4, together with the common agent loop).

## Milestone 4 — Agents
**Command launched:** draft of `.claude/commands/agents.md` written by Claude
Code at my request; first I asked it to explain what each agent does, and I launched
`/agents` unchanged.
**What was done:** `agents.py` with the common loop (`run_agent`), the
definition of the 4 agents as data (`AGENTS`), the prompt generated by
code and the functions `classifier`, `diagnosis`, `knowledge` and
`escalation`. Tests in `test_agents.py`. Work order: first loop +
knowledge (vertical slice, 19 tests green) and then the other three.
**Decisions:**
- Protocol: a single JSON per turn, either a call `{"tool", "arguments"}`
  or a final output with the contract keys; it is accepted inside ```json.
- Irreversible tools are never executed in the loop: knowledge proposes them in
  `action` and, if it calls them as a turn, they are blocked and it is warned. This way the
  confirmation and the guardrail of milestone 5 cannot be bypassed.
- The prompt is generated from the registry (signature with `inspect.signature` and
  description) and only shows the tools the agent is allowed to use.
- A broken contract (missing keys, `type` or priority out of range) counts
  as an unreadable response; 2 in a row → `reason="unreadable"`.
- Blocked calls stay in the trace with `tool=None`, so that they never
  look executed (rule 1).
- Escalation: if the agent does not create the escalation, the code creates it from its output
  (without ticket if the one in the state does not exist); it is never duplicated.
- The classifier's priority is stored as is; raising it belongs to milestone 5.
**Check:** `uv run pytest` green (160 tests).
**Problem:** a double `cat >> ... <<'EOF'` in a single Bash command failed
without writing anything; the code was added with the editor.
**Rejected:** having the classifier already correct the priority from the data (left
to the orchestrator, which has the information from all the agents).

## Milestone 5 — Command `/orchestrator`: decision on `rejected`
**Problem:** CLAUDE.md was ambiguous: with a rejected action it said "final
`escalated` or `rejected`", but the handoff rules said "→ escalation".
**My decision:** if the user rejects the action or does not agree with it, it is
escalated to second level until a coherent solution is found; `rejected`
only when the input is not valid (nonexistent office or ticket) or the
request is not office support. For the latter the type
`out_of_scope` is added (different from `other`, which is support without a category).
Updated CLAUDE.md and the milestone 5 command.
**Known risk:** detecting `out_of_scope` depends on the model; a false
positive would lose a valid incident.
**Rejected:** having an action the user rejects end in `rejected`: it would leave the employee without a solution; it is escalated.

## Milestone 5 — Orchestrator and rules R1–R5
**Command launched:** `/orchestrator` (Claude Code draft with my decision on
`rejected` and the `out_of_scope` type, see previous entry).
**What was done:** `orchestrator.py` with `orchestrate()` (CLAUDE.md signature plus
optional `network` and `index` for tests), `guardrail`, `minimum_priority`,
`raise_priority`, `check_citations`, `in_business_hours`, `trajectory` and the
answer to the employee written by code. Adjustments in `agents.py`: type
`out_of_scope`, `Step.n` = position in the trace, orchestrator notes in
the initial message and `ensure_escalation` made public. Tests in `test_orchestrator.py`.
**Decisions:**
- The minimum priority is computed with the diagnosed service (not with
  any service of the office); it is only raised, never lowered.
- Orchestrator notes stay in the trace but do not count towards the limit.
- Escalation never lowers the state's priority (`create_escalation` is wrapped),
  so the multi-office outage comes out with P1 even if the agent proposes P2.
- Extended guardrail: a service of another office is never restarted, maximum 1
  restart per service always, and only the incident's ticket is closed.
- If the escalation agent does not respond properly, the code creates the escalation with an
  automatic summary: there is always an id.
**Check with mutations:** Claude deliberately broke each rule (R1 without
confirming, R2 without guardrail, R3 without the limit before the action, R4 without escalating
unreadable responses, R5 without checking citations, priority not raised, reopened not escalated)
and I checked that tests fail. Checking the limit before executing the
action was caught by none: I added `test_r3_limit_before_executing_the_action`.
**Result:** `uv run pytest` green (198 tests).
**Rejected:** —

## Milestone 6 — Real model and command line
**Command launched:** `/cli-and-hf-model` (Claude Code draft, launched unchanged).
**What was done:** in `model.py`, `HFModel` (InferenceClient, `temperature=0`,
`max_tokens=512`, token from `.env` with python-dotenv) and `SimulatedModel`
(deterministic rules to use the program without a token); `cli.py` with
`argparse` (`--office`, `--ticket`, `--model simulated|hf`, `--trace`) and
terminal confirmation "[y/N]" (EOF = no); the `pyproject.toml` script
points to `office_support.cli:main`. Tests in `test_model_hf.py` and
`test_cli.py` with a fake client: none uses the network or reads `.env`.
**Decisions:**
- `SimulatedModel` because CLAUDE.md reserves `ScriptedModel` for tests and
  `--model simulated` needed to work on its own. It does not imitate the safety
  rules: the orchestrator keeps applying them.
- Without an interactive terminal, `confirm` returns False (for safety).
- The model error goes to stderr with exit code 2, without a Python traceback and with
  the token replaced by `***`.
**Check with the simulated model:** "I have no internet" in MAD-01 → asks,
"y" → restarts vpn → `resolved` with citation `kb-network-01.md#Steps` (9 steps, raises
P3→P1); "I can't log in to the ERP" in MAD-02 → `escalated` P1, ESC-0001.
**Real test with Hugging Face:**
`uv run office-support "I have no internet" --office MAD-01 --model hf --trace`
→ `402 Payment Required: You have no remaining credits` with
`Qwen/Qwen2.5-72B-Instruct`. The program responded as it should: clear message,
no token, exit code 2.
**Improvement after the error:** the 402 was also being retried (a useless call).
Now only transient failures are retried (network, 429, 5xx); test
`test_only_retries_transient_failures` (401/402/404 → 1 call; 429/5xx → 2).
**Pending:** ask the professor how to get credits (or whether the
course provides them) and repeat the real test; then confirm the default
model in CLAUDE.md (now marked "pending verification"). Alternatives
considered: wait for the monthly renewal, an own key from a provider (e.g.
Groq) in the Inference Providers settings, or local Ollama via `base_url`.
**Result:** `uv run pytest` green (239 tests).
**Rejected:** — (command launched unchanged).

## Review 1 — CLAUDE.md and permissions
**Context:** the assignment says that CLAUDE.md, the permissions, the commands and the
tests are written by the student. Since milestone 2 I had delegated a lot of
drafting to Claude Code, so I review everything from the beginning. Method:
Claude asks me section by section, I decide, Claude drafts my decisions
and I review the result.
**Reviewed and validated** (Claude's original wording, in line with my
judgement): first-level goal with escalation to second level; input and output;
dependencies; tests without network or token; token only in `.env`; 4 agents with
least privilege; handoff; reopened ticket → escalation; outage in several
offices → escalation P1; no citations, no "resolved"; knowledge only proposes
irreversible actions; extended guardrail (never another office, only the
incident's ticket, max. 1 restart per service); priority is only
raised; limit of 12 steps and 2 unreadable responses → escalation.
**My reasons:**
- No agent framework: I control and understand all the code; the loop and the
  safety rules are mine and I can explain them.
- Handoff: support is a sequential flow; a solution cannot be given
  without first knowing the incident and its cause.
- Reopened ticket: if it was already tried and could not be fixed, second level must assess it.
- Human confirmation: the machine may not know everything or may be wrong.
- Limit 12 / 2 unreadable: avoids loops and limits credit spending; to be
  revisited after the test with the real model.
**Changes I decided:**
1. Streamlit web **published with a link** so the professor can try it without
   downloading anything. `streamlit` becomes an allowed dependency only for `app.py`
   (resolves the contradiction in CLAUDE.md).
2. The public web uses only the simulated model: with the real one, anyone with the
   link would spend my credits. The real one is only shown locally.
3. Explicit "Out of scope" and what the employee is told if it is not resolved.
4. The real model is only used when I ask for it.
5. "Way of working": authorship (I decide, Claude drafts and I review) and git
   (one commit per milestone or block; I do the push).
6. The evaluation cases and their expected result are defined by me without looking at the
   code (independent oracle).
7. `settings.json`: `Read(./.env)` did not prevent `cat .env` from the terminal nor
   deleting with `del`/`Remove-Item`. Added to deny `cat|type|more|head|tail|
   less|Get-Content .env*` and `del`, `rmdir`, `Remove-Item`.
**Check:** `cat .env.noexiste` and `del archivo_que_no_existe.txt`
denied by settings (nonexistent files, no risk of reading the token);
`uv run pytest` green (239); CLAUDE.md 173 lines.
**Learned:** creating another token does not give more credits (they belong to the account, not the
token); the 402 is not retried because it is a permanent error.
**Known limitation:** permissions are a barrier, not a guarantee: a
`uv run python` could read `.env`, but it is in "ask" and I would see it.
**Open questions:** web platform (milestone 8); HF credits for the
real test.
**Rejected:** an agent framework (I could not explain the loop); an HTML page on claude.ai instead of Streamlit (it would not run my real Python code nor be in the repository); the real model on the public web (anyone would spend my credits); raising the limit to 15 or lowering it to 10 (12 is kept until measured).

## Review 2 — Commands of milestones 2 to 6
**Context:** the commands `state-and-tools.md` to `cli-and-hf-model.md` were drafted by Claude Code at
my request. I have reviewed them one by one: Claude explained every decision it
had made without asking me and I accepted or changed it. The commands
stay as they were launched (they are the record of what was asked); what I change
is applied in later milestones.
**Milestone 2 — accepted:** changes only in memory (each run starts from the
initial state; the demo always starts the same); `execute` as the only call
point with a single error type (R4); confirmation and guardrail in the
orchestrator, not spread across the tools.
**Milestone 3 — accepted:** hand-written BM25 instead of a library or embeddings (no
dependencies, deterministic and explainable), with the limitation that it does not understand
synonyms; fragment = section, for precise citations; no accents or stop
words, light stemming and title with weight 3. I validate the table of 7 test
queries. Learned: these tests check an isolated piece; the web tests
the whole system and the search engine is visible in the trace and in the citation.
**Milestone 4 — accepted:** prompt generated by code (it never announces a
forbidden tool); each agent receives a summary of what has been found out and not the
whole conversation (fewer credits and less confusion); escalation always
ends with an id even if the model fails (safe degradation).
**Milestone 5 — accepted:** the answer to the employee is written by the code from a
template (the model cannot promise false deadlines) and I validate the times
P1 15 min, P2 30 min, P3 2 h, P4 1 business day; the minimum priority is
computed only with the diagnosed service; orchestrator notes do not
count towards the limit.
**Milestone 6 — accepted:** without a terminal to confirm, the answer is "no";
I keep `Qwen/Qwen2.5-72B-Instruct` until testing it with credits.
**Milestone 6 — change I decided:** `SimulatedModel` is the one the public web
will use and it has two visible gaps: it classifies "can you recommend a
restaurant?" as `other` instead of `out_of_scope` and it does not recognise sentences without
its keywords ("I'm offline"). It is improved in milestone 8, before
publishing the web; the safety rules do not change because they belong to the orchestrator.
**Rejected:** leaving the simulated model with its gaps (the professor will see it on the web); starting with a small, cheap HF model (I keep the 72B one).

## Milestone 7 — Evaluation with my cases
**Command launched:** `/evaluation`. It replaces an earlier Claude draft: the
case table and the expectations are mine. Claude drafted the command from my
table and implemented `evaluation.py` and `tests/test_evaluation.py`.
**How I defined the expectations:** I applied my rules with a 7-question method in
order (valid input? is it support? type, priority, reopened or several
offices?, is there an article?, irreversible action and confirmation?). While applying it
I got three cases wrong and corrected them when reviewing the rule: in case 1 I put P3
(the vpn down is a critical service down → P1), in case 6 I put P1 (email is
degraded, not down → P2) and in case 10 I thought it was restarted (the guardrail
blocks without asking because the erp is not the diagnosed service).
I added case 11 ("my computer is slow") after trying the program with a
sentence of my own: the simulated model marked it resolved citing the network card
article.
**Cases:** 11 (happy paths, the three hard ones from the assignment, priorities raised
by the code, R1, R2, R5, invalid input, out of scope and mine). Each one
with two passes: script (`ScriptedModel`, checks my rules) and
`SimulatedModel` (what a user without a token would see). No real model: it would spend
credits.
**Result:** with script 9/11; with the simulated model 6/9. The failures are left as
`xfail` with their reason, without changing the expectations or the code:
- Script 7: an out-of-scope rejection keeps the classifier's P4
  priority. **Code bug**: what is not processed has no priority.
- Script 11: there is no article on slow computers; the citation is removed (R5) and it is
  escalated. **Missing content** in `docs/`.
- Simulated 4: escalates correctly but with P3 (the simulated model always starts at P3).
- Simulated 7: treats the restaurant as `other` and "resolves" it.
- Simulated 11: gets the final right by chance (resolved, C-D-K) with the wrong type,
  priority and article. Proof that the trajectory and the data must also be
  evaluated, not only the final.
**Check:** `uv run pytest` → 260 green and 5 `xfail`;
`python -m office_support.evaluation [--model simulated]` prints the table.
**Decisions for milestone 7b:** rejected without priority (D1); article
`kb-hardware-03`; simulated model with more keywords, `out_of_scope`, P4 for
printers (D2) and not citing articles of another type.
**Rejected:** Claude's draft of cases (circular evaluation: the same author defines the code and what is correct); evaluating with the real model (it would spend credits); changing the expectations or the code so that the cases pass.

## Milestone 7b — Fixes after the evaluation
**Command launched:** `/evaluation-fixes`, drafted by Claude with my decisions on
the 5 failures of milestone 7. Rule: fix the cause, never change the expectations.
**Decisions (mine):**
- D1: a rejection has no priority (what is not processed is not prioritised).
  It was a code bug found by my case 7.
- Article `kb-hardware-03.md` "The computer is slow" with my procedure:
  restart, close programs and, if nothing changes, contact the technical team.
- SimulatedModel (the web will use it): more hardware words; `out_of_scope`
  if it fits no type and does not sound like support; initial P4 for printers
  (D2: there is usually another one available); does not cite articles of another type.
**Claude's proposal that I accepted:** in the simulated model, initial P4 if the
incident talks about slowness ("slow", "takes long", "freezes"), applying my
definition of P4 (an inconvenience with an alternative). The orchestrator still raises it
from the data: in case 6 email starts at P4 and ends at P2.
**Check:** the `xfail(strict=True)` marks flagged each fix
(XPASS) and were then removed. Evaluation: script 11/11, simulated 9/9.
New tests: rejection without priority, search "my computer is slow" →
`kb-hardware-03`, classification and initial priority of the simulated model, and that it does not
cite an article of another type. `uv run pytest` → 276 green.
**Known limitation:** the simulated model still works by keywords; a
sentence without any known one may end up in `out_of_scope` by mistake. With
the real model the classifier decides.
**Rejected:** accepting that a rejection has P4 (option b of D1); leaving the simulated model's failures as a limitation without fixing them.

## README — exact run instructions
**What was done:** README with installation (`uv sync`), tests, running,
four examples, evaluation and optional use of the real model. Drafted by
Claude with my decisions.
**Decisions (mine):** the examples show human confirmation and the three
hard cases from the assignment. My first proposal (internet in MAD-02, ERP
in VAL-01…) did not fit the data: I ran it and saw that the vpn down is in
MAD-01 and the ERP down in MAD-02 and BCN-01, so I adjusted it. The real model is
explained, but everyone uses their own token in their `.env`: mine is not handed in.
**Check:** ran every command in the README as written; each gives what
its comment says.
**Rejected:** my first examples (internet in MAD-02, ERP in VAL-01), because they did not fit the data; including my token or my `.env`.

## Report (draft)
**What was done:** `report.pdf` (3 pages for now) generated with
`report/generate.py` (`uv run --no-project --with reportlab`, so as not to add
dependencies to the project). Drafted by Claude from my decisions in
this review; under my name and with my own design, without the institutional template.
**Structure:** problem and scope; architecture (agents, handoff, state and
messages); tools and BM25; R1–R5 and permissions; tests and my evaluation
(with the findings of the first pass); two real traces; way of working
and limitations. It follows the point distribution of the assignment.
**Pending:** the two real traces (`report/trace1.txt` and `trace2.txt`)
when there are HF credits; the script inserts them by itself.
**Rejected:** using the institutional template: the report is under my name with my own design.

## Milestone 6b — Real model locally (Ollama) and report traces
**Problem:** the HF account gave `402 Payment Required`. Following what the
professor said in class (more accounts or Ollama), I created a second account with
an inference-only fine-grained token: also `402 … no remaining
credits`. HF no longer gives free credits, so more accounts do not help.
**Decision (mine):** Ollama locally, without paying. I checked first that my machine
can handle it (31 GB of RAM, RTX 3050 Ti, 388 GB free) and that the professor does not
need it: tests, README and web use the simulated model; Ollama is optional.
**Command launched:** `/ollama-model`, drafted by Claude with my decisions.
`OllamaModel` reuses `HFModel` (same protocol, `temperature=0`,
retries) against `localhost`, without a token; `--model ollama`. HF stays intact.
**First real test (qwen2.5:7b):** both traces ended escalated. The
model returned JSON outside the contract (nonexistent service, evidence as
text) → R4 escalated after 2 unreadable; it did not call tools; and it made up
citations (`docs/red.md#…`) → R5 removed them. The rules prevented any harm,
but the system resolved nothing. Saved in `report/trace*_before.txt` and
`report/trace1_7b_improved_prompt.txt`.
**Cause:** the prompt did not state the exact format, the allowed values, that
it must check before concluding, what each service is (the model chose
`guest_wifi` for "I have no internet") nor that knowledge must start
with `search_docs`. I had anticipated it in milestone 4 ("dry" prompts).
**Solution (decided by me, option a):** each agent's prompt includes its
exact format generated from the same lists the code validates; the
diagnosis receives the service descriptions (the same as the catalog, checked
by a test) and knowledge always searches first. The validation in
code does not change: safety still does not depend on the prompt. With the 7B
the format improved but it still did not use tools; I moved to qwen2.5:14b.
**Adjusted test (explained):** `test_knowledge_prompt_separates_proposable`
looked for "restart_service" in the whole prompt; now it legitimately appears
in the format of `action`. It is limited to the list of callable tools, which
was what it was meant to check; the rule does not change.
**Result with qwen2.5:14b:** trace 1 ("I have no internet", MAD-01): checks
the vpn, raises P2→P1, searches and cites kb-network-01, proposes the restart, I confirm and
resolved (C-D-K): my case 1. Trace 2 (ERP, MAD-02): checks the erp, the code
detects the outage in MAD-02 and BCN-01 and escalates with P1 (C-D-E): my case 5.
**Limitation observed:** the escalation agent puts in "tried" things nobody
tried ("restart browser"). It is not dangerous, but it is inaccurate.
**Check:** `uv run pytest` → 289 green (without Ollama or network). Report
regenerated with the two traces (4 pages). While regenerating it, `settings.json`
blocked an `rm` of temporary images: the permission works.
**Rejected:** paying for HF credits; waiting to talk to the professor (risky with the deadline in two days); keeping the failed 7B traces (option b); forcing tool calls in code (option b: more risk two days before the deadline).

## Report — my review
After reading it I asked for two changes: a table with the P1–P4 priorities (criterion,
example from the data and first response time) and a "Language
models" section clarifying which model is used for what (tests, simulated, Ollama
for the traces and optional HF) and why not HF. It stays at 4 pages.
**Rejected:** —

## Review 3 — Comparison with the full assignment
**What I did:** I compared the project with all the slides of the assignment.
**Meets:** R1–R5, submission (CLAUDE.md < 200 lines, README, 4-page
report, zip without `.env` that starts clean) and the minimums of topic 2.
**Missing and corrected:**
1. R6 asks for one trace within the domain and one outside it: both were within the domain.
   I replaced the ERP one (saved in `report/trace_erp_domain.txt`) with
   "can you recommend a restaurant…?" with qwen2.5:14b: rejected, out of
   scope, without priority (my case 7).
2. Several entries in this worklog did not say what was rejected; added.
3. Commands without `disable-model-invocation` or `allowed-tools`, and without saying what
   I review (see below).
4. Permissions without deny on `CLAUDE.md` and `.claude/` (see below).
**Differences I keep and why:**
- I did milestone 0 by hand (`uv init --package`, permissions and CLAUDE.md), without
  a `/setup` command; I do not invent one after the fact.
- The project is packaged (`uv init --package`), although the slide talks about
  an unpackaged project: the `office-support` command in the
  README needs it, and changing it two days before the deadline puts the startup at risk.
- The irreversible action is simulated in memory (it touches no real system)
  instead of writing to a file: this way every run and every test starts from the
  same state.
**Commands:** added to all 9 the header `disable-model-invocation: true`
(they are only launched when I ask for them) and `allowed-tools` (only what
each milestone needs: reading and editing code and `uv run pytest`; in milestones 7 and 7b,
also the evaluation table), and a "What I review" section with what
I check in each milestone. Drafted by Claude from this review.

## Milestone 8 — Streamlit web
**Command launched:** `/streamlit-web`, drafted by Claude with my decisions.
**What was done:** `app.py` (display only) and `web.py` (logic without Streamlit,
tested); Streamlit in the optional `web` group, so that `uv sync` and
`uv run pytest` do not need it; light and dark themes in `.streamlit/config.toml`.
**Decisions (mine):** free text + office dropdown + optional ticket
(in a real company the office would come from the login); buttons with my
example cases; confirm with a button; simulated model by default, because it is
faster; a real Ollama model only if it works on the machine, to
show it locally at the defence.
**Bugs I found when testing it by hand:**
1. "Handle incident" broke the page (`StreamlitWidgetAlreadyInstantiatedError`):
   it rewrote form fields that were already drawn. A test that reproduces it
   (`test_form_typed_by_hand`) and a fix with a callback.
2. "I don't know how to turn off the printer" gave as procedure the
   «Cause» section of the paper-jam article. The simulated model used any section if there
   was no «Steps»; now only «Steps» is a procedure and, if there is none, it is escalated.
**Bugs that came up when testing the real model on the web:**
3. Confirming by repeating the run with the answer does not work with a real
   model: the second time it ended escalated instead of resolved. Now it is a
   single background run that waits for the button, like the [y/N].
4. If the run finished without asking and an answer was given anyway, it
   hung. `respond` does nothing if there is no question (with a test).
**Design (requested by me):** no emojis or gradient, selectable light and dark
mode, a single accent colour (darker in dark mode) and an
explanation of each final and priority, with the same texts as
`priority-guide.md` and the same times as the orchestrator (checked by a test).
**Check:** `uv run pytest` → 315 green; the page tests
(`test_app.py`, with `streamlit.testing`) are skipped without the `web` group and pass with
`uv run --group web pytest`. Real model on the web: a 98 s run
with qwen2.5:14b → asks → I confirm → resolved P1.
**Rejected:** an HTML page on claude.ai (it does not run my code); repeating the
run to confirm (non-deterministic with a real model); the first
design with emojis and gradient; the real model on a public web.

## Final permissions — lock on the specification
**What I did:** I wrote by hand in `.claude/settings.json` the edit and
write deny on `CLAUDE.md`, `.claude/` (permissions and commands), `docs/` and
`data/`, as H0 of the assignment requires: Claude Code cannot touch my
specification or the original documents and data. I added it at the end because
until then Claude drafted those files with my decisions.
**Check:** Claude tried to edit `CLAUDE.md`, create a command in
`.claude/commands/` and a file in `docs/`: all three blocked ("denied by
your permission settings"). It cannot remove the lock either: `settings.json`
is inside `.claude/`. If something needs to change, I edit it myself.
**Rejected:** —

## Final clean check (done by me)
**What I did:** as the professor will: I unzipped the submission zip with
Windows Explorer into a new folder on the Desktop (without `.env` or
`.venv`), opened a terminal there and followed the README: `uv sync`, `uv run pytest`
and `uv run office-support "I have no internet" --office MAD-01 --trace`,
answering "y"; I also started the web with
`uv run --group web streamlit run app.py`.
**Result:** everything worked: tests green (the web page tests are
skipped without the `web` group, as intended), the README command ended
resolved with P1 and its trace, and the web opened and responded.
**Rejected:** —

## Translation to English (2026-10-19)
**Why:** the professor asked for the whole project in English. Decided by me;
drafted and implemented by Claude Code from a glossary we agreed on
(one name per concept, used in code, data, docs, tests and prose).
**What was done:** everything translated as if it had been written in English:
package `soporte_oficinas` → `office_support`, command `office-support`,
modules (`state`, `model`, `tools`, `retrieval`, `agents`, `orchestrator`,
`evaluation`…), JSON contracts, data (`services.json`, `inventory.json`),
docs (`kb-network-01.md#Steps`…), tests, CLAUDE.md, commands
renamed after what they do (`/data-and-docs`, `/orchestrator`, `/streamlit-web`…), README, this worklog, the web and `report/`. Renames done with
`git mv`; as almost every line changed, git shows most of them as a deleted
file plus a new one. The Spanish history is kept in the `spanish-version` branch. The GitHub repository keeps
its name (`soporte-oficinas`) so the link already shared still works.
To let Claude edit them, I removed the deny on `CLAUDE.md`, `.claude/`,
`docs/` and `data/` for the translation and put it back afterwards.
**Problems and solutions:**
1. BM25 was tuned for Spanish. New English stop words and a light stemmer
   (-ing, -ed, plural, final e; 6 letters), with the stem tests rewritten
   ("restart/restarts/restarting/restarted"). The 11 quality queries rank the
   expected document first.
2. The restart-policy margin fell to ×1.15 (< 1.2) because the English catalog
   repeated "business hours". The catalog note was reworded; the test was not
   changed. Margins now ×1.24 and ×1.43 over `kb-printer-02.md`.
3. Simulated model keywords rewritten in English; the tokenizer drops
   apostrophes ("can't" → "cant") so "Can you recommend a restaurant?" stays
   `out_of_scope`.
4. Real traces re-run in English with qwen2.5:14b (not translated by hand).
   Trace 2 and the ERP trace behave as in Spanish. Trace 1 does not: the
   knowledge agent skipped `search_docs` and cited a document it never
   retrieved; R5 removed the citation and the run was escalated with P1
   instead of resolved. The code rules held; the prompt rule "first turn is
   ALWAYS search_docs" is not enough in English. The report says so. The
   older traces (`*_before.txt`, 7b) are archived Spanish runs, translated and
   labelled as such.
**Check:** `uv run pytest` → 314 green (one confirmation case fewer: Spanish
had "si" and "sí", English only "y"/"yes"); `uv run --group web pytest
tests/test_app.py` → 6 green; the README commands run with the simulated model.
**Rejected:** rewriting the git history in English (it needs a force push;
old commits stay in Spanish); translating the real traces by hand (they would
no longer be real); the React web and live trace, postponed after the deadline.

## Milestone 9 — React web console
**Why:** the professor suggested a more professional web where the agents can
be seen working. Decided by me after the translation; command
`/react-console` and code drafted by Claude Code with my decisions.
**What was done:** `orchestrate(..., on_step=)` streams each step as it enters
the trace (`Trace(list)` in `state.py`); `web.py` adds the live steps, a JSON
snapshot of the run and what each step is (tool call, answer, orchestrator
note…) and which rule it shows; `server.py` (standard library, 127.0.0.1 only)
serves the page and a small JSON API; `static/` holds the React console:
pipeline of the four agents with their tools and findings, R1–R5 badges that
light up when a rule acts, live trace, step counter against the limit, R1
confirmation modal, result with priority, escalation and citations, network
status, light and dark themes and `?example=N` links.
**Decisions:** React 18 + htm from a pinned CDN (no Node, no build, no new
Python dependency); polling instead of WebSockets; the page replays the steps
at a readable pace because the simulated model answers instantly. Streamlit
stays as an optional alternative.
**Check:** 14 new tests (live steps, R1 in the stream, JSON views, note rules,
the server over real HTTP: confirm → resolved, reject → escalated, path
traversal blocked, 400/404) → `uv run pytest` 328 green (341 after the
safety rule below). Screenshots with headless
Chrome of the empty page, the confirmation modal, the multi-office escalation
and a resolved case, in dark and light themes.
**Found:** with the simulated model, "I have no internet" in VAL-01 is resolved
citing `kb-network-01.md#Steps` (VPN) instead of `kb-network-02.md` (network
card). The Spanish version did the same (`kb-red-01`): it is a limit of the
keyword-based simulated model, not of the translation; my evaluation case 3
(scripted) cites `kb-network-02` and passes.
**Found by me in the console:** "The printed had exploded" was resolved with the
paper-jam steps: the simulated model only looked at the word "print". Physical
repairs are not first level, so now, if the incident describes physical damage
(explosion, fire, smoke, sparks…), the simulated diagnosis says so, knowledge
gives no procedure and the orchestrator escalates (test with 3 incidents).
The Spanish version had the same fault. Then I decided a new rule, guaranteed in
code: a safety hazard (explosion, fire, smoke, sparks, burning) raises the
priority to at least P2 and goes straight to escalation after the diagnosis,
whatever the model says. Added to CLAUDE.md, `priority-guide.md` and
`escalation-procedure.md`; 9 tests (words that are and are not a hazard, e.g.
"firewall" is not; P4 → P2 with escalation; P1 is never lowered).
**Rejected:** Node + Vite build (another toolchain to install for whoever
corrects it); WebSockets (polling is enough and simpler to test); removing the
Streamlit web.

## Final review of README, report and docs
**What was done:** README updated (React console, safety-hazard example,
English incidents, Ollama 14b for the report traces, commands by name, number
of tests); `report.pdf` regenerated (341 tests, safety hazard in priorities and
handoff, milestones 0 to 9, web console in "Reproduce"; still 4 pages); a
"Safety hazard" example case in the web. Drafted by Claude Code at my request.
**Check:** `uv run pytest` → 341 green; `uv run --group web pytest
tests/test_app.py` green; the README commands run.
**Rejected:** —
