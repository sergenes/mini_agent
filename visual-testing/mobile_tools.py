"""
Mobile screenshot and gesture tools.

iOS Simulator: requires Xcode + iOS Simulator running (xcrun simctl)
               window bounds: osascript + Accessibility permission for Terminal
               tap/swipe: JXA + CoreGraphics CGEventPost — no Accessibility needed
Android:       requires Android SDK + emulator or device connected via adb

Note: physical iOS device screenshots are not supported. Apple removed the
screenshotr service on iOS 17+. Use the iOS Simulator instead.
"""

import base64
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


# ── iOS Simulator ─────────────────────────────────────────────────────────────

def screenshot_ios(bundle_id: str = "") -> str:
    """Screenshot the booted iOS Simulator. bundle_id is ignored — simctl captures the booted device."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp = Path(f.name)
    try:
        subprocess.run(
            ["xcrun", "simctl", "io", "booted", "screenshot", str(tmp)],
            check=True, capture_output=True,
        )
        return base64.b64encode(tmp.read_bytes()).decode()
    finally:
        tmp.unlink(missing_ok=True)


def get_simulator_window_bounds() -> tuple[int, int, int, int]:
    """
    Return (x, y, w, h) of the Simulator window in macOS screen points.
    Requires Terminal to have Accessibility permission:
      System Settings → Privacy & Security → Accessibility → Terminal ✓
    """
    script = """
    tell application "System Events"
        set proc to first process whose name is "Simulator"
        set win to first window of proc
        set {wx, wy} to position of win
        set {ww, wh} to size of win
        return (wx as string) & "," & (wy as string) & "," & (ww as string) & "," & (wh as string)
    end tell
    """
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "Could not find Simulator window. Make sure Simulator.app is open "
            "and Terminal has Accessibility permission in System Settings → "
            "Privacy & Security → Accessibility."
        )
    wx, wy, ww, wh = [int(v.strip()) for v in result.stdout.strip().split(",")]
    return wx, wy, ww, wh


def tap_simulator_osx(x_pct: float, y_pct: float) -> None:
    """
    Tap at a position given as fractions of the simulator screen (0.0–1.0).
    Activate and tap in one JXA script — two separate subprocess calls let
    Terminal steal focus between them, causing the tap to land on Terminal.
    """
    wx, wy, ww, wh = get_simulator_window_bounds()
    title_bar = 28
    content_h = wh - title_bar
    screen_x = int(wx + x_pct * ww)
    screen_y = int(wy + title_bar + y_pct * content_h)
    print(f"       [tap] window=({wx},{wy},{ww},{wh}) → screen=({screen_x},{screen_y})")
    script = f"""
ObjC.import('CoreGraphics');
Application('Simulator').activate();
$.NSThread.sleepForTimeInterval(0.2);
var pt = $.CGPointMake({screen_x}, {screen_y});
var dn = $.CGEventCreateMouseEvent(null, $.kCGEventLeftMouseDown, pt, $.kCGMouseButtonLeft);
var up = $.CGEventCreateMouseEvent(null, $.kCGEventLeftMouseUp,   pt, $.kCGMouseButtonLeft);
$.CGEventPost($.kCGHIDEventTap, dn);
$.CGEventPost($.kCGHIDEventTap, up);
"""
    result = subprocess.run(["osascript", "-l", "JavaScript", "-e", script], capture_output=True)
    if result.returncode != 0:
        err = result.stderr.decode().strip()
        raise RuntimeError(f"CGEventPost tap failed at ({screen_x}, {screen_y}): {err}")


def swipe_simulator_osx(direction: str) -> None:
    """
    Swipe on the iOS Simulator screen.
    direction: "right" (finger moves right) or "left" (finger moves left).
    Ten drag steps give iOS enough motion events to recognise it as a swipe gesture.
    """
    wx, wy, ww, wh = get_simulator_window_bounds()
    title_bar = 28
    content_h = wh - title_bar
    cy = int(wy + title_bar + content_h * 0.5)
    if direction == "right":
        x_start = int(wx + ww * 0.2)
        x_end   = int(wx + ww * 0.8)
    else:
        x_start = int(wx + ww * 0.8)
        x_end   = int(wx + ww * 0.2)
    print(f"       [swipe {direction}] window=({wx},{wy},{ww},{wh}) x: {x_start}→{x_end} y={cy}")
    script = f"""
