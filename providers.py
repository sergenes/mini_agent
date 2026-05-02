"""
LLM provider abstraction.

Supported providers:
  - openai   : OpenAI API (gpt-4o-mini, gpt-4o, o1, ...)
  - anthropic : Anthropic API (claude-haiku-4-5-20251001, claude-sonnet-4-6, ...)
  - gemini    : Google Gemini via its OpenAI-compatible endpoint
  - ollama    : Local models via Ollama (llama3.1, qwen2.5, mistral-nemo, ...)

All providers share the same interface: .complete(messages, tools) → LLMMessage.
Messages are kept in canonical (OpenAI-style) dicts throughout; each provider
translates to its native format internally.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Canonical message types
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict  # already parsed from JSON


@dataclass
class LLMMessage:
    role: str
    content: str | None
    tool_calls: list[ToolCall] | None = None

    def to_dict(self) -> dict:
        """Canonical dict for the agent's messages list."""
        d: dict = {"role": self.role}
        if self.content is not None:
            d["content"] = self.content
        if self.tool_calls:
            d["tool_calls"] = [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in self.tool_calls
            ]
        return d


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class LLMProvider:
    name: str = "base"

    def complete(self, messages: list[dict], tools: list[dict]) -> LLMMessage:
        raise NotImplementedError

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# OpenAI-compatible provider (OpenAI, Ollama, Gemini)
# ---------------------------------------------------------------------------

class OpenAICompatProvider(LLMProvider):
    """
    Works for any OpenAI-compatible endpoint:
      - OpenAI:  api.openai.com (default)
      - Ollama:  localhost:11434/v1
      - Gemini:  generativelanguage.googleapis.com/v1beta/openai/
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        label: str = "openai",
    ):
        from openai import OpenAI
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model = model
        self.name = f"{label}/{model}"

    def complete(self, messages: list[dict], tools: list[dict]) -> LLMMessage:
        kwargs: dict = {
            "model": self.model,
            "messages": _to_openai_messages(messages),
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**kwargs)
        msg = response.choices[0].message

        tool_calls = None
        if msg.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                )
                for tc in msg.tool_calls
            ]

        return LLMMessage(role="assistant", content=msg.content, tool_calls=tool_calls)


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.name = f"anthropic/{model}"

    def complete(self, messages: list[dict], tools: list[dict]) -> LLMMessage:
        system, anthropic_msgs = _to_anthropic_messages(messages)
        anthropic_tools = _to_anthropic_tools(tools)

        kwargs: dict = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": anthropic_msgs,
        }
        if system:
            kwargs["system"] = system
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        response = self.client.messages.create(**kwargs)

        content_text = None
        tool_calls = None

        for block in response.content:
            if block.type == "text":
                content_text = block.text
            elif block.type == "tool_use":
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=block.input)
                )

        return LLMMessage(role="assistant", content=content_text, tool_calls=tool_calls)


# ---------------------------------------------------------------------------
# Format conversion helpers
# ---------------------------------------------------------------------------

def _to_openai_messages(canonical: list[dict]) -> list[dict]:
    """Canonical → OpenAI API format."""
    result = []
    for msg in canonical:
        if msg["role"] == "tool":
            result.append({
                "role": "tool",
                "tool_call_id": msg["tool_call_id"],
                "content": msg["content"],
            })
        elif msg["role"] == "assistant" and msg.get("tool_calls"):
            result.append({
                "role": "assistant",
                "content": msg.get("content"),
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]),
                        },
                    }
                    for tc in msg["tool_calls"]
                ],
            })
        else:
            result.append({"role": msg["role"], "content": msg.get("content", "")})
    return result


def _to_anthropic_messages(canonical: list[dict]) -> tuple[str | None, list[dict]]:
    """Canonical → Anthropic API format. Returns (system_str, messages_list)."""
    system = None
    messages = []
    i = 0

    while i < len(canonical):
        msg = canonical[i]

        if msg["role"] == "system":
            system = msg["content"]
            i += 1

        elif msg["role"] == "user":
            messages.append({"role": "user", "content": msg["content"]})
            i += 1

        elif msg["role"] == "assistant":
            blocks = []
            if msg.get("content"):
                blocks.append({"type": "text", "text": msg["content"]})
            for tc in msg.get("tool_calls", []):
                blocks.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc["arguments"],
                })
            messages.append({"role": "assistant", "content": blocks})
            i += 1

        elif msg["role"] == "tool":
            # Collect consecutive tool results into one user message
            results = []
            while i < len(canonical) and canonical[i]["role"] == "tool":
                results.append({
                    "type": "tool_result",
                    "tool_use_id": canonical[i]["tool_call_id"],
                    "content": canonical[i]["content"],
                })
                i += 1
            messages.append({"role": "user", "content": results})

        else:
            i += 1

    return system, messages


def _to_anthropic_tools(openai_tools: list[dict]) -> list[dict]:
    """Convert OpenAI tool schemas to Anthropic format."""
    return [
        {
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "input_schema": t["function"]["parameters"],
        }
        for t in openai_tools
    ]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_DEFAULTS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
    "gemini": "gemini-2.0-flash",
    "ollama": "qwen2.5",
}


def create_provider(provider: str, model: str | None = None) -> LLMProvider:
    """
    Create an LLM provider by name.

    provider: "openai" | "anthropic" | "gemini" | "ollama"
    model:    model name (uses a sensible default if omitted)
    """
    model = model or _DEFAULTS.get(provider, "")

    if provider == "openai":
        return OpenAICompatProvider(
            api_key=_require_env("OPENAI_API_KEY"),
            model=model,
            label="openai",
        )
    if provider == "anthropic":
        return AnthropicProvider(
            api_key=_require_env("ANTHROPIC_API_KEY"),
            model=model,
        )
    if provider == "gemini":
        return OpenAICompatProvider(
            api_key=_require_env("GEMINI_API_KEY"),
            model=model,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            label="gemini",
        )
    if provider == "ollama":
        return OpenAICompatProvider(
            api_key="ollama",         # required by the client, ignored by Ollama
            model=model,
            base_url="http://localhost:11434/v1",
            label="ollama",
        )

    raise ValueError(
        f"Unknown provider '{provider}'. Choose from: openai, anthropic, gemini, ollama"
    )


def _require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise EnvironmentError(
            f"Environment variable {key} is not set. "
            f"Add it to your .env file or export it in your shell."
        )
    return val
