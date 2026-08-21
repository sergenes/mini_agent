# factory.py — a naive software factory

A state machine that holds the seven-station loop from Part 7 together: **describe → remember → pattern → move → see → survive → run one milestone.** A project cannot advance past a station whose gate is not actually satisfied on disk, checked fresh every time, not trusted from last time.

## What this is not

This is not a competitor to real agentic-harness projects. [github/spec-kit](https://github.com/github/spec-kit) is GitHub's own official spec-driven-development toolkit, six phases, 30+ agent integrations. [hmzisb/software-factory](https://github.com/hmzisb/software-factory) is a Claude Code skill that scaffolds a 7-agent team, guardrail hooks, and a probabilistic eval harness, built on marmelab's ["Agentic Software Factories"](https://marmelab.com/blog/2026/05/22/software-factories-the-future-of-programming.html) article and their hand-built [crm-builder](https://github.com/marmelab/crm-builder) reference factory. Those are real, tested, production-oriented tools. Go use them if you want the real thing.

This is the Part 1 move applied one level up: build the naive version yourself, so the mechanism stops being magic. It is a few hundred lines, stdlib only, and it reuses this series' own parts directly instead of reinventing them:

- The six gate checks (`describe` through `survive`) are plain file and content checks, no model call, the same discipline as `feature-pipeline/pipeline_check.py`.
- **`run one milestone` is not reimplemented.** It imports `core.run_agent` and `providers.create_provider` from this repo and calls them directly, the actual Part 1 loop, unmodified.

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
python3 factory.py status ./my-new-app
python3 factory.py advance ./my-new-app
python3 factory.py run-milestone ./my-new-app "build the signed-out home screen" --provider openai
```

State lives in `<project>/.factory/state.json`.

## Try it

```bash
bash example/run_demo.sh
```

Walks a throwaway project through all seven stations, no API key needed. It shows an incomplete `SPEC.md` getting blocked, then walks describe through survive to a real PASS at each gate. The final `run-milestone` call is printed, not executed, since that step is the one that actually calls a model, everything before it is deterministic and free to check.

## Tests

```bash
python3 -m unittest test_factory -v
```

22 tests, stdlib only, no API key, no network. They cover every gate's pass and fail path plus the state machine (init, blocked advance, multi-station advance, state persisting across process runs).

## Honest limits

- The gates check *presence*, not quality. A one-line `SPEC.md` that happens to contain the word "boundaries" passes `describe`. This proves the mechanism, it is not a substitute for actually reading the spec.
- `pattern`'s platform detection is a keyword match on `SPEC.md`, not a real spec parser.
- `survive`'s code-tag scan is a regex over `.py` files. It does not verify the wrapping is correct, only that someone tagged it.
- There is no eval harness here. `hmzisb/software-factory` runs each case N times and scores against a baseline precisely because model output is probabilistic and file-presence checks cannot catch a bad implementation. This factory only guarantees the process was followed, never that the code is good.
