---
name: visual-check
description: >-
  Record and check iOS and Android UI flows with ui_agent.py (cloud) or
  ui_agent_local.py (Ollama). Use when recording a visual baseline, running
  check or check-all, debugging simulator taps, or editing files under
  visual-testing/.
---

# Visual check

All files live in `visual-testing/`. Run from that directory (`cd visual-testing`).

| File | Role |
|---|---|
| `ui_agent.py` | `record`, `check`, `check-all` (Anthropic) |
| `ui_agent_local.py` | same CLI, local Ollama |
| `mobile_tools.py` | Simulator + adb screenshot / tap / swipe |
| `requirements-ui.txt` | `anthropic`, `pillow` |
| `requirements-ui-local.txt` | `openai` (Ollama client), `pillow` |

Baselines: `visual-testing/baselines-ios/` and `baselines-android/`, each with `index.json`. Same flow name can exist on both platforms.

**Record:** optional `--describe`. Human navigates, Enter to capture. LLM writes LABEL/REVIEW/ADVANCE. Gestures stored per step.

**Check:** screenshot, MATCH/MISMATCH. MATCH replays the stored gesture. MISMATCH asks for a gesture, retries `--max-retries`.

Description in `index.json` is threaded into capture, match, and tap prompts.

iOS tap/swipe: CoreGraphics `CGEventPost` via JXA. Needs Terminal Accessibility to read window bounds. Android: `adb shell input`, size from `adb shell wm size`. Tap Y clamped to ≤ 0.85 for the iOS home indicator.

Do not add `idb` or libimobiledevice. Physical iOS devices are not supported (no screenshot service on iOS 17+). Use the Simulator.

Semantic vision: layout and elements, not pixel diff.
