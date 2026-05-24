#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AVAListener — Startup Verification Script (Phase 0)
====================================================
Spawns main.py as a child process, waits for it to reach the READY state,
captures its stdout/stderr, and verifies all required startup signals.

Designed for:
  - Phase 0 baseline validation
  - CI/CD regression gates (any phase)
  - Post-deployment sanity checks

Usage:
    python scripts/verify_startup.py [--timeout 15] [--python PATH]

Options:
    --timeout SECONDS   Seconds to wait for startup signals (default: 15)
    --python PATH       Python executable to use (default: auto-detect venv)
    --no-kill           Leave the process running after verification

Exit codes:
    0  All startup checks passed
    1  One or more startup checks failed or process crashed
    2  Timeout exceeded before all signals received
"""
from __future__ import annotations

import subprocess
import time
import sys
import os
import argparse

# Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


# ── Locate python executable ──────────────────────────────────────────────────

def _find_python() -> str:
    """
    Resolve the Python executable in order:
      1. AVALISTEN_PYTHON env var
      2. venv relative to this script (../../venv/Scripts/python on Windows)
      3. sys.executable (current interpreter)
    """
    env_override = os.environ.get("AVALISTEN_PYTHON")
    if env_override and os.path.isfile(env_override):
        return env_override

    # Detect: scripts/ is inside ava-listener/, venv is one level up
    script_dir = os.path.dirname(os.path.abspath(__file__))          # ava-listener/scripts/
    project_root = os.path.dirname(script_dir)                         # ava-listener/
    repo_root = os.path.dirname(project_root)                          # AVA-Listener/

    candidates = [
        # venv at repo root
        os.path.join(repo_root, "venv", "Scripts", "python.exe"),     # Windows
        os.path.join(repo_root, "venv", "bin", "python"),             # Unix
        os.path.join(repo_root, "venv", "bin", "python3"),            # Unix alt
        # venv inside project dir
        os.path.join(project_root, "venv", "Scripts", "python.exe"),
        os.path.join(project_root, "venv", "bin", "python"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c

    return sys.executable  # fallback: current interpreter


# ── Startup checks ─────────────────────────────────────────────────────────────

_STARTUP_SIGNALS = {
    # (description, search_in, substring_to_find)
    "Sherpa model loaded":     ("stderr", "Model loaded"),
    "Mic opened":              ("stderr", "Mic open"),
    "Engine started":          ("stderr", "AVAListener engine started"),
    "status=ready emitted":    ("stdout", '"ready"'),
    "Heartbeat emitted":       ("stdout", '"heartbeat"'),
}


def verify_startup(
    python_exe: str,
    timeout_s: float = 15.0,
    kill_after: bool = True,
) -> int:
    """
    Spawn main.py, wait up to timeout_s for all startup signals, report results.
    Returns 0 on full pass, 1 on failure, 2 on timeout.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)  # ava-listener/
    main_py = os.path.join(project_dir, "main.py")

    if not os.path.isfile(main_py):
        print(f"ERROR: main.py not found at {main_py}", file=sys.stderr)
        return 1

    print("=" * 60)
    print("  AVAListener — Startup Verification (Phase 0)")
    print("=" * 60)
    print(f"  Python   : {python_exe}")
    print(f"  main.py  : {main_py}")
    print(f"  Timeout  : {timeout_s}s")
    print("=" * 60)
    print(f"  Spawning main.py...\n")

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)

    proc = subprocess.Popen(
        [python_exe, "-u", main_py, "--mode", "direct", "--debug"],
        cwd=project_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    print(f"  PID: {proc.pid}  — waiting up to {timeout_s}s for startup signals...")

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    # Non-blocking read loop — accumulate output until timeout
    import threading

    def _read_stream(stream, buf: list[str]) -> None:
        try:
            for line in stream:
                buf.append(line.rstrip())
        except Exception:
            pass

    t_stdout = threading.Thread(target=_read_stream, args=(proc.stdout, stdout_lines), daemon=True)
    t_stderr = threading.Thread(target=_read_stream, args=(proc.stderr, stderr_lines), daemon=True)
    t_stdout.start()
    t_stderr.start()

    deadline = time.monotonic() + timeout_s
    all_signals_found = False

    while time.monotonic() < deadline:
        stdout_blob = "\n".join(stdout_lines)
        stderr_blob = "\n".join(stderr_lines)

        found_count = sum(
            1 for desc, (src, needle) in _STARTUP_SIGNALS.items()
            if needle in (stdout_blob if src == "stdout" else stderr_blob)
        )
        if found_count == len(_STARTUP_SIGNALS):
            all_signals_found = True
            break

        if proc.poll() is not None:
            # Process exited early
            break

        time.sleep(0.25)

    elapsed = time.monotonic() - (deadline - timeout_s)

    # Terminate
    if kill_after:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    t_stdout.join(timeout=2)
    t_stderr.join(timeout=2)

    stdout_blob = "\n".join(stdout_lines)
    stderr_blob = "\n".join(stderr_lines)

    # ── Print captured output ──────────────────────────────────────────────
    print(f"\n  [STDOUT — {len(stdout_lines)} lines]")
    for line in stdout_lines:
        print(f"    {line}")

    last_stderr = stderr_lines[-30:] if len(stderr_lines) > 30 else stderr_lines
    print(f"\n  [STDERR — last {len(last_stderr)} of {len(stderr_lines)} lines]")
    for line in last_stderr:
        print(f"    {line}")

    # ── Check results ──────────────────────────────────────────────────────
    print(f"\n  [STARTUP CHECKS]  (elapsed: {elapsed:.1f}s)")
    all_pass = True
    for desc, (src, needle) in _STARTUP_SIGNALS.items():
        blob = stdout_blob if src == "stdout" else stderr_blob
        found = needle in blob
        status = "PASS" if found else "FAIL"
        if not found:
            all_pass = False
        print(f"  {status}  {desc}")

    # ── Crash detection ────────────────────────────────────────────────────
    exit_code = proc.poll()
    # On Windows, proc.terminate() results in exit code 1 (not -15 like POSIX SIGTERM).
    # Treat code 1 as expected when we killed the process ourselves (kill_after=True).
    _expected_exit = {None, 0, -15, -9}  # POSIX: SIGTERM=-15, SIGKILL=-9
    if kill_after:
        _expected_exit.add(1)   # Windows terminate() → code 1
    if exit_code not in _expected_exit:
        print(f"\n  WARN  Process exited with code {exit_code} — possible crash")
        all_pass = False

    print()
    if not all_signals_found and not all_pass:
        print("  BASELINE STATUS: STARTUP SIGNALS MISSING OR CRASHED")
        return 1
    elif not all_signals_found:
        print(f"  BASELINE STATUS: TIMEOUT ({timeout_s}s) — signals incomplete")
        return 2
    elif all_pass:
        print("  BASELINE STATUS: RESTORED AND VERIFIED [OK]")
        return 0
    else:
        print("  BASELINE STATUS: STARTUP ISSUES REMAIN")
        return 1


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify AVAListener startup signals (Phase 0 baseline check)"
    )
    parser.add_argument(
        "--timeout", type=float, default=15.0,
        help="Seconds to wait for startup (default: 15)"
    )
    parser.add_argument(
        "--python", type=str, default=None,
        help="Python executable path (default: auto-detect from venv)"
    )
    parser.add_argument(
        "--no-kill", action="store_true",
        help="Leave the spawned process running after verification"
    )
    args = parser.parse_args()

    python_exe = args.python or _find_python()
    exit_code = verify_startup(
        python_exe=python_exe,
        timeout_s=args.timeout,
        kill_after=not args.no_kill,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
