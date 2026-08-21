# Project memory (example: a new mobile+web product)

Always-on for *this* repo. Identity, hard rules, index. Not the Android skill, not the deploy script.

## What this is

Native Android and iOS apps plus a small web client for the same product. Shared API contract. Companion agent tooling lives in github.com/sergenes/mini_agent.

## Always

- Do not commit secrets or credentials.
- Do not invent a new architecture. Load `android-architecture`, `ios-architecture`, or `web-architecture` before writing platform code.
- Do not invent a new deploy path. The pipeline is `release.py`.
- Do not invent a new home for a feature. Search the matching feature folder first.

## Skills

Project skills (this repo):

- `deploy`: TestFlight and Play uploads, `--ios` / `--android` flags
- `visual-check`: record/check flows with `ui_agent.py`

Personal skills (user-level, already referenced from common memory):

- `android-architecture`
- `ios-architecture`
- `web-architecture`

Product facts worth looking up (not copied here): `docs/` for the API contract and billing. Open the file the task needs.

<!-- mirror of CLAUDE.md in this folder. Keep them in sync. -->
