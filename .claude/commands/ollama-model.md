---
description: Milestone 6b — local model with Ollama for the real traces
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(uv run pytest:*)
---
# Milestone 6b — Local model (Ollama)

Read CLAUDE.md (section "Model contract") and `HFModel` in `model.py`.
In this milestone agents, orchestrator and rules are NOT changed, `.env` is NOT
touched and NO dependencies are added (Ollama is used through `huggingface_hub`, which is already there).

## Goal
Run the system with a real language model on my computer
(`--model ollama`) to produce the two real traces for the report.

## Context
Two Hugging Face accounts return `402 Payment Required: You have no remaining
credits`: HF no longer gives free credits. The lecturer said in class that,
without credits, we should use more accounts or Ollama. The accounts do not help; I use Ollama.

## Decisions (mine)
- `OllamaModel` reuses `HFModel` (same `generate`, `temperature=0`,
  `max_tokens=512` and retry only on transient failures) with
  `InferenceClient(base_url=...)` pointing to the local Ollama server, which
  speaks the same protocol. No token.
- Default model `qwen2.5:7b` (same family as the HF one, good JSON,
  fits on my machine). Configurable with `OLLAMA_MODEL`; address
  with `OLLAMA_URL` (default `http://localhost:11434/v1`).
- `HFModel` stays intact: if I get credits, `--model hf` works the same.

## Acceptance criteria
1. `OllamaModel(client=fake)` does not need `HF_TOKEN` and sends the model
   name in every call, with `temperature=0` and `max_tokens=512`.
2. `OLLAMA_MODEL` changes the model; without the variable, `qwen2.5:7b`.
3. `--model ollama` in the CLI creates an `OllamaModel`.
4. CLAUDE.md and README explain the option; the tests do not need Ollama
   installed (fake client) and still use no network.
5. `uv run pytest` green.

## When done
Criterion → test table. Do not commit.

## What I review
1. That `--model hf` stays the same and the tests do not need Ollama.
2. The real traces: response format, tool use and final.
3. That the improved prompt comes from the same lists the code validates.
