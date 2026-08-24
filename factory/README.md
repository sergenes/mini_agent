# factory.py — a naive software factory

A state machine that holds the seven-station loop from Part 7 together: **describe → remember → pattern → move → see → survive → run one milestone.** A project cannot advance past a station whose gate is not actually satisfied on disk, checked fresh every time, not trusted from last time.

## What this is not

This is not a competitor to real agentic-harness projects. [github/spec-kit](https://github.com/github/spec-kit) is GitHub's own official spec-driven-development toolkit, six phases, 30+ agent integrations. [`lee-to/ai-factory`](https://github.com/lee-to/ai-factory) is further still: over a thousand stars, an npm package, slash commands that carry a project from `/aif-plan` through `/aif-implement`, and quality gates that emit a structured `aif-gate-result` JSON block. [hmzisb/software-factory](https://github.com/hmzisb/software-factory), built on marmelab's ["Agentic Software Factories"](https://marmelab.com/blog/2026/05/22/software-factories-the-future-of-programming.html) article, is a smaller, unmaintained proof of concept by comparison. All are real, tested tools. Go use one of them if you want the durable version.

This is the Part 1 move applied one level up: build the naive version yourself, so the mechanism stops being magic. It is a few hundred lines, stdlib only, and it reuses this series' own parts directly instead of reinventing them, plus two ideas taken directly from `ai-factory`:

- The six gate checks (`describe` through `survive`) are plain file and content checks, no model call, the same discipline as `feature-pipeline/pipeline_check.py`.
- **`run one milestone` is not reimplemented.** It imports `core.run_agent` and `providers.create_provider` from this repo and calls them directly, the actual Part 1 loop, unmodified.
- **`scaffold`** writes a real starter file with proposed sections for the station you are blocked on, the same job `ai-factory`'s `/aif-docs` does for project documentation.
- **`--json`** on `status`/`advance` prints a machine-readable gate result, adapted from `ai-factory`'s `aif-gate-result` schema (status, blockers, a suggested next command) to this project's seven stations instead of its four.

## What each gate actually checks

| Station | Passes when |
|---|---|
| describe | `SPEC.md` exists and mentions platforms, a data model, boundaries, and milestone 1 |
| remember | `CLAUDE.md` or `AGENTS.md` exists, is under 60 lines, and points at at least one skill |
| pattern | every platform named in `SPEC.md` (android/iOS/web) has a matching `*-architecture` skill on disk |
| move | a deploy script exists (`scripts/release.py`, `release.py`, or `deploy.sh`), even a no-op one |
| see | a visual-baseline or golden-file directory exists and is non-empty |
| survive | a `SURVIVE.md` note exists, or a `# @survive:` tag is found in the code |
| run | delegates to the real agent loop, then re-checks `see` and `move` before counting the milestone shipped |

## Usage

```bash
python3 factory.py init ./my-new-app
python3 factory.py status ./my-new-app [--json]
python3 factory.py scaffold ./my-new-app
python3 factory.py advance ./my-new-app [--json]
python3 factory.py run-milestone ./my-new-app "build the signed-out home screen" --provider openai
```

State lives in `<project>/.factory/state.json`.

`scaffold` writes a starter file for whatever station is currently blocked, and never overwrites a file that already exists:

| Station | `scaffold` writes |
|---|---|
| describe | `SPEC.md`, with `Platforms:` / `Data model:` / `Boundaries:` / `Monetization:` / `Milestone 1:` placeholders |
| remember | `CLAUDE.md`, a thin starter with an `## Always` and a `## Skills` section |
| pattern | nothing. Architecture skills are meant to be reused across projects, so `scaffold` prints where to copy or write one instead |
| move | `scripts/release.py`, the same no-op `print("not wired yet")` stub the demo uses |
| see | `visual-testing/README.md`, pointing at where baselines belong |
| survive | `SURVIVE.md`, a placeholder asking whether this project touches money, email, or production data |

`--json` prints a fenced ` ```factory-gate-result ``` ` block after the normal human output: `schema_version`, `station`, `status`, `blocking`, a `blockers` list, and a `suggested_next` command, so an orchestrator can parse the last block instead of scraping prose.

## Try it

```bash
bash example/run_demo.sh
```

Walks a throwaway project through all seven stations, no API key needed. It shows an incomplete `SPEC.md` getting blocked, then walks describe through survive to a real PASS at each gate, then a bonus section scaffolding a fresh project and printing its `--json` gate result. The final `run-milestone` call is printed, not executed, since that step is the one that actually calls a model, everything before it is deterministic and free to check.

## Tests

```bash
python3 -m unittest test_factory -v
```

30 tests, stdlib only, no API key, no network. They cover every gate's pass and fail path, the state machine (init, blocked advance, multi-station advance, state persisting across process runs), `scaffold` for every station, and the `--json` payload shape for both a pass and a fail.

## Honest limits

- The gates check *presence*, not quality. A one-line `SPEC.md` that happens to contain the word "boundaries" passes `describe`. This proves the mechanism, it is not a substitute for actually reading the spec.
- `scaffold` does not dodge that limit, it demonstrates it. A freshly scaffolded `SPEC.md` contains the words "platform", "data model", "boundar", and "milestone 1" as section labels, so `describe` passes it before a single real word is written. What `scaffold` buys you is a place to write the real answer, not a shortcut past writing it.
- `pattern`'s platform detection is a keyword match on `SPEC.md`, not a real spec parser.
- `survive`'s code-tag scan is a regex over `.py` files. It does not verify the wrapping is correct, only that someone tagged it.
- There is no eval harness here. `hmzisb/software-factory` runs each case N times and scores against a baseline precisely because model output is probabilistic and file-presence checks cannot catch a bad implementation. `ai-factory`'s quality gates go further than presence checks too, but by having the agent itself judge correctness, not by running a statistical eval. This factory only guarantees the process was followed, never that the code is good.
