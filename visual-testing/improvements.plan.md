# ui_agent.py — Improvement Ideas

## 1. Text input / multi-step ADVANCE sequences

Support typing into form fields as part of the advancement gesture.

**Format** — semicolon-separated steps on one ADVANCE line:
```
tap 50% 28%; type "user@example.com"; tap 50% 45%; type "secret123"; tap 50% 78%
```

**Storage** in `index.json`:
```json
"advance": {"gesture": "sequence", "steps": [
  {"gesture": "tap",  "x": 0.50, "y": 0.28},
  {"gesture": "type", "text": "user@example.com"},
  {"gesture": "tap",  "x": 0.50, "y": 0.45},
  {"gesture": "type", "text": "secret123"},
  {"gesture": "tap",  "x": 0.50, "y": 0.78}
]}
```

**Execution** — `type` step: `System Events keystroke "text"` (Accessibility permission already required for window bounds). Android: `adb shell input text "..."`.

**Note** — test credentials end up in `baselines/index.json` (plain text). Use throwaway credentials, not real ones. Some apps autocorrect/autocapitalize — may need a dismiss-autocorrect tap or Return keystroke after each field.

---

## 2. Tap coordinate accuracy

LLM percentage estimates can be off by ~10% (estimated 93%, actual 82%), landing in the iOS home indicator gesture area. Current mitigation: prompt instructs the LLM to tap the text center of the button label and stay above 92% Y.

**Further ideas:**
- Overlay a coordinate grid on the screenshot before sending to the LLM so it can read off positions rather than estimate them visually.
- Ask the LLM for a bounding box (`x1% y1% x2% y2%`) and derive the tap from the box center — more robust than a single-point estimate.
- During `record`, after storing a tap, perform a test-tap and take a screenshot to verify the screen changed before saving. Retry the LLM if not.

---

## 3. Tap verification during record

After the LLM stores an ADVANCE gesture, immediately execute it as a dry run and check whether the screen changed. If the screen did NOT change, ask the LLM to try again before saving the baseline.

This catches wrong coordinates at record time rather than at check time in CI.

---

## 4. Local LLM support via Ollama (cost reduction)

Cloud vision calls get expensive at scale. The stored-advance optimization already cuts calls to 1 per step on the happy path — but that's still N calls per flow per CI run.

**Vision-capable models in Ollama:**

| Model | Size | Multi-image | Strength |
|-------|------|-------------|----------|
| `llama3.2-vision:11b` | 11B | Yes | Best instruction following |
| `qwen2.5vl:7b` | 7B | Yes | Strong on UI/screenshots |
| `minicpm-v` | 8B | Yes | Good at comparison |
| `moondream` | 1.6B | No | Too small, can't compare two images |

**Task difficulty mapping:**
- LABEL / REVIEW (CAPTURE_PROMPT): easy — local models handle fine
- MATCH / MISMATCH: medium — local models reach ~80-85% accuracy vs Claude ~95%
- TAP coordinates (TAP_PROMPT): hard — spatial precision is where small models fail most

**Proposed `--vision-model` flag:**
- `claude` — current default, Anthropic API
- `local` — Ollama for everything (cheapest, slightly lower accuracy)
- `hybrid` — Ollama for MATCH/MISMATCH (frequent, cheap task), Claude only for TAP (rare, needs precision)

Hybrid is the sweet spot: MATCH runs every step on every CI run; TAP only fires on regressions.

**Implementation:** `_vision_call` gets an optional `model_override` parameter. Ollama exposes an OpenAI-compatible API with base64 image support — same pattern already used in `providers.py`.

```python
# Ollama vision call (OpenAI-compatible endpoint)
client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
response = client.chat.completions.create(
    model="llama3.2-vision",
    messages=[{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        {"type": "text", "text": prompt},
    ]}],
)
```

---

## 5. Back-navigation check

The flow spec can describe back gestures (swipe left, hardware back), but `check` mode never exercises them — it only checks the forward path. A `--check-back` flag could verify that each step also supports back navigation correctly.

---

## 6. Platform-specific prompts and tap conventions

**Storage separation — done.** `record`/`check`/`check-all` now keep fully separate baseline directories per platform (`baselines-ios/`, `baselines-android/`, each with its own `index.json`), in both `ui_agent.py` and `ui_agent_local.py`. A flow name is only unique within its own platform's directory, so the same name can exist independently on both. `cmd_check_all` with no `--ios`/`--android` flag loads and runs both directories' flows together.

**Still open — platform-aware prompts.** The LLM prompts (`_capture_prompt`, `_match_prompt`, `_tap_prompt`) are still identical for both platforms. iOS and Android have different navigation idioms (iOS home indicator gesture area vs. Android nav bar/back button, different system UI chrome, different standard tap targets), so the prompt should tell the LLM which platform it's looking at and adjust the unsafe-tap-zone guidance accordingly (the current 85% Y clamp is tuned for iOS's home indicator; Android's gesture nav bar sits at a different height and devices vary more in aspect ratio).

**Proposed:** thread a `platform: "ios" | "android"` string (already known at call time via `_platform(args)`) into all three prompt builders. Use it to pick platform-appropriate phrasing ("avoid the gesture bar at the bottom" vs. "avoid the home indicator") and a platform-specific Y clamp instead of one hardcoded value for both.

---

## 7. Launch the app and reset state before each flow

`record` and `check` both assume the app is already running and on the right screen — there's no automated way to cold-launch the app or reset it to a known state before a flow starts. This means every CI run depends on whatever state the simulator/emulator was left in, which defeats the point of having a deterministic baseline.

**Proposed:**
- iOS: `xcrun simctl launch booted <bundle-id>` (and `xcrun simctl terminate` first to force a cold start) before the first step of `record`/`check`.
- Android: `adb shell am start -n <package>/<activity>` after `adb shell pm clear <package>` (or `am force-stop`) to reset app state and storage before launch.
- New flags: `--bundle-id` (iOS) / `--package` (Android), stored once in `index.json` per flow so `check` and `check-all` can relaunch automatically without re-typing them.
- Pairs naturally with the demo-mode pattern already described in the article: relaunching into a demo-flagged build gives every check run the same deterministic starting state, with no manual reset step before each run.
