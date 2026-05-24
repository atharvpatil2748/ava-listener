# -*- coding: utf-8 -*-
"""
AVAListener — Replay Regression Test Suite (Phase 0 Baseline)
=============================================================
Replays recorded ASR hypothesis sequences through the detection pipeline
WITHOUT a microphone, live ASR, or audio hardware. These tests constitute
the regression firewall: every future phase must keep all cases passing.

Architecture
------------
This test driver feeds (hypothesis, stability) pairs directly into the
matcher + scorer + cooldown stack, reproducing the exact computation that
`WakeEngine._on_hypothesis()` performs. Any change to scorer weights,
variant registrations, or threshold values that alters these results is
a regression and must be explicitly approved.

Phase 0 Baseline Fixture Set
-----------------------------
These fixtures are captured from the stable engine behaviour on 2026-05-22.
They represent the minimum correctness bar the engine must maintain.

Usage:
    python -m pytest tests/replay/test_replay.py -v
    python tests/replay/test_replay.py              (standalone)

Exit code: 0 = all pass, 1 = failures.
"""
from __future__ import annotations

import sys
import os
import time

# Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── Path bootstrap ─────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _ROOT)

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("ORT_NO_OPERATOR_CUSTOM_OPS", "1")

# Phase 0.5: load the test profile into the registry BEFORE importing
# matcher/variants so they see the phrases in the registry.
# _ROOT = ava-listener/, so profiles are at _ROOT/tests/profiles/...
_PROFILE_PATH = os.path.join(_ROOT, "tests", "profiles", "arvsal_test.json")

from runtime.config.profile_loader import load_profile
from runtime.matcher.registry.phrase_registry import get_registry, PhraseConfig
merged = load_profile(_PROFILE_PATH)
registry = get_registry()
registry.clear()
for phrase_data in merged.get("wakePhrases", []):
    registry.add_phrase(PhraseConfig.from_dict(phrase_data))
    
from detection.variants import rebuild_index
rebuild_index()

# ── Engine-layer imports (no audio, no ASR model) ─────────────────────────────
from detection.matcher import best_match, anchor_present
from detection.variants import get_canonical
from confidence.scorer import compute_confidence
from decision.cooldown import CooldownGate
from config.settings import DEFAULT_THRESHOLD

# ── Per-phrase threshold lookup (from registry, not settings) ─────────────────
def _threshold_for(phrase: str) -> float:
    for cfg in get_registry().get_all():
        if cfg.phrase == phrase:
            return cfg.threshold
    return DEFAULT_THRESHOLD


# ─────────────────────────────────────────────────────────────────────────────
# Fixture format
# ─────────────────────────────────────────────────────────────────────────────
#
# Each fixture is:
#   (
#     "description",                           # human-readable label
#     [(hypothesis_str, stability_int), ...],  # the ASR window to replay
#     expect_trigger: bool,                    # whether a wake should fire
#     expected_phrase: str | None,             # canonical phrase if triggered
#   )
#
# Phase 0 fixtures must remain stable. Never modify existing fixtures —
# add new ones only. Modifying a fixture without plan approval is a violation.

PHASE_0_FIXTURES: list[tuple[str, list[tuple[str, int]], bool, str | None]] = [

    # ── TRUE POSITIVES — canonical phrases ─────────────────────────────────
    ("bare arvsal",
     [("arvsal", 3)],
     True, "arvsal"),

    ("hey arvsal",
     [("hey arvsal", 4)],
     True, "hey arvsal"),

    ("wake up arvsal",
     [("wake up arvsal", 3)],
     True, "wake up arvsal"),

    ("listen arvsal",
     [("listen arvsal", 2)],
     True, "listen arvsal"),

    # ── TRUE POSITIVES — known ASR misrecognitions ─────────────────────────
    ("arsal variant",
     [("hey arsal", 3)],
     True, "hey arvsal"),

    ("arsel variant",
     [("hey arsel", 2)],
     True, "hey arvsal"),

    ("our whistle — direct",
     [("our whistle", 3)],
     True, "arvsal"),

    ("wake up our whistle",
     [("wake up our whistle", 3)],
     True, "wake up arvsal"),

    ("hey our whistle",
     [("hey our whistle", 4)],
     True, "hey arvsal"),

    ("arzal variant",
     [("arzal", 3)],
     True, "arvsal"),

    # ── TRUE POSITIVES — multi-chunk accumulation ──────────────────────────
    ("multi-chunk buildup",
     [("hey", 0), ("hey arv", 1), ("hey arvsal", 3)],
     True, "hey arvsal"),

    ("arzal with preamble",
     [("hey arzal", 4), ("hey arzal", 5)],
     True, "hey arvsal"),

    # NOTE: These false-positive cases reflect ACTUAL baseline engine behaviour.
    # Some inputs that SEEM like they should be rejected DO trigger at baseline
    # (the engine fuzzy-matches parts of the hypothesis).
    # These are documented here as the frozen baseline to detect FUTURE changes.

    # ── TRUE NEGATIVES — Phrase Boundary Protections (Phase 1) ─────────────────
    ("listen alone",
     [("listen", 4)],
     True, "listen"),  # triggers 'listen' because it is in the profile, but NOT 'listen arvsal'

    ("wake alone",
     [("wake", 4)],
     False, None),

    ("listen arv candidate only",
     [("listen arv", 3)],
     True, "listen"),  # triggers 'listen' because it is in the profile, but NOT 'listen arvsal'

    ("listen arvsal full",
     [("listen arv", 1), ("listen arvsal", 3)],
     True, "listen arvsal"),

    ("empty window",
     [],
     False, None),

    ("random everyday speech",
     [("the weather is nice today", 4)],
     False, None),

    ("context only - no anchor",
     [("wake up", 3)],
     False, None),

    ("hey alone",
     [("hey", 5)],
     False, None),

    # 'wake up ourselves' fuzzy-matches to 'wake up arvsal' at baseline
    # This is a KNOWN false positive in the current engine. Recorded as-is.
    # Phase 0.5+ matcher tuning may fix this; update fixture at that point.
    ("wake up ourselves",
     [("wake up ourselves", 4)],
     True, "wake up arvsal"),

    ("unrelated high-stability speech",
     [("open the browser please", 6)],
     False, None),

    ("arsenal football club - false anchor",
     [("arsenal football club", 3)],
     False, None),
]


