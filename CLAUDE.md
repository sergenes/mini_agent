# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A minimal AI agent built from scratch — no agent framework, just Python, the OpenAI SDK, and a `while` loop. Accompanies the Medium article "Build Your Own AI Agent from Scratch." Three execution modes: `local` (Ollama only), `remote` (cloud provider), `mixed` (local orchestrates, delegates to remote).

## Running the Agent

```bash
source .venv/bin/activate
cp .env.example .env   # add API keys first

# Local (requires Ollama running: ollama serve)
python agent.py --mode local --local-model mistral-nemo "What is 15% of 847?"
python agent.py --mode local "What is 15% of 847?"
python agent.py --mode local --local-model qwen2.5 "What's the weather in Tokyo?"

# Remote
python agent.py --mode remote --provider openai "Explain ReAct agents"
python agent.py --mode remote --provider anthropic --model claude-sonnet-4-6 "..."
python agent.py --mode remote --provider gemini "..."

# Mixed
python agent.py --mode mixed "What's today's date and explain quantum entanglement"

# Interactive REPL
python agent.py --mode local --interactive

# Suppress tool trace
python agent.py --mode remote --quiet "What is 144 * 37?"
```

## Architecture

Source files and their roles:

| File | Role |
|------|------|
| `agent.py` | CLI entry point — argparse, REPL, mode dispatch |
| `core.py` | The agent loop (`run_agent`, `run_agent_mixed`) |
| `reliability.py` | Reliability layer: `with_retry`, `CircuitBreaker`, `validated_call`, `traced_call`, `run_agent_reliable` |
| `providers.py` | Provider abstraction + format converters |
| `tools.py` | Tool implementations, schemas, `call_tool` dispatcher |
| `ui.py` | `Spinner` — thread-safe braille spinner for live terminal output |

**Message format:** The agent maintains a canonical OpenAI-style `messages` list throughout. Each provider translates internally: `_to_openai_messages()` for OpenAI/Ollama/Gemini, `_to_anthropic_messages()` for Anthropic. Tool results are always appended to `messages` before the next LLM call.

**Mixed mode mechanism:** `run_agent_mixed()` builds `mixed_tools = TOOL_SCHEMAS + [_ASK_REMOTE_SCHEMA]` and injects `ask_remote` as an `extra_functions` callable. When the local model calls `ask_remote(task)`, it triggers a fresh `run_agent()` on the remote provider. The local model assembles the final answer.

**Gemini** uses OpenAI's SDK pointed at `generativelanguage.googleapis.com/v1beta/openai/` — no `google-generativeai` package needed.

**Anthropic tool results** must be batched into a single `user` message with `tool_result` blocks — handled in `_to_anthropic_messages()`.

## Adding Tools

1. Write the function in `tools.py`
2. Add it to `TOOL_FUNCTIONS` dict
3. Add its JSON schema (OpenAI function-calling format) to `TOOL_SCHEMAS`

`web_search` and `get_weather` are stubs — replace with real API calls for production use.

## Environment Variables

| Key | Provider |
|-----|----------|
| `OPENAI_API_KEY` | OpenAI + Ollama (ignored by Ollama) |
| `ANTHROPIC_API_KEY` | Anthropic |
| `GEMINI_API_KEY` | Google Gemini |

## Default Models

| Provider | Default |
|----------|---------|
| openai | `gpt-4o-mini` |
| anthropic | `claude-haiku-4-5-20251001` |
| gemini | `gemini-2.0-flash` |
| ollama | `llama3.1` |

Ollama models that reliably support function calling: `llama3.1`, `llama3.2`, `qwen2.5`, `mistral-nemo`. Models like `phi3` or `deepseek-r1` may not.