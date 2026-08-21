# Common memory

User-level. Travels across repositories. Keep this file small enough to paste into a new machine without editing it down first.

Copy it to each tool's user-level slot so you are not maintaining five handbooks:

- Claude Code: `~/.claude/CLAUDE.md`
- Codex CLI: `~/.codex/AGENTS.md`
- Gemini CLI: `~/.gemini/GEMINI.md`
- Grok CLI: `~/.grok/` (Grok also reads `AGENTS.md` / `CLAUDE.md` in the repo)
- Cursor: user rules, plus `~/.cursor/skills/` for personal skills

The body below stays the same in every copy.

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
