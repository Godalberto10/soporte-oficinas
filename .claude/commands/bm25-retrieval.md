---
description: Milestone 3 — own BM25 index over docs/ and the search_docs tool
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(uv run pytest:*)
---
# Milestone 3 — BM25 retrieval and `search_docs`

Read CLAUDE.md (sections "Tools", "Documents" and rule 5 "Checked
citations").
In this milestone NO agents, orchestrator, `HFModel` or CLI are written. No
dependencies are added: BM25 is implemented by hand (no `rank_bm25`,
scikit-learn or similar).

## Goal
Let the agents retrieve fragments of the knowledge base and cite them in a
format the orchestrator can check in milestone 5.

## Expected files
- `src/office_support/retrieval.py`
- `src/office_support/tools.py` (add `search_docs` to the registry)
- `tests/test_retrieval.py` and extend `tests/test_tools.py`

## Decisions for this milestone
- **Retrieval unit = a `## ` section of a document.** Each fragment
  is `{"doc": "docs/<file>.md", "section": "<section title>",
  "text": "<content>"}`. The indexed text also includes the document's `# `
  title, so that "Steps" in kb-network-01 is distinguished from "Steps"
  in kb-email-01.
- **Citation format:** `docs/<file>.md#<section>`, e.g.
  `docs/kb-network-01.md#Steps`. `citation(fragment) -> str` builds it.
- **Tokenization:** lowercase, accents stripped (`unicodedata`), split on
  anything that is not a letter or digit, and a short list of English stop
  words removed, plus light stemming (`stem`) so that "passwords" and
  "password" match.
- **BM25** with `k1=1.5`, `b=0.75` and IDF `log(1 + (N - df + 0.5) / (df + 0.5))`.
  Fragments scoring 0 are not returned. Ties: by `doc` and
  `section`, so the order is deterministic.
- `create_tools(network, index=None)`: if no index is passed, one is built
  over `docs/`. `search_docs` returns `{"fragments": [...]}` (every tool
  returns a `dict`) and is reversible.
- Recording which fragments were retrieved in each run (for rule 5) is the
  orchestrator's job, in milestone 5. Not here.

## Acceptance criteria
1. `retrieval.py` defines `tokenize(text)`, `chunk(docs_path)` (list
   of fragments), the `BM25Index` class with `from_directory(path)` and
   `search(query, k=3)`, and `citation(fragment)`.
2. `chunk` produces one fragment per `## ` section of every `.md` in
   `docs/`; each `kb-*` article contributes exactly 3 (Symptoms, Cause, Steps).
3. `tokenize("Passwords EXPIRED?")` == `tokenize("password expired")`,
   and stop words ("the", "of", "a", "that"…) do not appear.
4. Correct BM25 on a small test corpus (in `tmp_path`): a rare term
   weighs more than a frequent one, and with the same frequency the shorter
   fragment scores higher. A query with no corpus terms returns `[]`.
5. Quality on the real documents (the first result is the expected one):
   | Query | Expected document |
   |---|---|
   | "I have no internet, the vpn is down" | `kb-network-01.md` |
   | "faulty network card, cable unplugged" | `kb-network-02.md` |
   | "paper jam in the printer" | `kb-printer-01.md` |
   | "expired password, locked account" | `kb-app_access-02.md` |
   | "mailbox full, not receiving emails" | `kb-email-02.md` |
   | "response times by priority" | `service-catalog.md` |
   | "restart a critical service during business hours" | `restart-policy.md` |
6. `search(query, k)` returns at most `k` fragments, sorted from highest to
   lowest score, and the same result in two identical calls.
7. `search_docs` is in the registry with a non-empty description and
   `reversible=True`; `execute(t, "search_docs", {"query": "vpn down"})`
   returns `{"fragments": [...]}` with keys `doc`, `section`, `text`.
8. `search_docs` raises `ToolError` with an empty or non-text query, and with
   a `k` that is not an integer between 1 and 10.
9. The `citation` of every returned fragment has the form `docs/<file>.md#<section>`
   and the file exists.
10. Code in English, typed, short functions. `uv run pytest` green,
    no network and no `HF_TOKEN`.

## When done
Summarize in a table which test covers each criterion. Do not commit.

## What I review
1. The query table: each one returns the document I expect first.
2. The margin of `restart-policy.md` over the second result (≥ 1.2).
3. That every citation has the form `docs/<file>.md#<section>` and the file exists.
