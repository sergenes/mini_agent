# Mini Agent

A minimal AI agent built without any agent framework — just Python, the OpenAI SDK, and a `while` loop.

This project accompanies the Medium article series by [Sergey Neskoromny](https://www.linkedin.com/in/sergey-neskoromny/):

- **Part 1:** [Building an AI Agent from Scratch: No Magic, Just a Deterministic Loop](https://medium.com/gitconnected/building-an-ai-agent-from-scratch-no-magic-just-a-deterministic-loop-a916161705fb) — the core loop, providers, tools, mixed mode
- **Part 2:** [Your AI Agent Will Fail. Here's How to Make It Recoverable.](https://medium.com/@sergey-nes/781e0db1b5b3) — reliability layer: retry, circuit breaker, schema validation, tracing, and provider fallback


Follow me on [LinkedIn](https://lnkd.in/epTFAmQJ) and [Medium](https://lnkd.in/eNCh6JTE) for more on AI tools, mobile development, and whatever I'm currently building!

---

## What it does

The agent takes a task, calls tools when needed, observes the results, and loops until it has a final answer. Three modes:

| Mode | What happens |
|------|--------------|
| `local` | All LLM calls go to a local Ollama model — fully offline |
| `remote` | All LLM calls go to a cloud provider (OpenAI, Anthropic, or Gemini) |
| `mixed` | Local Ollama orchestrates the loop; it delegates complex subtasks to the remote model via `ask_remote()` |

## Setup

```bash
git clone https://github.com/sergenes/mini-agent
cd mini-agent

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# edit .env and add your API keys
```

For local/mixed mode, install [Ollama](https://ollama.com) and pull a model that supports function calling:

```bash
ollama pull llama3.1       # good default
ollama pull qwen2.5        # strong at tool use
ollama pull mistral-nemo   # lighter alternative
ollama serve
```

---

## Usage

### Local (Ollama only)

```bash
python agent.py --mode local "What is 15% of 847?"
python agent.py --mode local --local-model qwen2.5 "What's the weather in Tokyo and today's date?"
```

### Remote (cloud provider)

```bash
# OpenAI
python agent.py --mode remote --provider openai "Explain how ReAct agents work"
python agent.py --mode remote --provider openai --model gpt-4o "Write a detailed explanation of MCP"

# Anthropic
python agent.py --mode remote --provider anthropic "Write a haiku about Python"
python agent.py --mode remote --provider anthropic --model claude-sonnet-4-6 "..."

# Google Gemini
python agent.py --mode remote --provider gemini "Summarize the ReAct paper"
python agent.py --mode remote --provider gemini --model gemini-2.0-flash-lite "..."
```

### Mixed (local orchestrates, remote handles complex reasoning)

```bash
python agent.py --mode mixed "What's today's date, and explain quantum entanglement in simple terms"
python agent.py --mode mixed --local-model qwen2.5 --provider anthropic "..."
```

In mixed mode the local model decides what to handle itself and when to call `ask_remote()`.
Simple tool calls (calculate, get_date) stay local. Knowledge-heavy tasks go to the cloud.

### Interactive REPL

```bash
python agent.py --mode local --interactive
python agent.py --mode mixed --interactive
```

### With provider fallback (local mode)

Try providers in order; skip models that don't support structured tool calling:

```bash
python agent.py --mode local --fallback llama3.1 mistral-nemo "What is 15% of 847?"
```

If `qwen2.5` (the default) fails or outputs text-based tool invocations, the agent retries with `llama3.1`, then `mistral-nemo`. Each attempt uses the full reliability stack from `reliability.py`.

### Network resilience test (LLM retry)

This demonstrates the reliability layer surviving a real network interruption:

```bash
python agent.py --mode remote --provider openai \
    "Get today's date and the weather in Tokyo."
```

1. Run the command. When you see `Thinking…`, turn off Wi-Fi or disconnect ethernet.
2. The agent retries the LLM call with exponential backoff:
   ```
   WARNING  LLM call attempt 1 failed (Connection error) — retrying in 2.1s
   WARNING  LLM call attempt 2 failed (Connection error) — retrying in 4.3s
   ```
3. Turn Wi-Fi back on. The next attempt succeeds and the agent finishes normally.

The retry is in `_RetryingProvider` inside `reliability.py` — it wraps the provider's `complete()` call so the agent loop never sees the transient failure. Up to 5 attempts, base delay 2 s, doubles each retry.

### Quiet mode (suppress tool trace)

```bash
python agent.py --mode remote --quiet "What is 144 * 37?"
```

### Multi-step example

```bash
python agent.py --mode remote --provider openai "Get today's date and the weather in Tokyo. Calculate how many days are left until New Year's Day 2027. Write a short daily briefing with all three facts to briefing.txt, then read it back and count how many words it has."
```

This triggers six tool calls in sequence: `get_current_date` → `get_weather` → `calculate` → `write_file` → `read_file` → `count_words`.

---

## Default models

| Provider | Default model |
|----------|---------------|
| openai | `gpt-4o-mini` |
| anthropic | `claude-haiku-4-5-20251001` |
| gemini | `gemini-2.0-flash` |
| ollama | `qwen2.5` |

---

## Project structure

```
mini_agent/
├── agent.py         # CLI entry point — argument parsing, REPL, mode dispatch
├── core.py          # The agent loop: run_agent() and run_agent_mixed()
├── reliability.py   # Reliability layer: retry, circuit breaker, validation, tracing, provider fallback
├── providers.py     # LLM provider abstraction (OpenAI, Anthropic, Gemini, Ollama)
├── tools.py         # Tool implementations and schemas
├── ui.py            # Spinner — thread-safe braille activity indicator
├── mcp_server.py    # Demo MCP server (to_uppercase, count_words)
├── mcp_client.py    # MCP client helper — spawns the server, calls tools via JSON-RPC
├── requirements.txt
└── .env.example
```

### Adding your own tools

1. Write a Python function in `tools.py`
2. Add it to `TOOL_FUNCTIONS`
3. Add its JSON schema to `TOOL_SCHEMAS`

The `web_search` and `get_weather` tools are stubs. Replace them with real API calls (Brave Search, Tavily, OpenWeatherMap, etc.) to make the agent genuinely useful.

---

## How the loop works

```
┌─────────────────────────────────────────┐
│  messages = [system, user_task]         │
│                                         │
│  while True:                            │
│    response = llm.complete(messages)    │
│                                         │
│    if no tool_calls:                    │
│      return response.content  ← done   │
│                                         │
│    for each tool_call:                  │
│      result = call_tool(name, args)     │
│      messages.append(tool_result)       │
└─────────────────────────────────────────┘
```

In mixed mode, `ask_remote()` is an extra tool the local model can call. Calling it triggers a fresh `run_agent()` with the remote provider.

---

## MCP tools

`mcp_server.py` is a standalone [Model Context Protocol](https://modelcontextprotocol.io) server that exposes two tools — `to_uppercase` and `count_words`. The agent calls them transparently via `mcp_client.py`; from the agent's perspective they are no different from any other tool.

**Verify the server starts:**

```bash
python mcp_server.py
```

It will block waiting for JSON-RPC messages on stdin — that's expected. Press `Ctrl+C` to exit. Normally the agent spawns it automatically as a subprocess.

**How the communication works:**

```
agent (tools.py)
  └── mcp_client.py          # asyncio JSON-RPC client
        └── subprocess: mcp_server.py   # FastMCP server on stdio
```

Each tool call spawns a fresh subprocess, performs the `initialize` → `call_tool` handshake, and exits. To add your own MCP tools, define them in `mcp_server.py` with `@mcp.tool()` and register wrapper functions in `tools.py` following the same pattern as `mcp_to_uppercase` and `mcp_count_words`.

---

## Notes

- `calculate()` uses Python's `eval()` with empty builtins — safe enough for a demo, not for production. Replace with a proper math library (`sympy`, `asteval`) for real use.
- Ollama function calling works with `llama3.1`, `llama3.2`, `qwen2.5`, `mistral-nemo`. Models like `phi3` or `deepseek-r1` may not support it reliably.
- Gemini uses its OpenAI-compatible endpoint — no `google-generativeai` SDK needed.
- The `anthropic` SDK is only needed if you use `--provider anthropic`.

---

## Changelog

### v0.2 — Reliability layer

Added `reliability.py` on top of the unchanged core loop. Every item is independently useful; none require changes to `core.py`.

**LLM-level resilience**
- `_RetryingProvider` — wraps any provider's `complete()` with exponential backoff + jitter (up to 5 attempts). The agent loop never sees a transient network failure.

**Tool-level resilience**
- `with_retry()` — retries a single tool call on exception (configurable attempts and base delay)
- `CircuitBreaker` — stops calling a broken tool after N consecutive failures; auto-resets after a timeout
- `validated_call()` — validates tool arguments against the JSON schema with pydantic before execution; returns an error string the model can self-correct on
- `traced_call()` — emits a structured log line (tool name, args, result, duration) for every call regardless of outcome
- `run_agent_reliable()` — `run_agent()` with all four tool layers stacked; drop-in replacement

**Provider fallback**
- `run_agent_with_fallback()` — tries a list of providers in order, falling back on exception *or* silent failure (model outputs tool invocations as plain text instead of structured `tool_calls`)
- `_looks_like_failed_tool_call()` — heuristic that turns the silent failure into a detectable error
- `--fallback MODEL [MODEL …]` CLI flag — e.g. `--fallback llama3.1 mistral-nemo`

**agent.py** — `run_agent_reliable()` is now the default for `local` and `remote` modes.

### v0.1 — Initial release

Core agent loop: `agent.py`, `core.py`, `providers.py`, `tools.py`, `ui.py`, MCP client/server.

---

## License

MIT
