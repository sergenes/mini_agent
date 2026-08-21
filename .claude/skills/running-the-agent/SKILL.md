---
name: running-the-agent
description: >-
  How to run mini_agent locally, remotely, or in mixed mode, including Ollama,
  env vars, MCP, interactive REPL, and provider fallback. Use when running
  agent.py, adding a provider, debugging tool calling, or setting up .env.
---

# Running the agent

```bash
source .venv/bin/activate
cp .env.example .env   # add API keys first

# Local (Ollama: ollama serve)
python agent.py --mode local --local-model mistral-nemo "What is 15% of 847?"
python agent.py --mode local "What is 15% of 847?"

# Remote
python agent.py --mode remote --provider openai "Explain ReAct agents"
python agent.py --mode remote --provider anthropic --model claude-sonnet-4-6 "..."
python agent.py --mode remote --provider gemini "..."

# Mixed: local orchestrates, ask_remote() hits the cloud
python agent.py --mode mixed "What's today's date and explain quantum entanglement"

python agent.py --mode local --interactive
python agent.py --mode remote --quiet "What is 144 * 37?"
```

## File roles

| File | Role |
|---|---|
| `agent.py` | CLI: argparse, REPL, mode dispatch |
| `core.py` | `run_agent`, `run_agent_mixed` |
| `reliability.py` | retry, circuit breaker, validation, tracing, fallback |
| `providers.py` | OpenAI, Anthropic, Gemini, Ollama |
| `tools.py` | tools, schemas, `call_tool` |
| `ui.py` | spinner |
| `mcp_server.py` / `mcp_client.py` | MCP demo tools |

Canonical messages list is OpenAI-style. Each provider converts internally. Mixed mode injects `ask_remote` into the local tool list.

Gemini uses the OpenAI SDK against `generativelanguage.googleapis.com/v1beta/openai/`.

## Adding tools

1. Function in `tools.py`
2. `TOOL_FUNCTIONS`
3. OpenAI-format schema in `TOOL_SCHEMAS`

`web_search` and `get_weather` are stubs.

## Keys

| Key | Provider |
|---|---|
| `OPENAI_API_KEY` | OpenAI (Ollama ignores it) |
| `ANTHROPIC_API_KEY` | Anthropic |
| `GEMINI_API_KEY` | Gemini |

Defaults: openai `gpt-4o-mini`, anthropic `claude-haiku-4-5-20251001`, gemini `gemini-2.0-flash`, ollama `qwen2.5`. Function calling works on `llama3.1`, `llama3.2`, `qwen2.5`, `mistral-nemo`. Skip `phi3` and `deepseek-r1` for tools.

`--fallback MODEL [MODEL …]` tries models in order when structured tool calls fail.
