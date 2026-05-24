"""
AVAListener — Phase 4 Recovery Tests
=====================================
Exercises RecoveryPolicy, FaultClassifier, RestartManager, and RecoveryCoordinator
without touching matcher, phrase registry, or ASR decoding behavior.

Run:
    python tests/runtime/test_recovery.py
"""

from __future__ import annotations

import sys
import os
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import after path fix so runtime modules are importable
from runtime.hardening.recovery_policy import RecoveryPolicy
from runtime.hardening.fault_classifier import FaultType, classify, classify_watchdog_trigger
from runtime.hardening.restart_manager import RestartManager
from runtime.hardening.recovery_coordinator import RecoveryCoordinator, RecoveryAction
from runtime.telemetry.events import start_telemetry_worker, stop_telemetry_worker

# ── Helpers ────────────────────────────────────────────────────────────────────

_passed = 0
_failed = 0

def _assert(condition: bool, name: str, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        print(f"  PASS  {name}")
        _passed += 1
    else:
        print(f"  FAIL  {name}{': ' + detail if detail else ''}")
        _failed += 1


# ── Scenario 1: Single transient ASR failure → recover ─────────────────────────

def test_single_transient_failure():
    print("\nScenario 1: Single transient ASR failure")
    mgr = RestartManager()
    coord = RecoveryCoordinator(mgr)

    action = coord.observe_fault("asr", TimeoutError("stream timeout"), is_timeout=True)
    _assert(action == RecoveryAction.RECOVER, "Single transient → RECOVER", action)


# ── Scenario 2: Repeated transient failures → restart ──────────────────────────

def test_repeated_transient_failures():
    print("\nScenario 2: Repeated transient failures → restart")
    mgr = RestartManager()
    # Use a short policy so we can trigger escalation quickly
    mgr._records["asr"].policy = RecoveryPolicy(max_retries=3, backoff_initial_ms=10, backoff_max_ms=80, escalation_threshold=2)

    restart_called = []
    mgr.register_restart_handler("asr", lambda: restart_called.append(1))

    coord = RecoveryCoordinator(mgr)

    # First RECOVERABLE fault → restart (no escalation yet)
    action1 = coord.observe_fault("asr", RuntimeError("stream error"))
    _assert(action1 == RecoveryAction.RESTART, "1st recoverable fault → RESTART", action1)

    action2 = coord.observe_fault("asr", RuntimeError("stream error"))
    _assert(action2 == RecoveryAction.RESTART, "2nd recoverable fault → RESTART", action2)

    # After max_retries exhausted, next call should escalate
    action3 = coord.observe_fault("asr", RuntimeError("stream error"))
    _assert(
        action3 in (RecoveryAction.RESTART, RecoveryAction.ESCALATE),
        "3rd+ recoverable fault → RESTART or ESCALATE", action3,
    )
    _assert(len(restart_called) >= 1, "Restart handler was invoked at least once")


# ── Scenario 3: Persistent failures > threshold → escalate ─────────────────────

def test_persistent_failures_escalate():
    print("\nScenario 3: Persistent failures beyond threshold → escalate")
    policy = RecoveryPolicy(max_retries=2, backoff_initial_ms=10, backoff_max_ms=20, escalation_threshold=1)
    mgr = RestartManager()
    mgr._records["asr"].policy = policy

    coord = RecoveryCoordinator(mgr)

    # Exhaust policy
    coord.observe_fault("asr", RuntimeError("err"))
    coord.observe_fault("asr", RuntimeError("err"))
    action = coord.observe_fault("asr", RuntimeError("err"))

    _assert(action == RecoveryAction.ESCALATE, "Policy exhausted → ESCALATE", action)


# ── Scenario 4: Critical failure → shutdown ────────────────────────────────────

def test_critical_failure_shutdown():
    print("\nScenario 4: Critical failure → shutdown")
    mgr = RestartManager()
    shutdown_called = []
    coord = RecoveryCoordinator(mgr, shutdown_callback=lambda: shutdown_called.append(1))

    action = coord.observe_fault("asr", FileNotFoundError("model missing"))

    _assert(action == RecoveryAction.SHUTDOWN, "Critical failure → SHUTDOWN", action)
    _assert(len(shutdown_called) == 1, "Shutdown callback invoked exactly once")


# ── Scenario 5: Recovery backoff timing ────────────────────────────────────────

def test_recovery_backoff_timing():
    print("\nScenario 5: Recovery backoff timing — exponential sequence")
    policy = RecoveryPolicy(
        max_retries=10,
        backoff_initial_ms=100.0,
        backoff_max_ms=10000.0,
        escalation_threshold=8,
    )

    expected = [100.0, 200.0, 400.0, 800.0]
    for i, expected_ms in enumerate(expected):
        policy.record_failure()
        delay = policy.next_backoff()
        _assert(
            abs(delay - expected_ms) < 1.0,
            f"Retry {i+1}: delay={delay:.0f}ms expected={expected_ms:.0f}ms",
            f"got {delay}",
        )


# ── Fault classifier unit tests ────────────────────────────────────────────────

def test_fault_classifier():
    print("\nFault Classifier unit tests")
    _assert(classify(TimeoutError()) == FaultType.TRANSIENT,     "TimeoutError → TRANSIENT")
    _assert(classify(FileNotFoundError()) == FaultType.CRITICAL, "FileNotFoundError → CRITICAL")
    _assert(classify(RuntimeError()) == FaultType.RECOVERABLE,   "RuntimeError → RECOVERABLE")
    _assert(classify(None, is_timeout=True) == FaultType.TRANSIENT,        "is_timeout flag → TRANSIENT")
    _assert(classify(None, is_queue_overflow=True) == FaultType.TRANSIENT,  "is_queue_overflow flag → TRANSIENT")
    _assert(classify_watchdog_trigger("worker_hang") == FaultType.TRANSIENT,    "worker_hang → TRANSIENT")
    _assert(classify_watchdog_trigger("worker_dead") == FaultType.RECOVERABLE,  "worker_dead → RECOVERABLE")
    _assert(classify_watchdog_trigger("memory_exhausted") == FaultType.CRITICAL, "memory_exhausted → CRITICAL")


# ── Main runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    start_telemetry_worker()
    try:
        print("=" * 60)
        print("  AVAListener — Phase 4 Recovery Tests")
        print("=" * 60)

        test_fault_classifier()
        test_single_transient_failure()
        test_repeated_transient_failures()
        test_persistent_failures_escalate()
        test_critical_failure_shutdown()
        test_recovery_backoff_timing()

        print()
        print("=" * 60)
        print(f"  Results: {_passed}/{_passed + _failed} passed  |  {_failed} failed")
        print("=" * 60)
    finally:
        stop_telemetry_worker()

    sys.exit(0 if _failed == 0 else 1)
