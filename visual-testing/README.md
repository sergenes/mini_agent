# Visual Testing

LLM-driven visual flow testing for iOS Simulator and Android. **No pixel comparison, no coordinate hunting** — the LLM looks at screenshots and judges by visual intent.

Part of the [mini_agent](../README.md) project. Accompanies the Medium article series:
- **Part 4:** [Give Your Testing Agent Eyes: A Visual Testing Agent from Scratch](https://medium.com/@sergey-nes/give-your-testing-agent-eyes-a-visual-testing-agent-from-scratch-f52a63ce72ed)

---

## Files

| File | Role |
|------|------|
| `ui_agent.py` | CLI — `record`, `check`, `check-all` modes (Anthropic Claude or OpenAI backend, picked by `--model`) |
| `ui_agent_local.py` | Same CLI, local Ollama backend (zero cloud cost) |
| `mobile_tools.py` | iOS Simulator + Android screenshot / tap / swipe helpers |
| `requirements-ui.txt` | `anthropic`, `openai`, `pillow` |
| `requirements-ui-local.txt` | `openai` (Ollama client), `pillow` |

Baselines (screenshots + navigation map) are saved per platform, in `baselines-ios/` or `baselines-android/`. A flow name is only unique within its own platform directory, so `myapp-onboarding` can be recorded separately for iOS and Android without collision.

The repo includes a real recorded example — a 6-screen onboarding flow, captured on both platforms with `record`, checked out as-is so you can see the shape of the output:

```
baselines-ios/
├── index.json                       # one entry: "myapp_onboarding" → 6 steps, each with
│                                     #   label, design review note, and advance gesture
├── myapp_onboarding_step_01.png
├── ...
└── myapp_onboarding_step_06.png

baselines-android/
├── index.json                       # same flow name, recorded independently — its own
│                                     #   screenshots, gestures, and (slightly different) Y taps
├── myapp_onboarding_step_01.png
├── ...
└── myapp_onboarding_step_06.png
```

Run `python ui_agent.py check --ios "myapp-onboarding"` or `--android` against these directly to see a check pass without recording anything yourself first.

---

## How it works

**Record** — you navigate the app manually, pressing Enter at each screen. Before the first capture you describe the flow in plain English: navigation gestures, key elements per screen, assertions to verify. The LLM uses that spec to label each screen, note design issues, and determine the advancement gesture (tap position or swipe direction) for each step. Both the screenshots and the navigation map are saved to `baselines-ios/` or `baselines-android/`, depending on `--ios`/`--android`.

**Check** — runs one named flow autonomously. For each step the LLM compares the current screen to the baseline (MATCH / MISMATCH). On MATCH it applies the stored advancement gesture directly — no extra LLM call. On MISMATCH it falls back to asking the LLM where to gesture, retries up to `--max-retries` times, then marks the step FAIL.

**Check-all** — runs every recorded flow in sequence and prints a combined pass/fail summary. Filter by platform with `--ios` or `--android`, or omit to run everything.

Gestures on iOS Simulator use CoreGraphics `CGEventPost` via JXA — taps and swipes, built-in macOS, no extra installs. Android gestures use `adb shell input`.

---

## Flow spec

A plain-English description of the flow written once at record time and used on every check run. The more precise the spec, the more accurate the LLM's gesture inference and visual assertions.

**Example — onboarding flow:**

```
5-screen iOS onboarding.

Navigation:
- Screens 1–4: tap "Continue" button (bottom-center) or swipe right to advance
- Screens 2–5: swipe left to go back; screen 1 has no back navigation

Screens:
  1. Welcome splash — app logo centered, tagline below, "Continue" button
  2. Feature highlights — illustrated feature cards with descriptions, "Continue" button
  3. Permissions — notification and location permission toggles, "Continue" button
  4. Scan QR code — camera viewfinder, QR code overlay, instructional text, "Continue" button
  5. Setup complete — success message, "Get Started" button;
     below the button: "Terms of Service" and "Privacy Policy" text links
     that must open an external browser when tapped

Assertions:
- "Terms of Service" link is visible and tappable on screen 5
- "Privacy Policy" link is visible and tappable on screen 5
```

Pass it with `--describe "..."` or enter it at the interactive prompt when you run `record`.

---

## Setup

### Cloud backend (Anthropic Claude or OpenAI)

```bash
pip install -r requirements-ui.txt
```

`ui_agent.py` picks the provider from `--model`: Claude model names (e.g. `claude-sonnet-4-6`, the default) route to Anthropic; anything starting with `gpt-` (e.g. `gpt-4o`) routes to OpenAI. Add whichever key(s) you need to `.env` in the project root:
```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

### Local backend (Ollama)

```bash
pip install -r requirements-ui-local.txt

# Install Ollama: https://ollama.com
ollama pull llama3.2-vision:11b   # ~7 GB download
ollama serve                       # keep running in a separate terminal
```

---

## iOS Simulator — one-time setup

### 1. Boot a Simulator

```bash
# list all available simulators
xcrun simctl list devices available

# boot the one you want (use the exact name from the list above)
xcrun simctl boot "iPhone 17 Pro"

# open Simulator.app so the window appears on screen
open -a Simulator
```

### 2. Turn off device bezels

In the Simulator menu bar: **Simulator → Window → Show Device Bezels → off**

This ensures the simulated screen fills the full window rectangle. With bezels on, the content inset can't be computed exactly and taps may land in the wrong place.

### 3. Grant Accessibility permission to your terminal

`osascript` needs to read the Simulator window position and size (to convert percentage-based tap coordinates into screen coordinates). This is the only step that requires Accessibility.

- Open **System Settings → Privacy & Security → Accessibility**
- Click the **`+`** button
- Navigate to `/Applications/Utilities/` and select **Terminal.app**
  (or your terminal of choice — iTerm2 is at `/Applications/iTerm.app`)
- Make sure the toggle next to it is **on** (blue)

> **Note on Python:** If you launch `ui_agent.py` from VS Code's integrated terminal, from a script, or from a process that's not Terminal.app, that process must have its own Accessibility entry. The process that runs `osascript` is the one that needs permission, not Python itself. When you run `python ui_agent.py` in Terminal, the parent process is Terminal — so Terminal is the one to add.
>
> If in doubt, run `ps -p $(ps -p $PPID -o ppid= | tr -d ' ') -o comm=` to see the grandparent process name. That is the app to add to Accessibility.

### 4. Tap mechanism — no extra permission needed

`ui_agent.py` taps the Simulator using macOS CoreGraphics **`CGEventPost`** via JXA (JavaScript for Automation). This sends a real hardware-level mouse event — the same as physically clicking — so the Simulator registers it as a touch. No Accessibility permission is needed for this step.

> Background: an earlier approach used `System Events click at {x, y}`, which sends an *accessibility press* action rather than a mouse button event. The Simulator ignores accessibility presses, so clicks appeared to succeed (no error) but nothing happened on screen. `CGEventPost` at the HID level fixes this.

### 5. Verify the setup

With the Simulator window open and on screen:

```bash
# Step A — read the window bounds (needs Accessibility permission for Terminal)
osascript -e '
tell application "System Events"
    set proc to first process whose name is "Simulator"
    set win to first window of proc
    set {wx, wy} to position of win
    set {ww, wh} to size of win
    return (wx as string) & "," & (wy as string) & "," & (ww as string) & "," & (wh as string)
end tell'
# → prints something like:  311,87,456,972
#   meaning: window left=311 top=87 width=456 height=972
```

Calculate the center of the content area (title bar is ~28pt):
```
center_x = left + width/2            → 311 + 228 = 539
center_y = top + 28 + (height-28)/2  → 87 + 28 + 472 = 587
```

```bash
# Step B — send a real hardware tap to the center (no Accessibility needed)
osascript -l JavaScript -e '
ObjC.import("CoreGraphics");
var pt = $.CGPointMake(539, 587);
var dn = $.CGEventCreateMouseEvent(null, $.kCGEventLeftMouseDown, pt, $.kCGMouseButtonLeft);
var up = $.CGEventCreateMouseEvent(null, $.kCGEventLeftMouseUp,   pt, $.kCGMouseButtonLeft);
$.CGEventPost($.kCGHIDEventTap, dn);
$.CGEventPost($.kCGHIDEventTap, up);
'
# → the Simulator should register a tap at the center of the screen
```

Replace `539, 587` with coordinates from your own window bounds. If the tap visually registers (you see a tap ripple or the UI responds), the setup is complete.

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Step A` prints an error or nothing | Terminal lacks Accessibility permission | System Settings → Privacy & Security → Accessibility → add Terminal.app |
| `Step A` works but `Step B` tap doesn't register | Simulator window not in focus | The tool activates Simulator automatically before each tap. If it still fails, make sure no other window is covering the Simulator. |
| `RuntimeError: Could not find Simulator window` | Simulator.app is closed | Run `open -a Simulator` and wait for the window to appear |
| `RuntimeError: CGEventPost tap failed` with a non-zero exit | JXA script error | Verify `osascript -l JavaScript -e 'ObjC.import("CoreGraphics"); "ok"'` prints `ok` |
| Tap lands in wrong position after moving the window | Window bounds are read at tap time | Bounds are always live — move the window freely, no reconfiguration needed |
| Multiple monitors with negative X coordinates | Secondary display to the left | This is normal; CGEventPost handles negative coordinates correctly |

---

## Android emulator setup

```bash
# List available virtual devices
~/Library/Android/sdk/emulator/emulator -list-avds

# Boot one (runs in the foreground — use & to background it, or open a new terminal tab)
~/Library/Android/sdk/emulator/emulator -avd Pixel_9_Pro &

# Wait for it to finish booting, then verify it appears
~/Library/Android/sdk/platform-tools/adb devices
# → List of devices attached
#   emulator-5554	device
```

> **Apple Silicon (M1/M2/M3...):** use `~/Library/Android/sdk/emulator/emulator`, not the legacy `~/Library/Android/sdk/tools/emulator`. The `tools/` binary is an old shim that looks for the Intel (`darwin-x86_64`) QEMU backend, which doesn't exist on arm64 Macs, and fails with `Could not launch '.../qemu/darwin-x86_64/qemu-system-aarch64': No such file or directory`. The real binary under `emulator/` picks the correct `darwin-aarch64` backend.
>
> **Add to PATH (optional but recommended)** so you can run `emulator` and `adb` directly instead of typing the full path every time:
> ```bash
> echo 'export PATH="$HOME/Library/Android/sdk/emulator:$HOME/Library/Android/sdk/platform-tools:$PATH"' >> ~/.zshrc
> source ~/.zshrc
> ```
> `mobile_tools.py` doesn't depend on this — it resolves `adb` itself via `PATH`, then `ANDROID_HOME`/`ANDROID_SDK_ROOT`, then the default SDK location, so `ui_agent.py`/`ui_agent_local.py` work even if `adb` isn't on PATH in the shell that launched Python (this matters for IDE-integrated terminals, which don't always inherit the same PATH as Terminal.app).

Screen resolution is read live from `adb shell wm size` — no hardcoded dimensions.

---

## Recording a flow

Navigate your app to the starting screen, then run:

```bash
python ui_agent.py record --ios "myapp-onboarding"
```

The tool enters a capture loop — navigate to each screen, press Enter, and the LLM labels it and notes any design issues automatically. No approval, no manual labelling:

```
Recording flow: myapp-onboarding

Describe this flow so the LLM knows the navigation gestures and what to verify.
Example: "6-screen onboarding. Tap Continue to advance. Last screen has ToS and Privacy links."
Flow description (or Enter to skip): 6-screen onboarding. Tap "Continue" (bottom-center) to advance on screens 1–5. Last screen has "Terms of Service" and "Privacy Policy" links.

Navigate to each screen, then press Enter to capture. Type 'done' to finish.

Step 1 — press Enter to capture, or 'done' to finish:
  Taking screenshot...
  Analysing...
  ✓ welcome splash screen
  → advance: tap (50%, 87%)

Step 2 — press Enter to capture, or 'done' to finish:
  Taking screenshot...
  Analysing...
  ✓ feature highlights slide
  → advance: tap (50%, 87%)
  ⚠ Download button contrast is slightly low against the teal background.

Step 3 — press Enter to capture, or 'done' to finish: done
Flow saved: 2 step(s) → baselines-ios/myapp_onboarding_step_*.png
```

Between captures, navigate the app yourself — tap the simulator with your mouse, swipe, use hardware buttons. The tool only captures; you drive.

---

## Checking for regressions

After a code change, run check. No navigation needed — the LLM drives the simulator:

```bash
python ui_agent.py check --ios "myapp-onboarding"

# Or use OpenAI instead of Claude
python ui_agent.py check --ios --model gpt-4o "myapp-onboarding"
```

```
Checking flow: myapp-onboarding (2 step(s))

Step 1/2: welcome splash screen
  [1] MATCH
       → stored tap (50%, 87%)
  PASS

Step 2/2: feature highlights slide
  [1] MISMATCH — the headline text is smaller and the illustration is missing
       → tapping (50%, 82%)
  [2] MATCH
       → stored tap (50%, 87%)
  PASS

────────────────────────────────────────
  ✓ splash screen
  ✓ feature highlights
────────────────────────────────────────
Overall: PASS
```

The LLM compares screenshots semantically — same elements, same layout, same intent. Minor rendering differences are ignored. If a step mismatches, it taps to advance and retries (up to `--max-retries`, default 5).

Exit code is `0` on PASS, `1` on FAIL — plug directly into CI:
```bash
python ui_agent.py check --ios "myapp-onboarding" && ./deploy.sh
```

---

## Running all flows at once

```bash
python ui_agent.py check-all --ios
```

```
══════════════════════════════════════════════════
  myapp-onboarding  [ios]
══════════════════════════════════════════════════
Checking flow: myapp-onboarding (2 step(s))
Step 1/2: splash screen
  [1] MATCH
  PASS
...

══════════════════════════════════════════════════
  SUMMARY
══════════════════════════════════════════════════
  ✓  myapp-onboarding
  ✓  myapp-signin
  ✗  myapp-purchase
       ✗ payment confirmation screen
══════════════════════════════════════════════════
  Overall: FAIL
══════════════════════════════════════════════════
```

Exit code is `0` if all flows pass, `1` if any fail.

---

## Running with a local model (Ollama)

`ui_agent_local.py` routes all vision calls to a local Ollama model. No API key, no cloud cost for check runs.

```bash
python ui_agent_local.py record --ios "myapp-onboarding"
python ui_agent_local.py check  --ios "myapp-onboarding"
python ui_agent_local.py check-all --ios
```

Override the model:
```bash
python ui_agent_local.py check --ios --model qwen2.5vl:7b "myapp-onboarding"
```

Point to a remote Ollama instance:
```bash
OLLAMA_HOST=http://192.168.1.10:11434 python ui_agent_local.py check --ios "myapp-onboarding"
```

### Supported vision models

| Model | Pull command | RAM needed | Notes |
|-------|-------------|------------|-------|
| `llama3.2-vision:11b` _(default)_ | `ollama pull llama3.2-vision:11b` | ~8 GB | Best instruction following |
| `qwen2.5vl:7b` | `ollama pull qwen2.5vl:7b` | ~5 GB | Strong on UI screenshots |
| `minicpm-v` | `ollama pull minicpm-v` | ~6 GB | Good multi-image comparison |

All three support multiple images in one call, which is required for the MATCH and TAP prompts.

### Expectations vs. cloud Claude

| Task | Cloud (Claude) | Local (llama3.2-vision) |
|------|---------------|------------------------|
| MATCH / MISMATCH accuracy | ~95% | ~80-85% |
| Tap coordinate precision | High | Medium — may need more retries |
| Format compliance | Strict | Occasional extra text, parsed best-effort |
| First-call latency | ~1-2s | ~10-30s (model load), then ~2-5s/call |
| Cost per check run | ~$0.01–0.05 | $0 |

**Baselines are shared between backends, not between platforms** — `baselines-ios/index.json` and `baselines-android/index.json` (and their PNGs) work with both `ui_agent.py` and `ui_agent_local.py`. Record with one backend, check with either, as long as you stay on the same `--ios`/`--android` flag.

---

## Command reference

**iOS Simulator**
```bash
python ui_agent.py record --ios "myapp-onboarding"
python ui_agent.py record --ios "myapp-signin"
python ui_agent.py record --ios "myapp-onboarding" --model gpt-4o

python ui_agent.py check      --ios "myapp-onboarding"
python ui_agent.py check      --ios "myapp-onboarding" --model gpt-4o
python ui_agent.py check-all  --ios                      # run all iOS flows
python ui_agent.py check-all                             # run every recorded flow
```

**Android emulator / device**
```bash
python ui_agent.py record    --android "myapp-onboarding"
python ui_agent.py check     --android "myapp-onboarding"
python ui_agent.py check-all --android
```

**Local Ollama backend**
```bash
python ui_agent_local.py record --ios "myapp-onboarding"
python ui_agent_local.py check  --ios "myapp-onboarding"
python ui_agent_local.py check-all --ios
```

**Options**

| Flag | Default | Description |
|------|---------|-------------|
| `--describe` | _(prompted at record time)_ | Flow spec: navigation gestures, key elements, assertions |
| `--model` | `claude-sonnet-4-6` | Vision LLM model. Any Claude model name uses Anthropic; a model starting with `gpt-` (e.g. `gpt-4o`) uses OpenAI instead |
| `--expect` | _(stored at record time)_ | Extra assertion appended to every check |
| `--max-retries` | `5` | Gesture attempts per step before marking FAIL |
| `--ios` | — | Use iOS Simulator |
| `--android` | — | Use Android emulator/device |

---

## Notes

- **One flow per name, per platform.** The name you pass is the storage key within that platform's `baselines-<platform>/index.json`. Recording the same name again on the same platform asks for confirmation before overwriting; the same name on the other platform is a separate, independent flow.
- **Between record steps, navigate yourself.** The tool captures; you drive. Tap the simulator window with your mouse, swipe, use hardware button shortcuts — whatever gets you to the next screen.
- **Check is fully hands-free.** On MATCH the tool applies the stored advancement gesture (tap or swipe) with no extra LLM call. On MISMATCH it asks the LLM where to gesture and retries. Gestures use CoreGraphics `CGEventPost` — real hardware-level mouse events the Simulator registers as actual touches.
- **Swipe support.** Both `swipe right` and `swipe left` are stored and replayed. The iOS Simulator receives 10 drag events across the screen width so it recognises the motion as a gesture.
- **The flow spec is your test contract.** Describing the navigation and assertions once at record time means every subsequent `check` run validates against those same criteria automatically — no `--expect` flag needed.
- **Physical iOS devices are not supported.** Apple removed the screenshotr service on iOS 17+. Use the Simulator.
- **Tap Y clamp.** Both agents clamp tap Y coordinates to ≤ 85% to stay clear of the iOS home indicator gesture area. The local agent (`ui_agent_local.py`) enforces this in code as a hard cap, since small models tend to estimate coordinates too low.

---

## Roadmap

Ideas not yet implemented, full detail in [`improvements.plan.md`](improvements.plan.md):

- **Text input gestures** — `type "text"` steps in the ADVANCE sequence, so flows can fill in forms (login, search) instead of stopping at tap/swipe.
- **Tap coordinate accuracy** — grid overlay or bounding-box prompts so the LLM reads off a position instead of estimating it, plus a record-time dry-run tap to catch bad coordinates before they're saved.
- **`--vision-model hybrid`** — local Ollama for the frequent MATCH/MISMATCH check, cloud model only for the rare TAP-recovery call, to cut cost without losing tap precision.
- **`--check-back`** — exercise the back-navigation gestures already described in the flow spec, not just the forward path.
- **Platform-aware prompts** — baselines are already split per platform (`baselines-ios/`, `baselines-android/`); next step is threading `ios`/`android` into the LLM prompts and tap-zone clamp too, instead of using one iOS-tuned convention for both.
- **Launch + reset before each run** — cold-launch the app (`simctl launch` / `adb shell am start`) and reset its state (`pm clear` / fresh install) before `record`/`check`, so every run starts from the same deterministic state instead of whatever was left on screen.

---

## A note on this project

This is a working proof-of-concept, not a production tool. It demonstrates that LLM-driven visual regression testing is genuinely feasible with surprisingly little code — but there are real gaps before it could be relied on in CI at scale: accuracy variance across LLM providers, latency on every check step, no support for physical iOS devices, and tap coordinate precision that depends on how well the model reads a screenshot.

I built this to show the idea is real, not to finish it. The goal is to inspire — whether that means someone adapts it for their own app, takes it further as an open-source project, or builds a proper product on top of it.

If you have the desire (or the funding) to turn this into something serious, I'd genuinely love to be involved in building it. Reach me on [LinkedIn](https://www.linkedin.com/in/sergey-neskoromny/) or [Medium](https://sergey-nes.medium.com/).
