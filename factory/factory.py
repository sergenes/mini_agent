#!/usr/bin/env python3
"""
factory.py — a naive software factory: a state machine that holds the
seven-station loop (describe, remember, pattern, move, see, survive, run
one milestone) together, so a project cannot drift past a station whose
gate is not actually satisfied on disk.

This does not compete with real agentic-harness projects like
github/spec-kit or hmzisb/software-factory. Those are production tools:
multi-agent teams, guardrail hooks, probabilistic eval harnesses. This is
the 50-line-loop move from Part 1 applied one level up: build the naive
version yourself so the mechanism stops being magic. It reuses this
series' own parts directly instead of reimplementing them:

  - describe/remember/pattern/move/see/survive gates: plain file and
    content checks, no model call, same spirit as feature-pipeline's
    pipeline_check.py.
  - run one milestone: imports core.run_agent and providers.create_provider
    from this repo, the actual Part 1 loop, unmodified.

State lives in <project>/.factory/state.json: which station is current,
how many milestones have shipped. Advancing a station re-checks its gate;
it never trusts what you did last time.

Usage:
    python3 factory.py init <project_dir>
    python3 factory.py status <project_dir> [--json]
    python3 factory.py scaffold <project_dir>
    python3 factory.py advance <project_dir> [--json]
    python3 factory.py run-milestone <project_dir> "<task>" [--provider openai] [--model gpt-4o-mini]

`scaffold` writes a starter file with proposed sections for whatever
station you are currently blocked on (SPEC.md, a project CLAUDE.md, a
no-op release.py, a visual-testing/README.md, or SURVIVE.md). It never
overwrites a file that already exists. `--json` on status/advance prints
a machine-readable ```factory-gate-result``` block after the human
summary, one JSON object with a status, a list of blockers, and a
suggested next command, the same shape ai-factory's quality gates use
for their `aif-gate-result` blocks, adapted to this project's own
seven stations.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

STATIONS = ["describe", "remember", "pattern", "move", "see", "survive", "run"]

STATE_DIR = ".factory"
STATE_FILE = "state.json"

PLATFORM_KEYWORDS = {
    "android": "android-architecture",
    "ios": "ios-architecture",
    "web": "web-architecture",
}


@dataclass
class GateResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)


def read_text(path: Path) -> str:
    return path.read_text() if path.exists() else ""


# ---------------------------------------------------------------- describe

def check_describe(project: Path) -> GateResult:
    spec = project / "SPEC.md"
    if not spec.exists():
        return GateResult(False, ["SPEC.md does not exist"])
    text = read_text(spec).lower()
    required = ["platform", "data model", "boundar", "milestone 1"]
    missing = [r for r in required if r not in text]
    if missing:
        return GateResult(False, [f"SPEC.md is missing a section on: {m}" for m in missing])
    return GateResult(True)


# ---------------------------------------------------------------- remember

def check_remember(project: Path, max_lines: int = 60) -> GateResult:
    reasons = []
    candidates = [project / "CLAUDE.md", project / "AGENTS.md"]
    found = next((c for c in candidates if c.exists()), None)
    if found is None:
        return GateResult(False, ["neither CLAUDE.md nor AGENTS.md exists"])
    lines = read_text(found).splitlines()
    if len(lines) > max_lines:
        reasons.append(f"{found.name} is {len(lines)} lines, over the {max_lines}-line budget")
    if "skill" not in read_text(found).lower():
        reasons.append(f"{found.name} does not point at any skill, it should index at least one")
    return GateResult(not reasons, reasons)


# ----------------------------------------------------------------- pattern

def _platforms_in_spec(project: Path) -> list[str]:
    text = read_text(project / "SPEC.md").lower()
    return [p for p in PLATFORM_KEYWORDS if p in text]


def _skill_exists(project: Path, skill_name: str) -> bool:
    search_roots = [
        project / ".claude" / "skills",
        project / ".cursor" / "skills",
        project / "agent-memory" / "personal-skills",
        Path.home() / ".claude" / "skills",
        Path.home() / ".cursor" / "skills",
    ]
    return any((root / skill_name / "SKILL.md").exists() for root in search_roots)


def check_pattern(project: Path) -> GateResult:
    platforms = _platforms_in_spec(project)
    if not platforms:
        return GateResult(True, ["no platform keywords found in SPEC.md, nothing to gate"])
    missing = [p for p in platforms if not _skill_exists(project, PLATFORM_KEYWORDS[p])]
    if missing:
        return GateResult(False, [
            f"SPEC.md names '{p}' but no {PLATFORM_KEYWORDS[p]} skill was found" for p in missing
        ])
    return GateResult(True)


# -------------------------------------------------------------------- move

def check_move(project: Path, script_globs: tuple[str, ...] = ("scripts/release.py", "release.py", "deploy.sh")) -> GateResult:
    for rel in script_globs:
        if (project / rel).exists():
            return GateResult(True)
    return GateResult(False, [f"no deploy script found at any of: {', '.join(script_globs)}"])


# --------------------------------------------------------------------- see

def check_see(project: Path) -> GateResult:
    candidates = [
        project / "visual-testing",
        project / "baselines",
        project / "tests" / "golden",
    ]
    if any(c.exists() and any(c.iterdir()) for c in candidates if c.exists()):
        return GateResult(True)
    return GateResult(False, ["no visual baseline or golden-file directory found"])


# ----------------------------------------------------------------- survive

SURVIVE_TAG = re.compile(r"#\s*@survive:")


def check_survive(project: Path) -> GateResult:
    if (project / "SURVIVE.md").exists():
        return GateResult(True)
    for py_file in project.rglob("*.py"):
        if SURVIVE_TAG.search(read_text(py_file)):
            return GateResult(True)
    return GateResult(False, [
        "no SURVIVE.md and no '# @survive:' tag found. "
        "If nothing here touches money, email, or production state, this station is a no-op, "
        "add a one-line SURVIVE.md that says so."
    ])


GATES = {
    "describe": check_describe,
    "remember": check_remember,
    "pattern": check_pattern,
    "move": check_move,
    "see": check_see,
    "survive": check_survive,
}


# ---------------------------------------------------------------- scaffold
#
# Writing a template does not launder its content: a scaffolded SPEC.md
# contains the words "platform", "data model", "boundar", and "milestone 1"
# as section labels, so check_describe passes it the moment it is saved,
# before a single real word is written. That is not a bug. It is the same
# honest limit the gates already have: presence, not quality. Scaffold buys
# you a place to write the real answer, not a shortcut past writing it.

SPEC_TEMPLATE = """# Spec

