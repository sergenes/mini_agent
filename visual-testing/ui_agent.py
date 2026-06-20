#!/usr/bin/env python3
"""
ui_agent.py — LLM-driven visual flow testing agent (Anthropic Claude backend)

Two modes:

  record  — human navigates the app step by step, pressing Enter at each screen.
             Before the first capture you describe the flow in plain English:
             navigation gestures, key elements per screen, assertions to verify.
             The LLM labels each screen, notes design issues, and stores the
             advancement gesture (tap position or swipe direction) per step.
             Result: baseline images + a navigation map in baselines/index.json.

  check   — LLM drives the simulator/device through the recorded flow autonomously.
             On MATCH it applies the stored advancement gesture (no extra LLM call).
             On MISMATCH it falls back to asking the LLM where to gesture, retries
             up to --max-retries times, then marks the step FAIL.

Usage:
  # iOS Simulator (must be booted, Simulator.app open)
  python ui_agent.py record --ios "myapp-onboarding"
  python ui_agent.py check  --ios "myapp-onboarding"

  # Pass the flow description directly (skips the interactive prompt)
  python ui_agent.py record --ios --describe "5-screen onboarding..." "myapp-onboarding"

  # Android emulator / device
  python ui_agent.py record --android "myapp-onboarding"
  python ui_agent.py check  --android "myapp-onboarding"

  # Check every recorded flow for the current platform
  python ui_agent.py check-all --ios

Options:
  --describe TEXT      Flow description: navigation gestures, key elements, assertions
  --model MODEL        Vision model — any Anthropic Claude model, or an OpenAI
                        model (gpt-4o, gpt-4o-mini, gpt-4.1, ...) (default: claude-sonnet-4-6)
  --expect TEXT        Extra natural-language assertion re-used on every check
  --max-retries N      Gesture attempts per step before marking FAIL (default: 5)
"""

import argparse
import base64
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASELINES_DIR = Path(__file__).parent / "baselines"
BASELINES_INDEX = BASELINES_DIR / "index.json"
DEFAULT_MODEL = "claude-sonnet-4-6"


# ── prompt builders ───────────────────────────────────────────────────────────

def _capture_prompt(description: str) -> str:
    lines = ["You are a UI analyst capturing a step in a mobile app flow.\n"]
    if description:
        lines.append(f"Flow description:\n{description}\n")
    lines.append(
        'Look at this screenshot and reply in EXACTLY this format (no extra text):\n'
        'LABEL: <3-6 word description of this screen, e.g. "welcome splash screen">\n'
        'REVIEW: <one sentence design notes, or "No issues found">'
    )
    if description:
        lines.append(
            'ADVANCE: <how to reach the next screen per the flow description — '
            '"tap X% Y%", "swipe right", "swipe left", or "none" for the last screen>\n\n'
            'For tap coordinates:\n'
            '- X% 0=left edge, 100=right edge of the full image\n'
            '- Y% 0=top edge, 100=bottom edge of the full image\n'
            '- Tap the TEXT CENTER of the button label, not the bottom edge of the button shape\n'
            '- The bottom ~15% of the screen is the home indicator / nav bar area — never tap below 85%'
        )
    return "\n".join(lines)


def _match_prompt(description: str, label: str, assertion: str) -> str:
    parts = [
        "You are a visual regression tester. Compare these two screenshots.\n",
        "First image: the approved baseline — the correct, expected state.",
        "Second image: the current screen.\n",
    ]
    if description:
        parts.append(f"Flow description:\n{description}\n")
        parts.append(f"Current step: {label}\n")
    parts.append(
        "Judge by visual intent: same UI elements present, same layout structure, same overall state.\n"
        "Ignore minor rendering differences like sub-pixel antialiasing.\n"
    )
    if assertion:
        parts.append(assertion + "\n")
    parts.append("Reply with exactly one of:\nMATCH\nMISMATCH — <one sentence reason>")
    return "\n".join(parts)


def _tap_prompt(description: str) -> str:
    parts = ["You are controlling a mobile app to navigate to a target screen.\n"]
    if description:
        parts.append(f"Flow description:\n{description}\n")
    parts.append(
        "First image: the TARGET screen you need to reach.\n"
        "Second image: the CURRENT screen you are on now.\n\n"
        "What single gesture would move the current screen closer to the target?"
    )
    if description:
        parts.append("Use the gesture described in the flow description.")
    parts.append(
        "\nReply with ONLY one of these formats (nothing else):\n"
        "tap X% Y%\n"
        "swipe right\n"
        "swipe left\n\n"
        "For tap coordinates:\n"
        "- X% 0=left edge, 100=right edge of the full image\n"
        "- Y% 0=top edge, 100=bottom edge of the full image\n"
        "- Tap the TEXT CENTER of the button label, not the bottom edge of the button shape\n"
        "- The bottom ~15% of the screen is the home indicator / nav bar area — never tap below 85%"
    )
    return "\n".join(parts)