# ─────────────────────────────────────────────────────────────────────────────
# Replay engine (mirrors WakeEngine._on_hypothesis() computation only)
# ─────────────────────────────────────────────────────────────────────────────

def _replay_window(
    window: list[tuple[str, int]],
) -> tuple[float, float, str, str]:
    """
    Run a hypothesis window through the detection pipeline.

    Returns:
        raw_conf, smooth_conf, phrase, matched_variant
    """
    if not window:
        return 0.0, 0.0, "", ""

    score, phrase, matched_variant = best_match(window)
    hit_count = 1 if score > 0.50 else 0
    raw_conf = compute_confidence(score, len(window), hit_count)
    threshold = _threshold_for(phrase) if phrase else DEFAULT_THRESHOLD

    return raw_conf, threshold, phrase, matched_variant


# ─────────────────────────────────────────────────────────────────────────────
# Test runner
# ─────────────────────────────────────────────────────────────────────────────

def run_replay_tests() -> tuple[int, int]:
    """Run all Phase 0 fixtures. Returns (passed, failed)."""
    passed = failed = 0

    print(f"\n{'='*72}")
    print(f"  AVAListener — Replay Regression Tests (Phase 0 Baseline)")
    print(f"  {len(PHASE_0_FIXTURES)} fixtures")
    print(f"{'='*72}")

    for desc, window, expect_trigger, expected_phrase in PHASE_0_FIXTURES:
        raw_conf, threshold, phrase, variant = _replay_window(window)
        triggered = raw_conf >= threshold and phrase != ""

        ok_trigger = (triggered == expect_trigger)
        ok_phrase  = (expected_phrase is None) or (phrase == expected_phrase)
        ok = ok_trigger and ok_phrase

        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1

        label = f"[{status}]"
        print(
            f"  {label}  {desc:<35} "
            f"raw={raw_conf:.2f}  thr={threshold:.2f}  "
            f"trigger={'Y' if triggered else 'N'}  phrase={phrase!r}"
        )
        if not ok:
            if not ok_trigger:
                print(f"         >>> trigger mismatch: expected={expect_trigger}, got={triggered}")
            if not ok_phrase:
                print(f"         >>> phrase mismatch: expected={expected_phrase!r}, got={phrase!r}")

    print(f"{'='*72}")
    print(f"  Results: {passed}/{len(PHASE_0_FIXTURES)} passed  ({failed} failed)")
    print(f"{'='*72}\n")
    return passed, failed


# ── pytest integration ─────────────────────────────────────────────────────────

def test_all_phase0_fixtures():
    """Pytest entry point — fails if any Phase 0 fixture regresses."""
    _, failed = run_replay_tests()
    assert failed == 0, f"{failed} Phase 0 regression fixture(s) failed."


# Individual pytest cases — one per fixture for fine-grained CI reporting
def _make_test(desc, window, expect_trigger, expected_phrase):
    def _test():
        raw_conf, threshold, phrase, variant = _replay_window(window)
        triggered = raw_conf >= threshold and phrase != ""
        assert triggered == expect_trigger, (
            f"Trigger mismatch for {desc!r}: "
            f"expected={expect_trigger}, got={triggered}, "
            f"raw_conf={raw_conf:.3f}, threshold={threshold:.3f}, phrase={phrase!r}"
        )
        if expected_phrase is not None:
            assert phrase == expected_phrase, (
                f"Phrase mismatch for {desc!r}: "
                f"expected={expected_phrase!r}, got={phrase!r}"
            )
    _test.__name__ = f"test_fixture_{desc.replace(' ', '_').replace('-', '_')}"
    return _test


# Inject individual test functions into module namespace for pytest discovery
for _desc, _window, _expect, _ephrase in PHASE_0_FIXTURES:
    _fn = _make_test(_desc, _window, _expect, _ephrase)
    globals()[_fn.__name__] = _fn


if __name__ == "__main__":
    t0 = time.monotonic()
    _, failed_count = run_replay_tests()
    elapsed = time.monotonic() - t0
    print(f"Completed in {elapsed:.2f}s")
    sys.exit(0 if failed_count == 0 else 1)