Platforms: <!-- e.g. iOS, Android, web -->

Data model: <!-- key entities and how they relate -->

Boundaries: <!-- what the agent must not invent or touch -->

Monetization: <!-- free, subscription, one-time, none yet -->

Milestone 1: <!-- the smallest thing a tester could open, with acceptance criteria -->
"""

CLAUDE_TEMPLATE = """# {name}

<!-- one or two sentences: what this repo is -->

## Always

- Do not invent a new architecture. Load the matching skill first.
- Do not invent a new deploy path.

## Skills

<!-- name the skills this project should load, e.g. android-architecture -->
"""

RELEASE_STUB = '#!/usr/bin/env python3\nprint("not wired yet")\n'

VISUAL_README_TEMPLATE = """# Visual testing

<!-- Put recorded baselines here, e.g. baselines-ios/index.json.
See Part 4 of the series for the full record/check tool. -->
"""

SURVIVE_TEMPLATE = """# Survive

<!-- Does this touch money, email, or production data?
If not, say so explicitly. If so, describe how it recovers: retry, circuit breaker, undo. -->
"""


def _write_template(path: Path, content: str) -> bool:
    if path.exists():
        print(f"{path} already exists, left untouched")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"wrote {path}")
    return True


def cmd_scaffold(project: Path) -> int:
    station = current_station(project)
    project.mkdir(parents=True, exist_ok=True)

    if station == "describe":
        _write_template(project / "SPEC.md", SPEC_TEMPLATE)
        return 0

    if station == "remember":
        if any((project / n).exists() for n in ("CLAUDE.md", "AGENTS.md")):
            print("CLAUDE.md or AGENTS.md already exists, left untouched")
            return 0
        _write_template(project / "CLAUDE.md", CLAUDE_TEMPLATE.format(name=project.name))
        return 0

    if station == "pattern":
        platforms = _platforms_in_spec(project)
        if not platforms:
            print("no platform named in SPEC.md, nothing to scaffold here")
            return 0
        missing = [p for p in platforms if not _skill_exists(project, PLATFORM_KEYWORDS[p])]
        if not missing:
            print("every named platform already has a matching skill")
            return 0
        print("architecture skills are not scaffolded, they are meant to be reused across projects, not generated per project:")
        for p in missing:
            print(f"    copy or write {PLATFORM_KEYWORDS[p]}/SKILL.md, e.g. from agent-memory/personal-skills/")
        return 1

    if station == "move":
        _write_template(project / "scripts" / "release.py", RELEASE_STUB)
        return 0

    if station == "see":
        _write_template(project / "visual-testing" / "README.md", VISUAL_README_TEMPLATE)
        return 0

    if station == "survive":
        _write_template(project / "SURVIVE.md", SURVIVE_TEMPLATE)
        return 0

    print('nothing to scaffold at the "run" station, use run-milestone')
    return 0


def suggest_next(station: str, project: Path, result: GateResult) -> dict:
    if result.ok:
        return {"command": "advance", "reason": f'"{station}" gate is satisfied'}
    needs_file = {
        "describe": not (project / "SPEC.md").exists(),
        "remember": not any((project / n).exists() for n in ("CLAUDE.md", "AGENTS.md")),
        "move": not any((project / p).exists() for p in ("scripts/release.py", "release.py", "deploy.sh")),
        "see": not any(
            (project / d).exists() and any((project / d).iterdir())
            for d in ("visual-testing", "baselines", "tests/golden")
        ),
        "survive": not (project / "SURVIVE.md").exists(),
    }
    if needs_file.get(station):
        return {"command": "scaffold", "reason": f'no file exists yet for "{station}"'}
    return {"command": "advance", "reason": "fix the blockers above, then advance"}


def gate_result_payload(station: str, project: Path, result: GateResult) -> dict:
    return {
        "schema_version": 1,
        "station": station,
        "status": "pass" if result.ok else "fail",
        "blocking": not result.ok,
        "blockers": [{"summary": r} for r in result.reasons],
        "suggested_next": suggest_next(station, project, result),
    }


def print_gate_result_json(station: str, project: Path, result: GateResult) -> None:
    print("```factory-gate-result")
    print(json.dumps(gate_result_payload(station, project, result), indent=2))
    print("```")


# ------------------------------------------------------------------ state

def state_path(project: Path) -> Path:
    return project / STATE_DIR / STATE_FILE


def load_state(project: Path) -> dict:
    p = state_path(project)
    if not p.exists():
        return {"station_index": 0, "milestones_shipped": 0}
    return json.loads(p.read_text())


def save_state(project: Path, state: dict) -> None:
    p = state_path(project)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2))


def current_station(project: Path) -> str:
    state = load_state(project)
    idx = min(state["station_index"], len(STATIONS) - 1)
    return STATIONS[idx]


# -------------------------------------------------------------------- CLI

def cmd_init(project: Path) -> int:
    if state_path(project).exists():
        print(f"already initialized at {state_path(project)}")
        return 0
    project.mkdir(parents=True, exist_ok=True)
    save_state(project, {"station_index": 0, "milestones_shipped": 0})
    print(f"initialized. current station: {STATIONS[0]}")
    return 0


def cmd_status(project: Path, emit_json: bool = False) -> int:
    state = load_state(project)
    station = current_station(project)
    print(f"station: {station} ({state['station_index'] + 1} of {len(STATIONS)})")
    print(f"milestones shipped: {state['milestones_shipped']}")
    if station in GATES:
        result = GATES[station](project)
        print(f"gate: {'PASS' if result.ok else 'BLOCKED'}")
        for r in result.reasons:
            print(f"    {r}")
        if emit_json:
            print_gate_result_json(station, project, result)
    else:
        print("gate: run one milestone, use `run-milestone` to actually do it")
    return 0


def cmd_advance(project: Path, emit_json: bool = False) -> int:
    state = load_state(project)
    station = current_station(project)
    if station == "run":
        print('current station is "run one milestone", use `run-milestone` instead of `advance`')
        return 1
    result = GATES[station](project)
    if emit_json:
        print_gate_result_json(station, project, result)
    if not result.ok:
        print(f"[BLOCKED] {station}")
        for r in result.reasons:
            print(f"    {r}")
        return 1
    state["station_index"] += 1
    if state["station_index"] >= len(STATIONS):
        state["station_index"] = len(STATIONS) - 1
    save_state(project, state)
    print(f"[PASS] {station}")
    print(f"now at: {current_station(project)}")
    return 0


def cmd_run_milestone(project: Path, task: str, provider_name: str, model: str | None) -> int:
    if current_station(project) != "run":
        print(f'not at the "run" station yet, currently at "{current_station(project)}"')
        return 1

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import core  # mini_agent's own agent loop, Part 1, unmodified
    import providers

    spec_text = read_text(project / "SPEC.md")
    system_prompt = (
        "You are building a feature for the product described below. "
        "Stay inside the boundaries this spec names. Do not invent architecture "
        "the spec does not call for.\n\n" + spec_text
    )

    provider = providers.create_provider(provider_name, model)
    print(f"running milestone {load_state(project)['milestones_shipped'] + 1} against {provider_name}...")
    answer = core.run_agent(task, provider, system_prompt=system_prompt)
    print("\n--- agent output ---")
    print(answer)

    for station in ("see", "move"):
        result = GATES[station](project)
        if not result.ok:
            print(f"\n[BLOCKED] milestone not done, \"{station}\" still fails:")
            for r in result.reasons:
                print(f"    {r}")
            return 1

    state = load_state(project)
    state["milestones_shipped"] += 1
    save_state(project, state)
    print(f"\n[PASS] milestone {state['milestones_shipped']} shipped. Back to \"run\" for the next one.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="initialize a project at station 1 (describe)")
    p_init.add_argument("project", type=Path)

    p_status = sub.add_parser("status", help="show current station and whether its gate passes")
    p_status.add_argument("project", type=Path)
    p_status.add_argument("--json", action="store_true", help="also print a machine-readable factory-gate-result block")

    p_advance = sub.add_parser("advance", help="check the current station's gate and advance if it passes")
    p_advance.add_argument("project", type=Path)
    p_advance.add_argument("--json", action="store_true", help="also print a machine-readable factory-gate-result block")

    p_scaffold = sub.add_parser("scaffold", help="write a starter file with proposed sections for the current station")
    p_scaffold.add_argument("project", type=Path)

    p_run = sub.add_parser("run-milestone", help="run one milestone through the real agent loop")
    p_run.add_argument("project", type=Path)
    p_run.add_argument("task")
    p_run.add_argument("--provider", default="openai")
    p_run.add_argument("--model", default=None)

    args = parser.parse_args()

    if args.command == "init":
        return cmd_init(args.project)
    if args.command == "status":
        return cmd_status(args.project, emit_json=args.json)
    if args.command == "advance":
        return cmd_advance(args.project, emit_json=args.json)
    if args.command == "scaffold":
        return cmd_scaffold(args.project)
    if args.command == "run-milestone":
        return cmd_run_milestone(args.project, args.task, args.provider, args.model)
    return 1


if __name__ == "__main__":
    sys.exit(main())