# ── helpers ───────────────────────────────────────────────────────────────────

def _key(target: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", target.lower()).strip("_")


def _load_index() -> dict:
    if BASELINES_INDEX.exists():
        return json.loads(BASELINES_INDEX.read_text())
    return {}


def _save_index(index: dict) -> None:
    BASELINES_DIR.mkdir(exist_ok=True)
    BASELINES_INDEX.write_text(json.dumps(index, indent=2))


def _take_screenshot(args: argparse.Namespace, target: str) -> str:
    if args.ios:
        from mobile_tools import screenshot_ios
        return screenshot_ios(target)
    if args.android:
        from mobile_tools import screenshot_android
        return screenshot_android(target)
    print("Error: specify --ios or --android")
    sys.exit(1)


def _resize_image(b64: str, max_width: int = 1080) -> str:
    import io
    from PIL import Image
    data = base64.b64decode(b64)
    img = Image.open(io.BytesIO(data))
    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def _vision_call(model: str, prompt: str, images: list[str]) -> str:
    # Anthropic and OpenAI model names never overlap, so the "gpt-" prefix is
    # enough to route without a separate --provider flag.
    if model.startswith("gpt-"):
        return _vision_call_openai(model, prompt, images)
    return _vision_call_anthropic(model, prompt, images)


def _vision_call_anthropic(model: str, prompt: str, images: list[str]) -> str:
    import anthropic
    client = anthropic.Anthropic()
    resized = [_resize_image(b64) for b64 in images]
    content = []
    for b64 in resized:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64},
        })
    content.append({"type": "text", "text": prompt})
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=256,
                messages=[{"role": "user", "content": content}],
            )
            return response.content[0].text.strip()
        except anthropic.APIConnectionError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def _vision_call_openai(model: str, prompt: str, images: list[str]) -> str:
    import openai
    client = openai.OpenAI()
    resized = [_resize_image(b64) for b64 in images]
    content = []
    for b64 in resized:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"},
        })
    content.append({"type": "text", "text": prompt})
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                max_tokens=256,
                messages=[{"role": "user", "content": content}],
            )
            return response.choices[0].message.content.strip()
        except openai.APIConnectionError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def _parse_advance(text: str) -> dict | None:
    """Parse an ADVANCE: line into a stored gesture dict, or None."""
    text = text.strip().lower()
    if not text or text == "none":
        return None
    if text.startswith("swipe right"):
        return {"gesture": "swipe_right"}
    if text.startswith("swipe left"):
        return {"gesture": "swipe_left"}
    m = re.search(r"tap\s+(\d+(?:\.\d+)?)%\s+(\d+(?:\.\d+)?)%", text)
    if m:
        x = float(m.group(1)) / 100
        y = min(float(m.group(2)) / 100, 0.85)
        return {"gesture": "tap", "x": x, "y": y}
    return None


def _do_tap(args: argparse.Namespace, x_pct: float, y_pct: float) -> None:
    if args.ios:
        from mobile_tools import tap_simulator_osx
        tap_simulator_osx(x_pct, y_pct)
    elif args.android:
        from mobile_tools import tap_android
        tap_android(x_pct, y_pct)


def _do_swipe(args: argparse.Namespace, direction: str) -> None:
    if args.ios:
        from mobile_tools import swipe_simulator_osx
        swipe_simulator_osx(direction)
    elif args.android:
        from mobile_tools import swipe_android
        swipe_android(direction)


def _apply_advance(args: argparse.Namespace, advance: dict) -> None:
    """Apply a stored advancement gesture after a MATCH."""
    gesture = advance.get("gesture")
    if gesture == "tap":
        x_pct, y_pct = advance["x"], advance["y"]
        print(f"       → stored tap ({x_pct * 100:.0f}%, {y_pct * 100:.0f}%)")
        _do_tap(args, x_pct, y_pct)
    elif gesture == "swipe_right":
        print("       → stored swipe right")
        _do_swipe(args, "right")
    elif gesture == "swipe_left":
        print("       → stored swipe left")
        _do_swipe(args, "left")


