# -*- coding: utf-8 -*-
"""
AVAListener - Smoke Test Suite (Phase 0 Baseline)
==================================================
Verifies environment, imports, config integrity, model file presence,
and basic matcher/variant behavior — all WITHOUT a microphone or live ASR.

These tests form the Phase 0 regression firewall. Every future phase must
keep all of these passing. A failure here means the baseline has regressed.

Usage:
    python -m pytest tests/smoke/test_smoke.py -v
    python tests/smoke/test_smoke.py          (standalone, no pytest needed)

Exit code: 0 = all pass, 1 = one or more failures.
"""
from __future__ import annotations

import sys
import os
import importlib
import hashlib
import json
import time

# Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# -- Path bootstrap ---------------------------------------------------------
# Allows running as:  python tests/smoke/test_smoke.py  from ava-listener/
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _ROOT)

# Force CPU-only (mirrors main.py)
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("ORT_NO_OPERATOR_CUSTOM_OPS", "1")

# -- Phase 0.5: Load test profile into registry BEFORE importing matcher ------
# The matcher/variants modules read from the registry on every call.
# Loading the test profile here ensures all SMOKE-06 matcher checks work.
_PROFILE_PATH = os.path.join(_ROOT, "tests", "profiles", "arvsal_test.json")
try:
    from core.engine import _load_profile_into_registry
    _load_profile_into_registry(_PROFILE_PATH)
except Exception as _profile_load_err:
    # If profile loading fails, SMOKE-06 matcher tests will fail too — that's correct behaviour.
    pass

# ─────────────────────────────────────────────────────────────────────────────
# Test infrastructure
# ─────────────────────────────────────────────────────────────────────────────

_results: list[tuple[str, bool, str]] = []  # (name, passed, detail)


def _check(name: str, cond: bool, detail: str = "") -> bool:
    _results.append((name, cond, detail))
    return cond


def _section(title: str) -> None:
    width = 64
    print(f"\n{'='*width}")
    print(f"  {title}")
    print(f"{'='*width}")


# ─────────────────────────────────────────────────────────────────────────────
# SMOKE-01: Python version
# ─────────────────────────────────────────────────────────────────────────────

def smoke_01_python_version() -> None:
    _section("SMOKE-01: Python Version")
    major, minor = sys.version_info[:2]
    ok = (major == 3 and minor >= 10)
    detail = f"Python {major}.{minor}.{sys.version_info[2]}"
    _check("Python >= 3.10", ok, detail)
    print(f"  {'PASS' if ok else 'FAIL'}  {detail}")


# ─────────────────────────────────────────────────────────────────────────────
# SMOKE-02: Core dependency imports
# ─────────────────────────────────────────────────────────────────────────────

def smoke_02_imports() -> None:
    _section("SMOKE-02: Dependency Imports")
    packages = [
        ("numpy",           "numpy"),
        ("sounddevice",     "sounddevice"),
        ("RapidFuzz",       "rapidfuzz"),
        ("jellyfish",       "jellyfish"),
        ("webrtcvad",       "webrtcvad"),
        ("onnxruntime",     "onnxruntime"),
        ("sherpa_onnx",     "sherpa_onnx"),
    ]
    for display_name, import_name in packages:
        try:
            mod = importlib.import_module(import_name)
            ver = getattr(mod, "__version__", "?")
            ok = True
            detail = f"v{ver}"
        except ImportError as e:
            ok = False
            detail = str(e)
        _check(f"import {display_name}", ok, detail)
        print(f"  {'PASS' if ok else 'FAIL'}  import {display_name:<20} {detail}")


# ─────────────────────────────────────────────────────────────────────────────
# SMOKE-03: Engine module imports (no microphone opened)
# ─────────────────────────────────────────────────────────────────────────────