ObjC.import('CoreGraphics');
Application('Simulator').activate();
$.NSThread.sleepForTimeInterval(0.2);
var xStart = {x_start}, xEnd = {x_end}, y = {cy}, steps = 10;
var pt0 = $.CGPointMake(xStart, y);
var dn  = $.CGEventCreateMouseEvent(null, $.kCGEventLeftMouseDown, pt0, $.kCGMouseButtonLeft);
$.CGEventPost($.kCGHIDEventTap, dn);
for (var i = 1; i <= steps; i++) {{
    var x   = xStart + (xEnd - xStart) * i / steps;
    var pt  = $.CGPointMake(x, y);
    var drg = $.CGEventCreateMouseEvent(null, $.kCGEventLeftMouseDragged, pt, $.kCGMouseButtonLeft);
    $.CGEventPost($.kCGHIDEventTap, drg);
}}
var ptEnd = $.CGPointMake(xEnd, y);
var up    = $.CGEventCreateMouseEvent(null, $.kCGEventLeftMouseUp, ptEnd, $.kCGMouseButtonLeft);
$.CGEventPost($.kCGHIDEventTap, up);
"""
    result = subprocess.run(["osascript", "-l", "JavaScript", "-e", script], capture_output=True)
    if result.returncode != 0:
        err = result.stderr.decode().strip()
        raise RuntimeError(f"CGEventPost swipe {direction} failed: {err}")


# ── Android ───────────────────────────────────────────────────────────────────

def _adb_path() -> str:
    """
    Resolve the adb binary without relying on the shell's PATH — IDE-integrated
    terminals and some shells don't inherit the same PATH as Terminal.app, so
    plain "adb" can resolve in an interactive shell but fail from a subprocess.
    Checks PATH first, then ANDROID_HOME / ANDROID_SDK_ROOT, then the default
    macOS SDK install location.
    """
    found = shutil.which("adb")
    if found:
        return found
    for env_var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        sdk_root = os.environ.get(env_var)
        if sdk_root:
            candidate = Path(sdk_root) / "platform-tools" / "adb"
            if candidate.exists():
                return str(candidate)
    default = Path.home() / "Library" / "Android" / "sdk" / "platform-tools" / "adb"
    if default.exists():
        return str(default)
    raise RuntimeError(
        "Could not find 'adb'. Install Android platform-tools and either add it to "
        "PATH, or set ANDROID_HOME/ANDROID_SDK_ROOT to your SDK root "
        "(default on macOS: ~/Library/Android/sdk)."
    )


def _get_android_screen_size() -> tuple[int, int]:
    """
    Return (width, height) in physical pixels from the connected device.
    Uses 'adb shell wm size'; falls back to 1080×2400 if adb is unavailable.
    If an override size is set it takes precedence (last match in the output).
    """
    try:
        result = subprocess.run(
            [_adb_path(), "shell", "wm", "size"],
            capture_output=True, text=True, check=True,
        )
        matches = re.findall(r"(\d+)x(\d+)", result.stdout)
        if matches:
            w, h = int(matches[-1][0]), int(matches[-1][1])
            return w, h
    except Exception:
        pass
    return 1080, 2400


def screenshot_android(package: str = "") -> str:
    """Screenshot the connected Android device or running emulator."""
    result = subprocess.run(
        [_adb_path(), "exec-out", "screencap", "-p"],
        capture_output=True, check=True,
    )
    return base64.b64encode(result.stdout).decode()


def tap_android(x_pct: float, y_pct: float) -> None:
    """Tap at a position given as fractions of the Android screen (0.0–1.0)."""
    w, h = _get_android_screen_size()
    x, y = int(x_pct * w), int(y_pct * h)
    print(f"       [tap] screen=({w},{h}) → tap=({x},{y})")
    subprocess.run(
        [_adb_path(), "shell", "input", "tap", str(x), str(y)],
        check=True, capture_output=True,
    )


def swipe_android(direction: str) -> None:
    """Swipe on the Android device/emulator via adb. direction: 'right' or 'left'."""
    w, h = _get_android_screen_size()
    cy = h // 2
    if direction == "right":
        x1, x2 = int(w * 0.2), int(w * 0.8)
    else:
        x1, x2 = int(w * 0.8), int(w * 0.2)
    print(f"       [swipe {direction}] screen=({w},{h}) x: {x1}→{x2} y={cy}")
    subprocess.run(
        [_adb_path(), "shell", "input", "swipe", str(x1), str(cy), str(x2), str(cy), "300"],
        check=True, capture_output=True,
    )