def _apply_gesture_reply(args: argparse.Namespace, reply: str) -> bool:
    """Parse and apply a dynamic gesture reply. Returns True if a gesture was executed."""
    m = re.search(r"tap\s+(\d+(?:\.\d+)?)%\s+(\d+(?:\.\d+)?)%", reply, re.IGNORECASE)
    if m:
        x_pct = float(m.group(1)) / 100
        y_pct = min(float(m.group(2)) / 100, 0.85)
        print(f"       → tapping ({m.group(1)}%, {m.group(2)}%)")
        _do_tap(args, x_pct, y_pct)
        return True
    if re.search(r"swipe\s+right", reply, re.IGNORECASE):
        print("       → swiping right")
        _do_swipe(args, "right")
        return True
    if re.search(r"swipe\s+left", reply, re.IGNORECASE):
        print("       → swiping left")
        _do_swipe(args, "left")
        return True
    print(f"       → could not parse gesture from: {reply!r}")
    return False


# ── record ────────────────────────────────────────────────────────────────────

def cmd_record(args: argparse.Namespace, target: str) -> None:
    if not args.ios and not args.android:
        print("Error: specify --ios or --android")
        sys.exit(1)

    key = _key(target)
    index = _load_index()
    if key in index and index[key].get("steps"):
        answer = input(
            f"Baseline '{target}' already has {len(index[key]['steps'])} step(s). Overwrite? [y/N] "
        ).strip().lower()
        if answer != "y":
            print("Aborted.")
            sys.exit(0)

    description = args.describe or ""
    if not description:
        print("\nDescribe this flow so the LLM knows the navigation gestures and what to verify.")
        print('Example: "5-screen onboarding. Tap Continue to advance. Last screen has ToS and Privacy links."')
        description = input("Flow description (or Enter to skip): ").strip()

    print(f"\nRecording flow: {target}")
    print("Navigate to each screen, then press Enter to capture. Type 'done' to finish.\n")

    steps = []
    step_num = 0
    capture_prompt = _capture_prompt(description)

    while True:
        raw = input(f"Step {step_num + 1} — press Enter to capture, or 'done' to finish: ").strip().lower()
        if raw == "done":
            break

        step_num += 1
        print("  Taking screenshot...")
        b64 = _take_screenshot(args, target)

        print("  Analysing...")
        analysis = _vision_call(args.model, capture_prompt, [b64])

        label, review, advance = f"step {step_num}", "", None
        for line in analysis.splitlines():
            if line.startswith("LABEL:"):
                label = line[len("LABEL:"):].strip()
            elif line.startswith("REVIEW:"):
                review = line[len("REVIEW:"):].strip()
            elif line.startswith("ADVANCE:"):
                advance = _parse_advance(line[len("ADVANCE:"):])

        BASELINES_DIR.mkdir(exist_ok=True)
        filename = f"{key}_step_{step_num:02d}.png"
        (BASELINES_DIR / filename).write_bytes(base64.b64decode(b64))

        step_entry: dict = {"file": filename, "label": label, "review": review}
        if advance:
            step_entry["advance"] = advance
        steps.append(step_entry)

        print(f"  ✓ {label}")
        if advance:
            g = advance.get("gesture", "")
            if g == "tap":
                print(f"  → advance: tap ({advance['x'] * 100:.0f}%, {advance['y'] * 100:.0f}%)")
            else:
                print(f"  → advance: {g.replace('_', ' ')}")
        if review and review.lower() != "no issues found":
            print(f"  ⚠ {review}")
        print()

    if not steps:
        print("No steps recorded. Baseline not saved.")
        sys.exit(0)

    index[key] = {
        "target": target,
        "platform": "ios" if args.ios else "android",
        "recorded_at": datetime.utcnow().isoformat(),
        "description": description,
        "assertion": args.expect or "",
        "steps": steps,
    }
    _save_index(index)
    print(f"Flow saved: {len(steps)} step(s) → baselines/{key}_step_*.png")


# ── check ─────────────────────────────────────────────────────────────────────

def _run_flow_check(
    args: argparse.Namespace, target: str, entry: dict
) -> tuple[bool, list[tuple[str, bool]]]:
    """
    Run the check loop for one flow. Returns (all_passed, [(label, passed), ...]).
    Does not call sys.exit — callers decide what to do with the result.
    """
    steps = entry.get("steps", [])
    description = args.describe or entry.get("description") or ""
    assertion_text = args.expect or entry.get("assertion") or ""
    assertion_line = f"Also verify: {assertion_text}" if assertion_text else ""

    print(f"Checking flow: {target} ({len(steps)} step(s))\n")
    results: list[tuple[str, bool]] = []

    for i, step in enumerate(steps):
        label = step.get("label", f"step {i + 1}")
        baseline_b64 = base64.b64encode(
            (BASELINES_DIR / step["file"]).read_bytes()
        ).decode()
        is_last = (i == len(steps) - 1)

        print(f"Step {i + 1}/{len(steps)}: {label}")

        passed = False
        for attempt in range(args.max_retries):
            current_b64 = _take_screenshot(args, target)

            verdict = _vision_call(
                args.model,
                _match_prompt(description, label, assertion_line),
                [baseline_b64, current_b64],
            )
            print(f"  [{attempt + 1}] {verdict}")

            if verdict.startswith("MATCH"):
                passed = True
                if not is_last:
                    stored = step.get("advance")
                    if stored:
                        _apply_advance(args, stored)
                        time.sleep(0.8)
                break

            if attempt < args.max_retries - 1:
                gesture_reply = _vision_call(
                    args.model,
                    _tap_prompt(description),
                    [baseline_b64, current_b64],
                )
                if not _apply_gesture_reply(args, gesture_reply):
                    break
                time.sleep(0.8)

        results.append((label, passed))
        print(f"  {'PASS' if passed else 'FAIL'}\n")

    return all(ok for _, ok in results), results