def smoke_03_engine_imports() -> None:
    _section("SMOKE-03: Engine Module Imports")
    modules = [
        "config.settings",
        "config.schema",
        "detection.matcher",
        "detection.variants",
        "confidence.scorer",
        "decision.cooldown",
        "utils.logger",
        "audio.buffer",
        "runtime.state_machine",
        "runtime.watchdog",
        "runtime.matcher.registry.phrase_registry",
        "telemetry.collector",
        "integration.stdout_bridge",
    ]
    for mod_name in modules:
        try:
            importlib.import_module(mod_name)
            ok = True
            detail = "OK"
        except Exception as e:
            ok = False
            detail = f"{type(e).__name__}: {e}"
        _check(f"import {mod_name}", ok, detail)
        print(f"  {'PASS' if ok else 'FAIL'}  {mod_name:<42} {detail}")


# ─────────────────────────────────────────────────────────────────────────────
# SMOKE-04: Config integrity
# ─────────────────────────────────────────────────────────────────────────────

def smoke_04_config_integrity() -> None:
    _section("SMOKE-04: Config Integrity (Phase 0.5)")
    from config.settings import (
        SAMPLE_RATE, BLOCK_SIZE, NUM_THREADS,
        DEFAULT_THRESHOLD, EMA_RISE_ALPHA, EMA_DECAY_ALPHA,
        STABILITY_CAP, COOLDOWN_SECONDS,
    )
    from runtime.matcher.registry.phrase_registry import get_registry

    # Phase 0.5: WAKEWORDS removed from settings. Phrases now live in the registry.
    registry = get_registry()
    active_count = registry.active_count()
    total_count  = registry.count()
    ok_registry = active_count > 0
    _check("Registry has active phrases (profile loaded)", ok_registry,
           f"{active_count}/{total_count} phrases")
    print(f"  {'PASS' if ok_registry else 'FAIL'}  Registry: {active_count} active / {total_count} total phrases")

    # Numeric sanity checks
    num_checks = [
        ("SAMPLE_RATE == 16000",        SAMPLE_RATE == 16000,          str(SAMPLE_RATE)),
        ("BLOCK_SIZE > 0",              BLOCK_SIZE > 0,                str(BLOCK_SIZE)),
        ("NUM_THREADS >= 1",            NUM_THREADS >= 1,              str(NUM_THREADS)),
        ("DEFAULT_THRESHOLD in [0,1]",  0 < DEFAULT_THRESHOLD <= 1,   f"{DEFAULT_THRESHOLD:.2f}"),
        ("EMA_RISE_ALPHA in (0,1]",     0 < EMA_RISE_ALPHA <= 1,       f"{EMA_RISE_ALPHA:.2f}"),
        ("EMA_DECAY_ALPHA in (0,1]",    0 < EMA_DECAY_ALPHA <= 1,      f"{EMA_DECAY_ALPHA:.2f}"),
        ("STABILITY_CAP > 0",           STABILITY_CAP > 0,             str(STABILITY_CAP)),
        ("COOLDOWN_SECONDS > 0",        COOLDOWN_SECONDS > 0,          f"{COOLDOWN_SECONDS:.1f}s"),
    ]
    for label, cond, val in num_checks:
        _check(label, cond, val)
        print(f"  {'PASS' if cond else 'FAIL'}  {label:<40} = {val}")

    # All phrase thresholds in range (from registry)
    active_phrases = registry.get_active()
    threshold_ok = all(0 < cfg.threshold <= 1.0 for cfg in active_phrases)
    _check("All phrase thresholds in (0,1]", threshold_ok)
    print(f"  {'PASS' if threshold_ok else 'FAIL'}  All phrase thresholds in range")

    # No duplicate canonical phrases
    phrases = [cfg.phrase for cfg in registry.get_all()]
    no_dupes = len(phrases) == len(set(phrases))
    _check("No duplicate canonical phrases", no_dupes)
    print(f"  {'PASS' if no_dupes else 'FAIL'}  No duplicate canonical phrases")


