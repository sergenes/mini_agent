# Agent memory examples

Companion files for the Medium article **Your AI Agent Loads Two Memory/Instruction Files Every Turn. Keep Both Thin.** (Part 6, *Software Engineering in the Agentic AI Era*).

## This repo vs a production app

| Repo | Role |
|---|---|
| **this repo (`mini_agent`)** | Learning loop, visual testing, deploy template, and these example memory files |
| **a larger production app** (unnamed in the article) | Talks to Claude, Codex, Gemini, Grok, and Cursor. Same split applied there: thin always-on files plus skills |

## Always-on files in this repo (project)

| File | Who loads it |
|---|---|
| `CLAUDE.md` | Claude |
| `AGENTS.md` | Codex, Cursor, Grok (Grok also reads `CLAUDE.md`, so keep that one short) |
| `GEMINI.md` | Gemini (`~/.gemini/GEMINI.md` is the user-level twin) |

Those three at the repo root are the *project* index. They are short on purpose. Procedures live under `.claude/skills/` (and, for Codex, `.agents/skills/`; for Grok, `.grok/skills/`).

`.cursor/skills/` in this repo is a full copy of `.claude/skills/`, not a symlink, so Cursor picks the same skills up. Keep both in sync by hand, or replace the copy with a symlink locally; editing one side and forgetting the other is the easiest way to make this repo lie about itself.

## Portable pack (`agent-memory/`)

Copy onto a machine, not into every session.

| Path | Copy to |
|---|---|
| `common/CLAUDE.md` | `~/.claude/CLAUDE.md`, also paste into Cursor user rules; Codex: `~/.codex/AGENTS.md`; Gemini: `~/.gemini/GEMINI.md`; Grok: `~/.grok/` |
| `personal-skills/android-architecture/` | `~/.claude/skills/` and `~/.cursor/skills/` |
| `personal-skills/ios-architecture/` | same |
| `personal-skills/web-architecture/` | same |
| `personal-skills/new-project/` | same |
| `project/CLAUDE.md` | starter for a *new product* repo, not this Python agent |

## Skills note (accurate as of the article's publish date)

Skill folder locations differ by tool and change as each vendor ships updates. As of writing:

- Claude and Cursor: `.claude/skills/<name>/SKILL.md` and `.cursor/skills/<name>/SKILL.md`
- Codex: `.agents/skills/<name>/SKILL.md`, walked from the repo root down to the current directory
- Grok: `.grok/skills/<name>/SKILL.md` natively, plus it reads `.claude/skills/` and `.cursor/skills/` for compatibility with skills written for those tools
- Gemini: no native skill router at the time of writing; use `@file` imports and `/memory show` instead

Check each vendor's current docs before relying on a specific path, this table is a snapshot, not a promise.
