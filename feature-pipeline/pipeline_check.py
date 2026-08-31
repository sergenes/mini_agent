#!/usr/bin/env python3
"""
pipeline_check.py — verify an open -> staging -> log work-tracking pipeline
instead of trusting that it was kept honest by hand.

Built for the three-file pattern described in "What I Stand Up Before the
First Feature": an open list (todo.md), a staging list for implemented-but-
unverified work (testing.md), and an append-only log of what actually
shipped (releases.md). The names and headings are configurable, so the same
checks work for a bug tracker, a content calendar, an ops runbook, or any
other team's version of the same three-stage flow.

Checks:
  1. No item title appears in both the open file and the staging file.
     An item that never got removed from "open" when it moved to "staging"
     is exactly the drift this pipeline exists to prevent.
  2. The log file is append-only relative to git history: everything that
     was already committed must still be present, unchanged, as a suffix
     of the current file. Only additions are allowed.
  3. Every entry newly added to the log file (since the last commit)
     contains at least one piece of evidence: a file path, a URL, or a
     commit-like hash. "Done" with nothing to point at does not pass.

Usage:
    python3 pipeline_check.py --open todo.md --staging testing.md --log releases.md
    python3 pipeline_check.py --open todo.md --staging testing.md --log releases.md --skip evidence

Exit code 0 if every requested check passes, 1 otherwise. Missing files are
treated as empty, not as errors, so you can run this before any of the
three files exist yet.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ITEM_LINE = re.compile(
    r"""^\s*
    (?:-\s*\[[ xX]\]\s*   # "- [ ] " or "- [x] " checkbox
     |\#{1,6}\s*          # or "## " heading
    )
    (?P<rest>.+)$
    """,
    re.VERBOSE,
)
LEADING_NUMBER = re.compile(r"^\s*\d+[.)]\s*")
BOLD_MARKERS = re.compile(r"\*\*")
DATE_TAG = re.compile(r"\[\d{4}-\d{2}-\d{2}\]")

EVIDENCE_PATTERNS = [
    re.compile(r"https?://\S+"),                      # a URL
    re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE),  # a commit-like hash
    re.compile(r"\S+\.(png|jpg|jpeg|log|txt|json|md|pdf|zip)\b", re.IGNORECASE),  # a file path
]


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: list[str] = field(default_factory=list)


def read_text(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def extract_items(text: str) -> dict[str, int]:
    """Map normalized item title -> line number (1-indexed) for the first match."""
    items: dict[str, int] = {}
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = ITEM_LINE.match(line)
        if not m:
            continue
        title = m.group("rest")
        title = LEADING_NUMBER.sub("", title)
        title = BOLD_MARKERS.sub("", title)
        title = DATE_TAG.sub("", title)
        title = " ".join(title.split()).lower().rstrip(":.-— ")
        if title and title not in items:
            items[title] = lineno
    return items


def check_no_stuck_items(open_text: str, staging_text: str) -> CheckResult:
    open_items = extract_items(open_text)
    staging_items = extract_items(staging_text)
    stuck = sorted(set(open_items) & set(staging_items))
    if not stuck:
        return CheckResult("no items stuck in both open and staging", True)
    details = [
        f'"{title}" — open:line {open_items[title]}, staging:line {staging_items[title]}'
        for title in stuck
    ]
    return CheckResult("no items stuck in both open and staging", False, details)


def git_show(ref: str, path: Path, cwd: Path) -> str | None:
    """Return file content at a git ref, or None if the file doesn't exist there."""
    try:
        rel = path.resolve().relative_to(cwd.resolve())
    except ValueError:
        rel = path
    result = subprocess.run(
        ["git", "show", f"{ref}:{rel.as_posix()}"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def split_entries(text: str) -> list[str]:
    """Split a log file's body into per-entry chunks on top-level '## ' headings.
    A preamble before the first '## ' (a title, a note) is dropped, entries only."""
    if not text.strip():
        return []
    first = re.search(r"(?m)^## ", text)
    if not first:
        return []
    body = text[first.start():]
    parts = re.split(r"(?m)^(?=## )", body)
    return [p.strip() for p in parts if p.strip()]


def diff_entries(previous_text: str, current_text: str) -> tuple[bool, list[str]]:
    """Compare entry lists. Returns (append_only_holds, new_entries).

    append-only holds if every previously committed entry still appears,
    unchanged and in the same relative order, as a contiguous block inside
    the current entries. new_entries is whatever comes before that block.
    """
    previous_entries = split_entries(previous_text)
    current_entries = split_entries(current_text)
    if not previous_entries:
        return True, current_entries
    n = len(previous_entries)
    for start in range(0, len(current_entries) - n + 1):
        if current_entries[start:start + n] == previous_entries:
            return True, current_entries[:start]
    return False, []


def check_append_only(log_path: Path, current_text: str, repo_root: Path) -> CheckResult:
    previous = git_show("HEAD", log_path, repo_root)
    if previous is None:
        return CheckResult(
            "log file is append-only since last commit", True,
            ["no committed version yet, nothing to compare"],
        )
    ok, _ = diff_entries(previous, current_text)
    if ok:
        return CheckResult("log file is append-only since last commit", True)
    return CheckResult(
        "log file is append-only since last commit", False,
        ["a previously committed entry is missing, edited, or out of order, "
         "releases.md must only ever grow at the top"],
    )


def check_evidence(log_path: Path, current_text: str, repo_root: Path) -> CheckResult:
    previous = git_show("HEAD", log_path, repo_root) or ""
    _, entries = diff_entries(previous, current_text)
    if not entries:
        return CheckResult("new log entries cite evidence", True, ["no new entries to check"])
    missing = []
    for entry in entries:
        title_line = entry.strip().splitlines()[0] if entry.strip() else "(untitled)"
        if not any(p.search(entry) for p in EVIDENCE_PATTERNS):
            missing.append(title_line.lstrip("# ").strip())
    if not missing:
        return CheckResult("new log entries cite evidence", True)
    return CheckResult(
        "new log entries cite evidence", False,
        [f'"{t}" has no URL, file path, or commit hash to point at' for t in missing],
    )


def find_repo_root(start: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return Path(result.stdout.strip())
    return start


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--open", dest="open_file", default="todo.md", help="open/backlog file (default: todo.md)")
    parser.add_argument("--staging", dest="staging_file", default="testing.md", help="implemented-not-verified file (default: testing.md)")
    parser.add_argument("--log", dest="log_file", default="releases.md", help="append-only shipped log (default: releases.md)")
    parser.add_argument(
        "--skip", action="append", default=[], choices=["stuck", "append-only", "evidence"],
        help="skip a check by name; repeatable",
    )
    args = parser.parse_args()

    open_path = Path(args.open_file)
    staging_path = Path(args.staging_file)
    log_path = Path(args.log_file)
    repo_root = find_repo_root(Path.cwd())

    open_text = read_text(open_path)
    staging_text = read_text(staging_path)
    log_text = read_text(log_path)

    results: list[CheckResult] = []

    if "stuck" not in args.skip:
        results.append(check_no_stuck_items(open_text, staging_text))
    if "append-only" not in args.skip:
        results.append(check_append_only(log_path, log_text, repo_root))
    if "evidence" not in args.skip:
        results.append(check_evidence(log_path, log_text, repo_root))

    ok = True
    for r in results:
        status = "PASS" if r.ok else "FAIL"
        print(f"[{status}] {r.name}")
        for line in r.details:
            print(f"    {line}")
        ok = ok and r.ok

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