# ─────────────────────────────────────────────────────────────────────────────
# SMOKE-05: Model files present and SHA256 matches manifest
# ─────────────────────────────────────────────────────────────────────────────

def smoke_05_model_files() -> None:
    _section("SMOKE-05: Model File Integrity")
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    manifest_path = os.path.join(root, "models_manifest.json")

    if not os.path.exists(manifest_path):
        _check("models_manifest.json exists", False, manifest_path)
        print(f"  FAIL  models_manifest.json not found at {manifest_path}")
        return

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    for entry in manifest.get("models", []):
        name   = entry["name"]
        path   = entry["path"]
        expected_sha = entry.get("sha256", "")
        expected_size = entry.get("size_bytes", 0)

        # File exists
        exists = os.path.isfile(path)
        _check(f"{name} exists", exists, path if not exists else "")
        if not exists:
            print(f"  FAIL  {name:<30} NOT FOUND at {path}")
            continue

        # Size check
        actual_size = os.path.getsize(path)
        size_ok = (actual_size == expected_size)
        _check(f"{name} size matches", size_ok, f"{actual_size} vs {expected_size}")
        print(f"  {'PASS' if size_ok else 'WARN'}  {name:<30} size={actual_size:,} bytes")

        # SHA256 check (skip if no expected hash in manifest)
        if expected_sha:
            sha = hashlib.sha256()
            with open(path, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    sha.update(chunk)
            actual_sha = sha.hexdigest()
            sha_ok = (actual_sha == expected_sha)
            _check(f"{name} SHA256 matches", sha_ok,
                   f"expected {expected_sha[:12]}… actual {actual_sha[:12]}…")
            print(f"  {'PASS' if sha_ok else 'FAIL'}  {name:<30} SHA256: {'OK' if sha_ok else 'MISMATCH'}")


# ─────────────────────────────────────────────────────────────────────────────
# SMOKE-06: Matcher + variant correctness (no ASR)
# ─────────────────────────────────────────────────────────────────────────────

def smoke_06_matcher_variants() -> None:
    _section("SMOKE-06: Matcher & Variant Core Logic")
    from detection.matcher import best_match, anchor_present
    from detection.variants import get_variants, get_canonical

    # Anchor gate: known-good variants must pass
    must_pass = [
        "arvsal", "arsal", "our whistle", "hey arvsal", "wake up arvsal",
        "listen arvsal",
    ]
    for v in must_pass:
        ok = anchor_present(v)
        _check(f"anchor_present({v!r})", ok)
        print(f"  {'PASS' if ok else 'FAIL'}  anchor_present({v!r})")

    # Anchor gate: must NOT pass
    must_fail = ["wake up", "hey", "hello world", "the weather is nice"]
    for v in must_fail:
        ok = not anchor_present(v)
        _check(f"NOT anchor_present({v!r})", ok)
        print(f"  {'PASS' if ok else 'FAIL'}  NOT anchor_present({v!r})")

    # Variant deduplication
    variants = get_variants()
    dedup_ok = len(variants) == len(set(variants))
    lowercase_ok = all(v == v.lower() for v in variants)
    _check("get_variants() deduplicated", dedup_ok, f"{len(variants)} variants")
    _check("get_variants() all lowercase", lowercase_ok)
    print(f"  {'PASS' if dedup_ok else 'FAIL'}  get_variants() deduplicated ({len(variants)} variants)")
    print(f"  {'PASS' if lowercase_ok else 'FAIL'}  get_variants() all lowercase")

    # Canonical mapping
    canon_cases = [
        ("arvsal",          "arvsal"),
        ("arsal",           "arvsal"),
        ("our whistle",     "arvsal"),
        ("hey arsel",       "hey arvsal"),
    ]
    for variant, expected in canon_cases:
        result = get_canonical(variant)
        ok = result == expected
        _check(f"get_canonical({variant!r}) == {expected!r}", ok, str(result))
        print(f"  {'PASS' if ok else 'FAIL'}  get_canonical({variant!r}) -> {result!r}")

    # Matcher: known true positives must score above 0 with a phrase match
    tp_cases = [
        ("arvsal",       "arvsal"),
        ("hey arvsal",   "hey arvsal"),
        ("our whistle",  "arvsal"),
    ]
    for hyp, expected_phrase in tp_cases:
        score, phrase, variant = best_match([(hyp, 3)])
        ok = (phrase == expected_phrase and score > 0)
        _check(f"best_match({hyp!r}) -> {expected_phrase!r}", ok,
               f"score={score:.2f} phrase={phrase!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  best_match({hyp!r:<20}) -> phrase={phrase!r} score={score:.2f}")

    # Matcher: known false positives must NOT match
    fp_cases = ["the weather is nice today", "hello world", "open the browser"]
    for hyp in fp_cases:
        score, phrase, variant = best_match([(hyp, 4)])
        ok = phrase == ""
        _check(f"best_match({hyp!r}) -> no match", ok, f"phrase={phrase!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  best_match({hyp!r:<30}) -> no match (phrase={phrase!r})")


# ─────────────────────────────────────────────────────────────────────────────
# SMOKE-07: Cooldown gate
# ─────────────────────────────────────────────────────────────────────────────

def smoke_07_cooldown() -> None:
    _section("SMOKE-07: Cooldown Gate")
    from decision.cooldown import CooldownGate

    gate = CooldownGate()

    # Initially: can trigger
    ok1 = gate.can_trigger()
    _check("CooldownGate: can trigger initially", ok1)
    print(f"  {'PASS' if ok1 else 'FAIL'}  can_trigger() = True initially")

    # After marking triggered: cannot trigger
    gate.mark_triggered()
    ok2 = not gate.can_trigger()
    _check("CooldownGate: blocked after trigger", ok2)
    print(f"  {'PASS' if ok2 else 'FAIL'}  can_trigger() = False after mark_triggered()")

    # time_remaining() returns > 0
    remaining = gate.time_remaining()
    ok3 = remaining > 0
    _check("CooldownGate: time_remaining() > 0", ok3, f"{remaining:.2f}s")
    print(f"  {'PASS' if ok3 else 'FAIL'}  time_remaining() = {remaining:.2f}s")


# ─────────────────────────────────────────────────────────────────────────────
# SMOKE-08: Hypothesis buffer
# ─────────────────────────────────────────────────────────────────────────────

def smoke_08_hypothesis_buffer() -> None:
    _section("SMOKE-08: Hypothesis Buffer")
    from audio.buffer import HypothesisBuffer

    buf = HypothesisBuffer()
    buf.push("hello", 3)
    buf.push("hello world", 5)
    window = buf.get_window()

    ok1 = len(window) >= 1
    _check("HypothesisBuffer returns non-empty window", ok1, f"len={len(window)}")
    print(f"  {'PASS' if ok1 else 'FAIL'}  get_window() returned {len(window)} entries")

    buf.clear()
    window_after_clear = buf.get_window()
    ok2 = len(window_after_clear) == 0
    _check("HypothesisBuffer.clear() empties window", ok2)
    print(f"  {'PASS' if ok2 else 'FAIL'}  after clear(), window is empty")


# ─────────────────────────────────────────────────────────────────────────────
# SMOKE-09: State machine (no audio)
# ─────────────────────────────────────────────────────────────────────────────

def smoke_09_state_machine() -> None:
    _section("SMOKE-09: Runtime State Machine")
    from runtime.state_machine import RuntimeStateMachine

    sm = RuntimeStateMachine()
    ok1 = sm is not None
    _check("RuntimeStateMachine instantiates", ok1)
    print(f"  {'PASS' if ok1 else 'FAIL'}  RuntimeStateMachine() instantiates")

    try:
        sm.transition("start")
        ok2 = True
    except Exception as e:
        ok2 = False
    _check("RuntimeStateMachine.transition('start') runs", ok2)
    print(f"  {'PASS' if ok2 else 'FAIL'}  transition('start') runs without error")


# ─────────────────────────────────────────────────────────────────────────────
# SMOKE-10: models_manifest.json schema
# ─────────────────────────────────────────────────────────────────────────────

def smoke_10_manifest_schema() -> None:
    _section("SMOKE-10: Models Manifest Schema")
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    manifest_path = os.path.join(root, "models_manifest.json")

    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        ok_parse = True
    except Exception as e:
        ok_parse = False
        _check("models_manifest.json parses as JSON", False, str(e))
        print(f"  FAIL  Parse error: {e}")
        return

    _check("models_manifest.json parses as JSON", True)
    print(f"  PASS  models_manifest.json valid JSON")

    # Required fields per model entry
    required_keys = {"name", "path", "sha256", "size_bytes", "load_status"}
    models = manifest.get("models", [])
    ok_structure = (
        isinstance(models, list)
        and len(models) > 0
        and all(required_keys <= set(m) for m in models)
    )
    _check("All model entries have required keys", ok_structure, f"{len(models)} entries")
    print(f"  {'PASS' if ok_structure else 'FAIL'}  {len(models)} model entries with required keys")

    # All load_status are "OK"
    all_ok = all(m.get("load_status") == "OK" for m in models)
    _check("All model load_status == 'OK'", all_ok)
    print(f"  {'PASS' if all_ok else 'FAIL'}  All load_status == 'OK'")


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

def run_all() -> int:
    print("\n" + "=" * 64)
    print("  AVAListener — Smoke Tests (Phase 0 Baseline)")
    print("=" * 64)

    t0 = time.monotonic()

    smoke_01_python_version()
    smoke_02_imports()
    smoke_03_engine_imports()
    smoke_04_config_integrity()
    smoke_05_model_files()
    smoke_06_matcher_variants()
    smoke_07_cooldown()
    smoke_08_hypothesis_buffer()
    smoke_09_state_machine()
    smoke_10_manifest_schema()

    elapsed = time.monotonic() - t0
    passed  = sum(1 for _, ok, _ in _results if ok)
    failed  = sum(1 for _, ok, _ in _results if not ok)
    total   = len(_results)

    print(f"\n{'='*64}")
    print(f"  Results: {passed}/{total} passed  |  {failed} failed  |  {elapsed:.1f}s")
    print(f"{'='*64}\n")

    if failed:
        print("  FAILED checks:")
        for name, ok, detail in _results:
            if not ok:
                print(f"    ✗  {name}  →  {detail}")
        print()

    return 0 if failed == 0 else 1


# ── pytest integration ─────────────────────────────────────────────────────────
# When run under pytest, each SMOKE-XX becomes a separate test function.

def test_python_version():       smoke_01_python_version();     _assert_all()
def test_imports():              smoke_02_imports();             _assert_all()
def test_engine_imports():       smoke_03_engine_imports();      _assert_all()
def test_config_integrity():     smoke_04_config_integrity();    _assert_all()
def test_model_files():          smoke_05_model_files();         _assert_all()
def test_matcher_variants():     smoke_06_matcher_variants();    _assert_all()
def test_cooldown():             smoke_07_cooldown();            _assert_all()
def test_hypothesis_buffer():    smoke_08_hypothesis_buffer();   _assert_all()
def test_state_machine():        smoke_09_state_machine();       _assert_all()
def test_manifest_schema():      smoke_10_manifest_schema();     _assert_all()


def _assert_all():
    """After each SMOKE section, assert all recorded checks passed."""
    failures = [(name, detail) for name, ok, detail in _results if not ok]
    if failures:
        msg = "\n".join(f"  FAIL: {n}  ({d})" for n, d in failures)
        assert False, f"\nSmoke check failures:\n{msg}"
    # Clear results for next section when running under pytest
    _results.clear()


if __name__ == "__main__":
    sys.exit(run_all())
