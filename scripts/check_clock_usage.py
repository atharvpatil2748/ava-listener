"""
AVAListener — Clock Usage Enforcement (Phase 5.2)
==================================================
Scans runtime/ for forbidden direct time calls that bypass RuntimeClock.

Usage:
    python scripts/check_clock_usage.py

Returns exit code 0 if clean, 1 if violations found.
"""
from __future__ import annotations
import os
import sys

# Patterns that bypass RuntimeClock and must not appear in runtime/
FORBIDDEN_PATTERNS = [
    "time.time(",
    "time.monotonic(",
    "datetime.now(",
    "datetime.utcnow(",
]

# Files and directories explicitly exempted (legacy code that owns time)
EXEMPTED_PATHS = {
    # utils/logger.py uses time.strftime for log formatting only
    os.path.join("utils", "logger.py"),
    # telemetry events uses time.time_ns for nanosecond precision
    os.path.join("runtime", "telemetry", "events.py"),
    os.path.join("runtime", "telemetry", "schema.py"),
    # timing/clock.py IS the RuntimeClock — it wraps time.*
    os.path.join("runtime", "timing", "clock.py"),
    # formatters uses time.strftime for human-readable log output only
    os.path.join("runtime", "logging", "formatters.py"),
    # replay_capture uses time.time_ns for capture timestamps
    os.path.join("runtime", "telemetry", "replay_capture.py"),
    # crash_snapshot uses time.time_ns for snapshot timestamping
    os.path.join("runtime", "debug", "crash_snapshot.py"),
    # latency.py wraps time.time_ns
    os.path.join("runtime", "timing", "latency.py"),
}

SCAN_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ava-listener", "runtime")


def is_exempted(filepath: str) -> bool:
    norm = os.path.normpath(filepath)
    for exempt in EXEMPTED_PATHS:
        if norm.endswith(os.path.normpath(exempt)):
            return True
    return False


def scan() -> list[tuple[str, int, str]]:
    violations: list[tuple[str, int, str]] = []
    for root, dirs, files in os.walk(SCAN_ROOT):
        # Skip __pycache__
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(root, fname)
            if is_exempted(fpath):
                continue
            try:
                with open(fpath, encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, 1):
                        for pattern in FORBIDDEN_PATTERNS:
                            if pattern in line:
                                violations.append((fpath, lineno, line.rstrip()))
            except OSError:
                continue
    return violations


if __name__ == "__main__":
    print("=" * 60)
    print("  Clock Usage Enforcement Check")
    print(f"  Scanning: {SCAN_ROOT}")
    print("=" * 60)

    violations = scan()

    if not violations:
        print("\n  PASS  No forbidden clock usage found in runtime/")
        print("=" * 60)
        sys.exit(0)
    else:
        print(f"\n  FAIL  {len(violations)} violation(s) found:\n")
        for fpath, lineno, line in violations:
            rel = os.path.relpath(fpath, SCAN_ROOT)
            print(f"  {rel}:{lineno}")
            print(f"    {line.strip()}")
        print()
        print("=" * 60)
        sys.exit(1)
