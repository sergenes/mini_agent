# Mini Agent

Companion repo for the series Software Engineering in the Agentic AI Era. No agent framework: Python, the OpenAI SDK, and a `while` loop. Three modes: local (Ollama), remote (cloud), mixed.

## Always

- Do not commit `.env` or credentials.
- Add tools only through `tools.py` (`TOOL_FUNCTIONS` + `TOOL_SCHEMAS`).
- If the task matches a skill, load the skill before acting.

## Skills

- `running-the-agent`: venv, `.env`, local / remote / mixed, MCP, fallback
- `visual-check`: `visual-testing/ui_agent.py` record and check
- `deploy`: `deployment-pipeline/release.py` and `infra_tools.py`

## Tools

Codex CLI, Cursor, and Grok CLI read `AGENTS.md` (same text as this file). Gemini CLI reads `GEMINI.md`, which points here. Keep `CLAUDE.md` and `AGENTS.md` in sync by hand until you make one a generated copy of the other.

<!-- mirror of AGENTS.md. Keep them in sync. -->

