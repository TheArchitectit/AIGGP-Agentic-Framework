# fw-* audit infrastructure: resource & economic governance.
"""Budgets and runaway detection for long-running evaluation flows.

An evaluation that eventually succeeds after consuming unbounded time,
output, or retries is not reliable. This module provides the primitive
governance building blocks used across the framework:

  - WallClockBudget: a hard wall-clock budget with deadline checks; on
    exhaustion it raises BudgetExceeded — a CONTROLLED, observable,
    recoverable outcome, never a hang.
  - run_capped: a subprocess runner with BOTH a wall-clock timeout and an
    output-size cap; a process that spews output forever or never exits is
    stopped and reported, not absorbed.
  - RunawayDetector: recognizes degenerate loop behavior — repeated
    identical failures, no-progress repetition — so callers can change
    strategy or stop with an accurate state instead of retrying forever.
  - backoff: adaptive exponential backoff with a hard cap (retry storms
    are a governance failure, not a strategy).

Nothing here kills processes mid-write: run_capped preserves whatever the
child wrote before the cap, and the caller decides what recovery means.
"""
from __future__ import annotations

import subprocess
import time


class BudgetExceeded(RuntimeError):
    """A resource budget was exhausted (controlled stop, not a crash)."""

    def __init__(self, budget: str, detail: str = ""):
        super().__init__(f"budget exceeded: {budget}"
                         + (f" ({detail})" if detail else ""))
        self.budget = budget


class WallClockBudget:
    """A wall-clock allowance checked explicitly at safe points.

    Deliberately cooperative (no signals, no threads): the owner calls
    check() between work units. This keeps budget stops deterministic and
    recoverable — work units complete atomically, state stays consistent.
    """

    def __init__(self, seconds: float, clock=time.monotonic):
        if seconds <= 0:
            raise ValueError("budget must be positive")
        self._seconds = seconds
        self._clock = clock
        self._start = clock()

    def elapsed(self) -> float:
        return self._clock() - self._start

    def remaining(self) -> float:
        return max(0.0, self._seconds - self.elapsed())

    def check(self, what: str = "") -> None:
        if self.elapsed() > self._seconds:
            raise BudgetExceeded(
                f"wall-clock {self._seconds}s",
                f"after {self.elapsed():.1f}s"
                + (f" during {what}" if what else ""))


def run_capped(cmd: list, timeout: float = 60.0, max_output: int = 1_000_000,
               cwd: str = None) -> dict:
    """Run a subprocess under time AND output budgets.

    Returns {exit, stdout, stderr, truncated, duration_sec, stopped}.
    Output beyond max_output is truncated (the head is kept — errors
    usually explain themselves early). A timeout produces exit=None with
    stopped="timeout": controlled, observable, recoverable.
    """
    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, cwd=cwd)
        out, err, exit_ = r.stdout or b"", r.stderr or b"", r.returncode
        stopped = None
    except subprocess.TimeoutExpired as e:
        out = e.stdout or b""
        err = (e.stderr or b"") + b"\n[run_capped: timed out]"
        exit_, stopped = None, "timeout"
    duration = round(time.monotonic() - t0, 3)

    def cap(b: bytes):
        if len(b) > max_output:
            return b[:max_output] + b"\n[run_capped: output truncated]", True
        return b, False

    out, cut1 = cap(out)
    err, cut2 = cap(err)
    return {
        "exit": exit_,
        "stdout": out.decode("utf-8", errors="replace"),
        "stderr": err.decode("utf-8", errors="replace"),
        "truncated": cut1 or cut2,
        "duration_sec": duration,
        "stopped": stopped,
    }


class RunawayDetector:
    """Detect degenerate repetition in retry/agent loops.

    Feed it an event signature per iteration (e.g. the exception class +
    failing assertion id). It answers:
      repeated_failure(min_repeat)  — same signature N times in a row
      no_progress(variety_needed)   — too few distinct signatures recently

    A loop that keeps failing identically is not making progress; the
    caller should change strategy, checkpoint, reduce scope, or stop with
    an accurate state — not keep burning budget.
    """

    def __init__(self, window: int = 20):
        if window < 2:
            raise ValueError("window must be at least 2")
        self._window = window
        self._history: list = []

    def record(self, signature: str) -> None:
        self._history.append(signature)
        if len(self._history) > self._window:
            self._history.pop(0)

    def repeated_failure(self, min_repeat: int = 3) -> bool:
        if len(self._history) < min_repeat:
            return False
        tail = self._history[-min_repeat:]
        return len(set(tail)) == 1

    def no_progress(self, variety_needed: int = 2) -> bool:
        """True when the recent window shows fewer distinct signatures than
        needed — the loop is stuck in a groove."""
        if len(self._history) < self._window:
            return False
        return len(set(self._history)) < variety_needed

    def reset(self) -> None:
        self._history.clear()


def backoff(attempt: int, base: float = 0.1, cap: float = 30.0) -> float:
    """Exponential backoff with a hard cap. Attempt numbering starts at 0.
    The cap is the governance point: after ~8 attempts the wait stops
    growing, and callers should couple this with RunawayDetector so the
    loop terminates rather than cycling at cap forever."""
    if attempt < 0:
        raise ValueError("attempt must be >= 0")
    return min(cap, base * (2 ** attempt))
