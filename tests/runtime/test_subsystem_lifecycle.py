"""
AVAListener — Subsystem Lifecycle Regression Tests
====================================================
Verifies every subsystem follows the mandatory transition sequence:
  OFFLINE -> INITIALIZING -> READY -> ACTIVE

And that recovery/shutdown paths work correctly.

Run:
    python tests/runtime/test_subsystem_lifecycle.py
"""

from __future__ import annotations

import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from runtime.kernel.lifecycle import SubsystemLifecycle, SubsystemState

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

def _assert_raises(fn, exc_type: type, name: str) -> None:
    """Assert that fn() raises exc_type."""
    global _passed, _failed
    try:
        fn()
        print(f"  FAIL  {name}: expected {exc_type.__name__} but no exception raised")
        _failed += 1
    except exc_type:
        print(f"  PASS  {name}")
        _passed += 1
    except Exception as e:
        print(f"  FAIL  {name}: wrong exception {type(e).__name__}: {e}")
        _failed += 1


def _startup_sequence(name: str) -> SubsystemLifecycle:
    """Run canonical OFFLINE->INITIALIZING->READY->ACTIVE for named subsystem."""
    fsm = SubsystemLifecycle(name)
    _assert(fsm.state == SubsystemState.OFFLINE, f"{name}: starts OFFLINE")
    fsm.transition(SubsystemState.INITIALIZING)
    _assert(fsm.state == SubsystemState.INITIALIZING, f"{name}: OFFLINE->INITIALIZING")
    fsm.transition(SubsystemState.READY)
    _assert(fsm.state == SubsystemState.READY, f"{name}: INITIALIZING->READY")
    fsm.transition(SubsystemState.ACTIVE)
    _assert(fsm.state == SubsystemState.ACTIVE, f"{name}: READY->ACTIVE")
    return fsm


# ── Startup sequences for each subsystem ───────────────────────────────────────

def test_asr_startup():
    print("\nASR startup sequence")
    _startup_sequence("ASR")

def test_audio_startup():
    print("\nAudio startup sequence")
    _startup_sequence("Audio")

def test_vad_startup():
    print("\nVAD startup sequence")
    _startup_sequence("VAD")

def test_matcher_startup():
    print("\nMatcher startup sequence")
    _startup_sequence("Matcher")

def test_transport_startup():
    print("\nTransport startup sequence")
    _startup_sequence("Transport")


# ── Recovery path ──────────────────────────────────────────────────────────────

def test_recovery_sequence():
    print("\nRecovery sequence: ACTIVE -> FAULTED -> RECOVERING -> ACTIVE")
    fsm = _startup_sequence("ASR-recovery")

    # Use recover() helper: ACTIVE -> FAULTED -> RECOVERING
    fsm.recover("test fault")
    _assert(fsm.state == SubsystemState.RECOVERING, "ASR: ACTIVE->FAULTED->RECOVERING via recover()")

    # RECOVERING -> ACTIVE is legal
    fsm.transition(SubsystemState.ACTIVE)
    _assert(fsm.state == SubsystemState.ACTIVE, "ASR: RECOVERING->ACTIVE")


# ── Shutdown path ──────────────────────────────────────────────────────────────

def test_shutdown_sequence():
    print("\nShutdown sequence: ACTIVE -> READY -> OFFLINE")
    fsm = _startup_sequence("ASR-shutdown")

    fsm.transition(SubsystemState.READY)
    _assert(fsm.state == SubsystemState.READY, "ASR: ACTIVE->READY")

    fsm.transition(SubsystemState.OFFLINE)
    _assert(fsm.state == SubsystemState.OFFLINE, "ASR: READY->OFFLINE")


# ── shutdown() helper path ─────────────────────────────────────────────────────

def test_shutdown_helper():
    print("\nshutdown() helper from ACTIVE")
    fsm = _startup_sequence("ASR-shutdown-helper")
    fsm.shutdown()
    _assert(fsm.state == SubsystemState.OFFLINE, "ASR: shutdown() -> OFFLINE from ACTIVE")

    print("\nshutdown() helper from RECOVERING")
    fsm2 = _startup_sequence("ASR-shutdown-from-recovering")
    fsm2.recover()
    _assert(fsm2.state == SubsystemState.RECOVERING, "ASR: recover() -> RECOVERING")
    fsm2.shutdown()
    _assert(fsm2.state == SubsystemState.OFFLINE, "ASR: shutdown() -> OFFLINE from RECOVERING")


# ── Illegal transitions ────────────────────────────────────────────────────────

def test_illegal_offline_to_active():
    print("\nIllegal: OFFLINE -> ACTIVE must raise ValueError")
    fsm = SubsystemLifecycle("Test-illegal-1")
    _assert_raises(
        lambda: fsm.transition(SubsystemState.ACTIVE),
        ValueError,
        "OFFLINE -> ACTIVE raises ValueError"
    )

def test_illegal_active_to_initializing():
    print("\nIllegal: ACTIVE -> INITIALIZING must raise ValueError")
    fsm = _startup_sequence("Test-illegal-2")
    _assert_raises(
        lambda: fsm.transition(SubsystemState.INITIALIZING),
        ValueError,
        "ACTIVE -> INITIALIZING raises ValueError"
    )

def test_illegal_ready_to_recovering():
    print("\nIllegal: READY -> RECOVERING must raise ValueError")
    fsm = SubsystemLifecycle("Test-illegal-3")
    fsm.transition(SubsystemState.INITIALIZING)
    fsm.transition(SubsystemState.READY)
    _assert_raises(
        lambda: fsm.transition(SubsystemState.RECOVERING),
        ValueError,
        "READY -> RECOVERING raises ValueError"
    )

def test_illegal_offline_to_ready():
    print("\nIllegal: OFFLINE -> READY must raise ValueError")
    fsm = SubsystemLifecycle("Test-illegal-4")
    _assert_raises(
        lambda: fsm.transition(SubsystemState.READY),
        ValueError,
        "OFFLINE -> READY raises ValueError"
    )


# ── Main runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  AVAListener — Subsystem Lifecycle Regression Tests")
    print("=" * 60)

    test_asr_startup()
    test_audio_startup()
    test_vad_startup()
    test_matcher_startup()
    test_transport_startup()
    test_recovery_sequence()
    test_shutdown_sequence()
    test_shutdown_helper()
    test_illegal_offline_to_active()
    test_illegal_active_to_initializing()
    test_illegal_ready_to_recovering()
    test_illegal_offline_to_ready()

    print()
    print("=" * 60)
    print(f"  Results: {_passed}/{_passed + _failed} passed  |  {_failed} failed")
    print("=" * 60)

    sys.exit(0 if _failed == 0 else 1)
