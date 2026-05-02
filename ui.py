"""Single-line activity indicator for the agent loop."""

from __future__ import annotations

import itertools
import sys
import threading
import time

_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_ANSI = sys.stdout.isatty()


class Spinner:
    """
    Animates a braille spinner on a single terminal line.

    start(msg)  — begin spinning with a status message
    update(msg) — swap the message while the spinner keeps running
    stop()      — clear the spinner line
    println(s)  — commit a permanent line without breaking the animation
    """

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._msg = "Thinking…"
        self._msg_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._start_time: float = 0.0

    def start(self, msg: str = "Thinking…") -> None:
        if not _ANSI:
            return
        self._stop.clear()
        self._start_time = time.monotonic()
        with self._msg_lock:
            self._msg = msg
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def update(self, msg: str) -> None:
        with self._msg_lock:
            self._msg = msg

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.3)
            self._thread = None
        if _ANSI:
            with self._write_lock:
                sys.stdout.write("\r\033[K")
                sys.stdout.flush()

    def println(self, text: str) -> None:
        """Print a permanent line. Safe to call while the spinner is running."""
        with self._write_lock:
            sys.stdout.write(f"\r\033[K{text}\n" if _ANSI else f"{text}\n")
            sys.stdout.flush()

    @staticmethod
    def _fmt_elapsed(seconds: float) -> str:
        s = int(seconds)
        return f"{s // 60}m {s % 60}s" if s >= 60 else f"{s}s"

    def _spin(self) -> None:
        for frame in itertools.cycle(_FRAMES):
            if self._stop.is_set():
                break
            with self._msg_lock:
                msg = self._msg
            elapsed = self._fmt_elapsed(time.monotonic() - self._start_time)
            with self._write_lock:
                sys.stdout.write(f"\r{frame} {msg} ({elapsed})\033[K")
                sys.stdout.flush()
            time.sleep(0.08)
