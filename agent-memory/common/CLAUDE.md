# Common memory

User-level. Travels across repositories. Keep this file small enough to paste into a new machine without editing it down first.

Copy it to each tool's user-level slot so you are not maintaining five handbooks:

- Claude Code: `~/.claude/CLAUDE.md`
- Codex CLI: `~/.codex/AGENTS.md`
- Gemini CLI: `~/.gemini/GEMINI.md`
- Grok CLI: `~/.grok/` (Grok also reads `AGENTS.md` / `CLAUDE.md` in the repo)
- Cursor: user rules, plus `~/.cursor/skills/` for personal skills

The body below stays the same in every copy.

## General guidelines

- When writing commit messages, never auto-add the agent's name as co-author.
- When making technical decisions, do not weigh development cost heavily. Prefer quality, simplicity, robustness, scalability, and long-term maintainability.
- When fixing a bug, start by reproducing it end-to-end, as close as possible to how a real user would trigger it. That is how you find the real problem instead of patching a symptom.
- Hold the same bar for engineering hygiene: lint errors, failing tests, flaky tests. Fix one on sight, even if it is not what you are currently working on.

## Always

- Ask before committing. Never skip hooks.
- Do not dump secrets, `.env` files, or credentials into the repo.
- Prefer a surgical change over a rewrite you were not asked for.
- If a workflow has a skill, load the skill. Do not reconstruct it from nearby files.

## New repos

When the task is a greenfield app or an empty repository, load `new-project` before writing a feature. That skill is the start loop: describe, remember, pattern, move, see, survive, then one milestone.

## Architecture defaults

When the task is Android, iOS, or web, load the matching skill before writing code. Do not invent a competing pattern.

- Android: `android-architecture` (MVVM, `:app` / `:domain` / `:data`, Compose, Hilt)
- iOS: `ios-architecture` (MVVM, SwiftUI, `@Observable`, async/await)
- Web: `web-architecture` (screen / state / client split, TypeScript)

Do not copy those skills into this file. The `description` field on each skill is how they get loaded on the right turn.
