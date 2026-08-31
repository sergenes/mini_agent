# Feature pipeline check

A convention of three files, `open` a source of truth for what is not done, `staging` for what is implemented but not verified, and `log` an append-only record of what actually shipped, is only as honest as the person updating it by hand. `pipeline_check.py` turns that promise into something a script verifies.

It is generic on purpose: file names, headings, and item formats are not hardcoded to this repo's own `todo.md` / `testing.md` / `releases.md`. Point it at whatever three files your team already uses for the same open → staging → log shape.

## What it checks

1. **No item stuck in both `open` and `staging`.** An item that moved to staging but never got removed from open is exactly the drift this pipeline exists to catch.
2. **`log` is append-only.** Every entry already committed to git must still be present, unchanged, as a contiguous block inside the current file. New entries may only be added, conventionally at the top.
3. **New `log` entries cite evidence.** Any entry added since the last commit must contain a URL, a file path, or a commit-like hash. "Shipped, looks good" with nothing to point at does not pass.

Any check can be skipped with `--skip stuck`, `--skip append-only`, or `--skip evidence` (repeatable) if your process does not need all three.

## Item and entry format

- `open` and `staging` items are either checkbox lines (`- [ ] Title` / `- [x] Title`) or headings (`## Title`, `## 3. Title`). Items are matched across the two files by title text, normalized (numbering, bold markers, and `[YYYY-MM-DD]` date tags stripped, case-insensitive).
- `log` entries are top-level `## ` headings. Everything before the first `## ` (a title, a short note) is treated as a preamble and ignored by the append-only and evidence checks.

## Usage

```bash
python3 pipeline_check.py --open todo.md --staging testing.md --log releases.md
```

Defaults to `todo.md`, `testing.md`, and `releases.md` in the current directory if the flags are omitted. Exit code is `0` if every requested check passes, `1` otherwise, so it drops into a pre-commit hook or a CI step directly:

```bash
# .git/hooks/pre-commit, or a CI step
python3 feature-pipeline/pipeline_check.py --open docs/todo.md --staging docs/testing.md --log docs/releases.md || exit 1
```

Missing files are treated as empty, not as errors, so it is safe to run before any of the three files exist yet.

## Try it

`example/` has a working before/after pair. From this directory:

```bash
cd example
python3 ../pipeline_check.py --open todo.md --staging testing.md --log releases.md
```

Passes clean. Edit `releases.md` to remove or reword the existing entry and rerun it, it fails the append-only check. Add a new entry with no link or file path and rerun it, it fails the evidence check.
