---
name: new-project
description: >-
  Bootstrap a new product repository for agentic development. Use when starting
  a new app, empty repo, greenfield project, or when the user asks to stand up
  the factory, the start loop, or what to install before the first feature.
---

# New project

Do not write a feature until this loop has run once. The loop is the product spine. Features go through it after it exists.

## 1. Describe

Write a spec that answers, before any screen exists:

- Platforms this product will eventually support
- Data model for the mature product, not the demo
- Monetization, if there will be any
- Boundaries: where a kind of feature lives, what the agent must not invent
- Milestone 1: one deliverable, acceptance criteria, explicit non-goals

You are allowed to change the spec. You are not allowed to skip it.

## 2. Remember

Copy user-level common memory if this machine does not have it yet (`agent-memory/common/CLAUDE.md`).

In the new repo, write a short `CLAUDE.md` / `AGENTS.md` that names the product, the hard rules, and the skills. Do not paste architecture tutorials into that file.

## 3. Pattern

For each platform in the spec, load the matching architecture skill before generating files:

- Android: `android-architecture`
- iOS: `ios-architecture`
- Web: `web-architecture`

If the spec names a platform that has no skill, write the skill first (folders, default libraries, one pattern). Do not let the first generated file pick a pattern by accident.

## 4. Move

Add a one-command path to put a build in front of testers or on a staging URL. An empty script that prints "not wired" is progress. Opening Xcode Organizer or a cloud console as the release process is not. Details: Part 5 of the series, `release.py` in mini-agent.

## 5. See

Decide how you will look at what the agent produced without sitting through every screen.

- UI product: visual record/check (Part 4) or a screenshot skill. Prefer a demo data source so checks do not chase a live API.
- Library or CLI: a golden-output test or a scripted walkthrough with an exit code.

A green unit suite is not this station.

## 6. Survive

If a tool will charge a card, send email, or write production data, wrap it before the first call. Retry, a circuit breaker, and a way to undo. Part 2. Skip this station only for read-only toys.

## 7. Run one milestone

Only now: one scoped prompt against the spec, the project memory, and the matching skills. When it is done, see, then move.

Next milestone repeats from step 7. Steps 1-6 get edited when the product changes, not reinvented when a screen is added.
