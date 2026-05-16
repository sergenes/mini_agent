"""
reliability.py — the infrastructure layer on top of the 50-line agent.

Diff this file against core.py to see exactly what each layer adds.

Five layers, each independently useful:

  with_retry()              — exponential backoff + jitter on transient failures
  CircuitBreaker            — stop hammering a broken service; fail fast
  validated_call()          — schema check before any tool executes
  traced_call()             — structured log line for every tool call
  run_agent_with_fallback() — try providers in order; skip models that fail or
                              output text-based tool calls instead of structured ones

  run_agent_reliable()      — run_agent() with the first four layers stacked
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from collections import defaultdict
from typing import Callable, Optional

from pydantic import ValidationError, create_model

from core import run_agent, _SYSTEM_DEFAULT
from tools import TOOL_SCHEMAS, call_tool

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S", level=logging.INFO)
_log = logging.getLogger("reliability")

# Build a name → parameters-schema index once at import time.
_SCHEMAS: dict[str, dict] = {
    s["function"]["name"]: s["function"]["parameters"]
    for s in TOOL_SCHEMAS
}


# -------------------------------------------------
# Layer 1 — Retry with exponential backoff and jitter
# -------------------------------------------------

def with_retry(
    fn: Callable[..., str],
    args: dict,
    max_attempts: int = 3,
    base_delay: float = 1.0,
) -> str:
    """Call fn(**args), retrying up to max_attempts times on any exception."""
    for attempt in range(max_attempts):
        try:
            return fn(**args)
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            _log.warning("attempt %d failed (%s) — retrying in %.1fs", attempt + 1, e, delay)
            time.sleep(delay)


# -------------------------------------------------
# Layer 2 — Circuit breaker
# -------------------------------------------------

class CircuitBreaker:
    """
    Stop calling a service after N consecutive failures.
    Transitions: closed → open (after threshold) → half-open (after timeout) → closed (on success).
    """

    CLOSED, OPEN, HALF_OPEN = "closed", "open", "half-open"

    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._failures = 0
        self._state = self.CLOSED
        self._opened_at: float | None = None

    def call(self, fn: Callable[..., str], args: dict) -> str:
        if self._state == self.OPEN:
            elapsed = time.time() - self._opened_at
            if elapsed < self.reset_timeout:
                raise RuntimeError(
                    f"Circuit open — service unavailable "
                    f"(resets in {self.reset_timeout - elapsed:.0f}s)"
                )
            self._state = self.HALF_OPEN

        try:
            result = fn(**args)
            if self._state == self.HALF_OPEN:
                self._reset()
            return result
        except Exception:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._state = self.OPEN
                self._opened_at = time.time()
                _log.error("circuit opened after %d consecutive failures", self._failures)
            raise

    def _reset(self) -> None:
        self._failures = 0
        self._state = self.CLOSED
        self._opened_at = None


# -------------------------------------------------
# Layer 3 — Schema validation with pydantic
# -------------------------------------------------

_TYPE_MAP = {"string": str, "number": float, "integer": int, "boolean": bool}


def _build_validator(schema: dict):
    """Build a pydantic model from a JSON schema parameters block."""
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields = {}
    for field, spec in props.items():
        py_type = _TYPE_MAP.get(spec.get("type", "string"), str)
        fields[field] = (py_type, ...) if field in required else (Optional[py_type], None)
    return create_model("ToolArgs", **fields)


_VALIDATORS: dict[str, type] = {
    name: _build_validator(schema)
    for name, schema in _SCHEMAS.items()
}


def validated_call(name: str, args: dict) -> str:
    """
    Validate args against the tool's JSON schema before calling it.
    Returns an error string on failure — the LLM receives it as a tool result
    and self-corrects on the next turn.
    """
    validator = _VALIDATORS.get(name)
    if validator is None:
        return call_tool(name, args)
    try:
        validated = validator(**args)
        return call_tool(name, validated.model_dump(exclude_none=True))
    except ValidationError as e:
        return f"Invalid arguments for '{name}': {e}"


# -------------------------------------------------
# Layer 4 — Structured tracing
# -------------------------------------------------

def traced_call(name: str, args: dict, fn: Callable[..., str]) -> str:
    """Execute fn(**args) and emit a structured log line regardless of outcome."""
    sanitized = {
        k: "***" if any(w in k.lower() for w in ("key", "secret", "token", "password")) else v
        for k, v in args.items()
    }
    start = time.time()
    try:
        result = fn(**args)
        _log.info(
            "tool=%s args=%s result=%r duration=%.3fs",
            name, json.dumps(sanitized), str(result)[:120], time.time() - start,
        )
        return result
    except Exception as e:
        _log.error(
            "tool=%s args=%s error=%s duration=%.3fs",
            name, json.dumps(sanitized), e, time.time() - start,
        )
        raise


# -------------------------------------------------
# Compose all four layers into a single dispatcher
# -------------------------------------------------

def _make_dispatcher(
    breakers: dict[str, CircuitBreaker],
    max_retries: int,
) -> Callable[[str, dict], str]:
    """Stack traced → circuit breaker → retry → validate → call."""

    def dispatch(name: str, args: dict) -> str:
        def core(**kw) -> str:
            return validated_call(name, kw)

        def retried(**kw) -> str:
            return with_retry(core, kw, max_attempts=max_retries)

        def guarded(**kw) -> str:
            return breakers[name].call(retried, kw)

        return traced_call(name, args, guarded)

    return dispatch


def run_agent_reliable(
    task: str,
    provider,
    tools: list[dict] | None = None,
    system_prompt: str = _SYSTEM_DEFAULT,
    verbose: bool = True,
    max_retries: int = 3,
    llm_max_retries: int = 5,
    circuit_failure_threshold: int = 3,
    circuit_reset_timeout: float = 30.0,
) -> str:
    """
    run_agent() with retry, circuit breaker, schema validation, and tracing
    applied to every tool call. Drop-in replacement for run_agent().

    llm_max_retries: retries on the LLM call itself (network drops, 503s, etc.)
    max_retries:     retries on individual tool calls
    """
    breakers: dict[str, CircuitBreaker] = defaultdict(
        lambda: CircuitBreaker(
            failure_threshold=circuit_failure_threshold,
            reset_timeout=circuit_reset_timeout,
        )
    )
    return run_agent(
        task,
        _RetryingProvider(provider, max_retries=llm_max_retries),
        tools=tools,
        system_prompt=system_prompt,
        verbose=verbose,
        tool_dispatcher=_make_dispatcher(breakers, max_retries),
    )


# -------------------------------------------------
# LLM-level retry wrapper
# -------------------------------------------------

class _RetryingProvider:
    """Wraps any LLMProvider and adds exponential-backoff retry to complete()."""

    def __init__(self, inner, max_retries: int = 5, base_delay: float = 2.0) -> None:
        self._inner = inner
        self._max_retries = max_retries
        self._base_delay = base_delay

    def complete(self, messages, tools):
        for attempt in range(self._max_retries):
            try:
                return self._inner.complete(messages, tools)
            except Exception as e:
                if attempt == self._max_retries - 1:
                    raise
                delay = self._base_delay * (2 ** attempt) + random.uniform(0, 1.0)
                _log.warning(
                    "LLM call attempt %d failed (%s) — retrying in %.1fs",
                    attempt + 1, e, delay,
                )
                time.sleep(delay)

    def __str__(self) -> str:
        return str(self._inner)


# -------------------------------------------------
# Layer 5 — Provider fallback
# -------------------------------------------------

def _looks_like_failed_tool_call(text: str) -> bool:
    """Detect when a model outputs tool invocations as text instead of structured calls."""
    return bool(re.search(r'\(\(\w+\s*\{', text))


def run_agent_with_fallback(
    task: str,
    providers: list,
    tools: list[dict] | None = None,
    system_prompt: str = _SYSTEM_DEFAULT,
    verbose: bool = True,
    max_retries: int = 2,
    circuit_failure_threshold: int = 3,
    circuit_reset_timeout: float = 30.0,
) -> str:
    """
    Try providers in order, falling back to the next on exception or unstructured output.

    Each attempt uses run_agent_reliable() so retry/circuit-breaker/validation/tracing
    are still active. A provider is skipped when it either raises an exception or returns
    text that looks like a text-based tool invocation (structured calling not supported).
    """
    last_exc: Exception | None = None

    for i, provider in enumerate(providers):
        is_last = i == len(providers) - 1
        try:
            _log.info("trying provider: %s", provider)
            result = run_agent_reliable(
                task, provider,
                tools=tools,
                system_prompt=system_prompt,
                verbose=verbose,
                max_retries=max_retries,
                circuit_failure_threshold=circuit_failure_threshold,
                circuit_reset_timeout=circuit_reset_timeout,
            )
            if _looks_like_failed_tool_call(result):
                raise RuntimeError(
                    f"{provider} did not use structured tool calling — got: {result[:80]!r}"
                )
            return result
        except Exception as e:
            _log.warning("provider %s failed: %s", provider, e)
            last_exc = e
            if not is_last:
                _log.info("falling back to next provider")

    raise last_exc or RuntimeError("all providers failed")