def _print_flow_summary(results: list[tuple[str, bool]]) -> None:
    all_pass = all(ok for _, ok in results)
    print("─" * 40)
    for label, ok in results:
        print(f"  {'✓' if ok else '✗'} {label}")
    print("─" * 40)
    print(f"Overall: {'PASS' if all_pass else 'FAIL'}")


def cmd_check(args: argparse.Namespace, target: str) -> None:
    key = _key(target)
    index = _load_index()
    if key not in index:
        print(f"No baseline for '{target}'. Run: python ui_agent.py record --ios '{target}'")
        sys.exit(1)

    entry = index[key]
    if not entry.get("steps"):
        print(f"Baseline '{target}' has no recorded steps. Re-record it with --ios or --android.")
        sys.exit(1)

    all_pass, results = _run_flow_check(args, target, entry)
    _print_flow_summary(results)
    sys.exit(0 if all_pass else 1)


def cmd_check_all(args: argparse.Namespace) -> None:
    import copy
    index = _load_index()
    if not index:
        print("No flows recorded yet.")
        sys.exit(0)

    flows = {
        key: entry for key, entry in index.items()
        if not (args.ios or args.android)
        or (args.ios and entry.get("platform") == "ios")
        or (args.android and entry.get("platform") == "android")
    }

    if not flows:
        print("No matching flows found for the specified platform.")
        sys.exit(0)

    print(f"Running {len(flows)} flow(s)...\n")

    all_results: list[tuple[str, bool, list[tuple[str, bool]]]] = []

    for key, entry in flows.items():
        target = entry["target"]
        platform = entry.get("platform", "")

        if not entry.get("steps"):
            print(f"Skipping '{target}': no recorded steps.")
            continue

        flow_args = copy.copy(args)
        flow_args.ios = (platform == "ios")
        flow_args.android = (platform == "android")

        print(f"{'═' * 50}")
        print(f"  {target}  [{platform}]")
        print(f"{'═' * 50}")

        passed, step_results = _run_flow_check(flow_args, target, entry)
        all_results.append((target, passed, step_results))
        print()

    if not all_results:
        print("No flows with recorded steps found.")
        sys.exit(0)

    print(f"\n{'═' * 50}")
    print("  SUMMARY")
    print(f"{'═' * 50}")
    overall = True
    for target, passed, step_results in all_results:
        print(f"  {'✓' if passed else '✗'}  {target}")
        if not passed:
            for label, ok in step_results:
                if not ok:
                    print(f"       ✗ {label}")
        overall = overall and passed
    print(f"{'═' * 50}")
    print(f"  Overall: {'PASS' if overall else 'FAIL'}")
    print(f"{'═' * 50}")
    sys.exit(0 if overall else 1)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM-driven visual flow testing — record baselines, check for regressions."
    )
    subs = parser.add_subparsers(dest="mode", required=True)

    def _add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--ios", action="store_true", help="Use iOS Simulator")
        p.add_argument("--android", action="store_true", help="Use Android emulator/device")
        p.add_argument("--model", default=DEFAULT_MODEL, help="Vision LLM model")
        p.add_argument("--expect", default="", help="Extra natural-language assertion")
        p.add_argument("--describe", default="", metavar="TEXT",
                       help="Flow description: navigation gestures, key elements, assertions")
        p.add_argument("--max-retries", type=int, default=5,
                       help="Gesture attempts per step before FAIL (default: 5)")

    rec = subs.add_parser("record", help="Record a baseline flow")
    rec.add_argument("target", help="Flow name")
    _add_common(rec)

    chk = subs.add_parser("check", help="Check one flow against its baseline")
    chk.add_argument("target", help="Flow name")
    _add_common(chk)

    chk_all = subs.add_parser("check-all", help="Check every recorded flow")
    _add_common(chk_all)

    args = parser.parse_args()

    if args.mode == "record":
        cmd_record(args, args.target)
    elif args.mode == "check":
        cmd_check(args, args.target)
    else:
        cmd_check_all(args)


if __name__ == "__main__":
    main()
