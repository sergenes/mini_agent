#!/usr/bin/env python3
"""
Mini Agent — a minimal AI agent with no framework dependencies.

Three modes:
  local   — all LLM calls go to a local Ollama model
  remote  — all LLM calls go to a cloud provider (OpenAI, Anthropic, or Gemini)
  mixed   — local Ollama orchestrates; delegates complex tasks to the remote model

Usage examples:
  python agent.py --mode local "What is 15% of 847?"
  python agent.py --mode local --local-model qwen2.5 "What's the weather in Tokyo?"

  python agent.py --mode remote --provider openai "Explain how ReAct agents work"
  python agent.py --mode remote --provider anthropic --model claude-haiku-4-5-20251001 "Write a haiku about Python"
  python agent.py --mode remote --provider gemini --model gemini-2.0-flash "Summarize MCP"

  python agent.py --mode mixed "What's today's date and explain quantum entanglement"
  python agent.py --mode mixed --local-model qwen2.5 --provider anthropic "..."

  python agent.py --mode local --interactive
  python agent.py --mode remote --interactive
"""

from __future__ import annotations

import argparse
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; export env vars manually if not installed

from providers import create_provider, LLMProvider
from core import run_agent, run_agent_mixed
from reliability import run_agent_reliable, run_agent_with_fallback


_BANNER = """\
╔══════════════════════════════════════════╗
║           Mini Agent  v0.1               ║
║   local  |  remote  |  mixed             ║
╚══════════════════════════════════════════╝"""


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agent",
        description="A minimal AI agent — no frameworks, just the loop.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--mode",
        choices=["local", "remote", "mixed"],
        default="local",
        help="Execution mode (default: local)",
    )
    p.add_argument(
        "--local-model",
        default="qwen2.5",
        metavar="MODEL",
        help="Ollama model for local/mixed mode (default: qwen2.5). "
             "Any model that supports function calling works: qwen2.5, mistral-nemo, llama3.2, ...",
    )
    p.add_argument(
        "--provider",
        choices=["openai", "anthropic", "gemini"],
        default="openai",
        dest="remote_provider",
        help="Cloud provider for remote/mixed mode (default: openai)",
    )
    p.add_argument(
        "--model",
        default=None,
        dest="remote_model",
        metavar="MODEL",
        help=(
            "Cloud model name. Defaults: "
            "openai→gpt-4o-mini, anthropic→claude-haiku-4-5-20251001, gemini→gemini-2.0-flash"
        ),
    )
    p.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Start an interactive REPL session instead of running a single task",
    )
    p.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress tool call trace output",
    )
    p.add_argument(
        "--fallback",
        nargs="+",
        default=[],
        metavar="MODEL",
        help=(
            "Fallback local model(s) tried in order if the primary fails "
            "(e.g. --fallback llama3.1 mistral-nemo). Local mode only."
        ),
    )
    p.add_argument(
        "task",
        nargs="*",
        help="Task to run (omit when using --interactive)",
    )
    return p


def _describe_mode(args, local: LLMProvider | None, remote: LLMProvider | None) -> str:
    if args.mode == "local":
        return f"local  →  {local}"
    if args.mode == "remote":
        return f"remote →  {remote}"
    return f"mixed  →  local: {local}  |  remote: {remote}"


def run_task(task: str, args, local: LLMProvider | None, remote: LLMProvider | None) -> str:
    verbose = not args.quiet
    if args.mode == "local":
        if args.fallback:
            providers = [local] + [create_provider("ollama", m) for m in args.fallback]
            return run_agent_with_fallback(task, providers, verbose=verbose)
        return run_agent_reliable(task, local, verbose=verbose)
    if args.mode == "remote":
        return run_agent_reliable(task, remote, verbose=verbose)
    return run_agent_mixed(task, local, remote, verbose=verbose)


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    print(_BANNER)

    # --- Build providers ---
    local: LLMProvider | None = None
    remote: LLMProvider | None = None

    try:
        if args.mode in ("local", "mixed"):
            local = create_provider("ollama", args.local_model)
        if args.mode in ("remote", "mixed"):
            remote = create_provider(args.remote_provider, args.remote_model)
    except EnvironmentError as e:
        print(f"\nConfiguration error: {e}\n")
        sys.exit(1)

    print(f"\nMode: {_describe_mode(args, local, remote)}\n")

    # --- Run ---
    if args.interactive:
        _repl(args, local, remote)
    else:
        if not args.task:
            parser.print_help()
            sys.exit(0)
        task = " ".join(args.task)
        print(f"Task: {task}\n")
        try:
            answer = run_task(task, args, local, remote)
            print(f"\nAnswer: {answer}\n")
        except KeyboardInterrupt:
            print("\nInterrupted.")
            sys.exit(0)
        except Exception as e:
            print(f"\nError: {e}\n")
            sys.exit(1)


def _repl(args, local: LLMProvider | None, remote: LLMProvider | None) -> None:
    print("Interactive mode. Type your task and press Enter.")
    print("Commands: 'exit' or Ctrl+C to quit.\n")

    while True:
        try:
            task = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        if task.lower() in ("exit", "quit", "q", ":q"):
            print("Goodbye.")
            break
        if not task:
            continue

        print()
        try:
            answer = run_task(task, args, local, remote)
            print(f"\nAgent: {answer}\n")
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    main()
