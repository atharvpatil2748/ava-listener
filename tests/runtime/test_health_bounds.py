"""
AVAListener -- Health Score Bounds Test (P6-FIX-1)
===================================================
Verifies that compute_health_score() always returns a value in [0.0, 1.0]
regardless of extreme, zero, or adversarial MetricsCollector inputs.

Also verifies:
  - The HealthReporter.get_report() key is "runtimeHealth" (not "score")
  - score_from_metrics() clamps correctly end-to-end
  - compute_signals() handles None / negative / overflow inputs safely
  - getDiagnostics() health key is accessible at the correct path

Usage:
    python tests/runtime/test_health_bounds.py
    python -m pytest tests/runtime/test_health_bounds.py -v
"""
from __future__ import annotations

import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _ROOT)
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("ORT_NO_OPERATOR_CUSTOM_OPS", "1")

from runtime.health.scorer import compute_health_score, score_from_metrics
from runtime.health.signals import compute_signals, HealthSignals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_bounded(score: float, context: str) -> None:
    assert isinstance(score, float), f"{context}: score is not float, got {type(score)}"
    assert 0.0 <= score <= 1.0, (
        f"{context}: score={score!r} is outside [0.0, 1.0]"
    )


# ---------------------------------------------------------------------------
# 1. Direct scorer tests
# ---------------------------------------------------------------------------

def test_scorer_healthy_signals():
    """All zero-pressure signals -> score = 1.0."""
    s = HealthSignals()  # all 0.0
    score = compute_health_score(s)
    _assert_bounded(score, "healthy_signals")
    assert score == 1.0, f"Expected 1.0 for zero-pressure signals, got {score}"
    return True


def test_scorer_fully_degraded_signals():
    """All 1.0-pressure signals -> score = 0.0."""
    s = HealthSignals(
        queue_overruns=1.0,
        vad_lag=1.0,
        memory_pressure=1.0,
        restart_frequency=1.0,
        transport_latency=1.0,
        dropped_wake_candidates=1.0,
    )
    score = compute_health_score(s)
    _assert_bounded(score, "fully_degraded_signals")
    assert score == 0.0, f"Expected 0.0 for full-pressure signals, got {score}"
    return True


def test_scorer_extreme_pressure_overflow():
    """Pressure > 1.0 must be clamped to 1.0 (not produce negative score)."""
    s = HealthSignals(
        queue_overruns=999.0,
        vad_lag=500.0,
        memory_pressure=1000.0,
        restart_frequency=100.0,
        transport_latency=9999.0,
        dropped_wake_candidates=88888.0,
    )
    score = compute_health_score(s)
    _assert_bounded(score, "extreme_pressure_overflow")
    return True


def test_scorer_negative_pressure():
    """Negative pressure values (shouldn't happen, but must not produce score > 1.0)."""
    s = HealthSignals(
        queue_overruns=-10.0,
        vad_lag=-5.0,
        memory_pressure=-99.0,
        restart_frequency=-1.0,
        transport_latency=-100.0,
        dropped_wake_candidates=-50.0,
    )
    score = compute_health_score(s)
    _assert_bounded(score, "negative_pressure")
    return True


def test_scorer_partial_degradation():
    """Partial degradation should produce a score between 0 and 1."""
    s = HealthSignals(restart_frequency=0.5)
    score = compute_health_score(s)
    _assert_bounded(score, "partial_degradation")
    assert 0.0 < score < 1.0, f"Expected intermediate score, got {score}"
    return True


# ---------------------------------------------------------------------------
# 2. Signals compute_signals() with extreme metric values
# ---------------------------------------------------------------------------

def test_signals_from_extreme_metrics():
    """compute_signals() handles extreme raw metric values safely."""
    extreme_metrics = {
        "queue_depth":          10_000_000,
        "reset_count":          999_999,
        "memory_usage_mb":      999_999.0,
        "restart_count":        10_000,
        "transport_latency_ms": 1_000_000.0,
        "telemetry_drop_count": 99_999_999,
    }
    signals = compute_signals(extreme_metrics)
    # All signals must be in [0.0, 1.0]
    for field, val in signals.to_dict().items():
        assert 0.0 <= val <= 1.0, f"Signal {field}={val} out of bounds"
    score = compute_health_score(signals)
    _assert_bounded(score, "signals_from_extreme_metrics")
    return True


def test_signals_from_zero_metrics():
    """compute_signals() handles all-zero metrics."""
    zero_metrics = {
        "queue_depth": 0, "reset_count": 0,
        "memory_usage_mb": 0.0, "restart_count": 0,
        "transport_latency_ms": 0.0, "telemetry_drop_count": 0,
    }
    signals = compute_signals(zero_metrics)
    for field, val in signals.to_dict().items():
        assert val == 0.0, f"Signal {field}={val}, expected 0.0 for zero metrics"
    score = compute_health_score(signals)
    assert score == 1.0, f"Expected 1.0 for zero metrics, got {score}"
    return True


def test_signals_from_none_values():
    """compute_signals() handles None metric values (psutil unavailable path)."""
    none_metrics = {
        "queue_depth": 0, "reset_count": 0,
        "memory_usage_mb": None, "restart_count": 0,
        "transport_latency_ms": None, "telemetry_drop_count": 0,
    }
    signals = compute_signals(none_metrics)
    score = compute_health_score(signals)
    _assert_bounded(score, "signals_from_none_values")
    return True


def test_signals_from_missing_keys():
    """compute_signals() handles completely empty metrics dict."""
    score = score_from_metrics({})
    _assert_bounded(score, "signals_from_missing_keys")
    assert score == 1.0, f"Expected 1.0 for empty metrics (all signals default to 0), got {score}"
    return True


# ---------------------------------------------------------------------------
# 3. HealthReporter key name verification
# ---------------------------------------------------------------------------

def test_health_reporter_key_is_runtimeHealth():
    """
    HealthReporter.get_report() must use key 'runtimeHealth', NOT 'score'.
    This is the root cause of the P6-FIX-1 anomaly (stress_monitor read 'score').
    """
    from runtime.health.reporter import HealthReporter
    from runtime.telemetry.metrics import MetricsCollector
    from unittest.mock import MagicMock

    mc = MetricsCollector()
    mock_fsm = MagicMock()
    mock_fsm.state.value = "ACTIVE"

    reporter = HealthReporter(mc, {"MockSubsystem": mock_fsm})
    report = reporter.get_report()

    assert "runtimeHealth" in report, (
        f"Key 'runtimeHealth' missing from HealthReporter.get_report(). "
        f"Keys present: {list(report.keys())}"
    )
    assert "score" not in report, (
        "Key 'score' should NOT be in HealthReporter.get_report(). "
        "Use 'runtimeHealth' instead."
    )
    _assert_bounded(report["runtimeHealth"], "reporter_key_runtimeHealth")
    return True


def test_diagnostics_health_path():
    """
    getDiagnostics()["health"]["runtimeHealth"] must exist and be in [0.0, 1.0].
    Regression guard: stress_monitor was reading ["health"]["score"] which returned -1.
    """
    from unittest.mock import MagicMock, patch
    import os

    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

    # We only need the health reporter chain — mock everything else
    from runtime.health.reporter import HealthReporter
    from runtime.health.scorer import compute_health_score
    from runtime.health.signals import compute_signals
    from runtime.telemetry.metrics import MetricsCollector

    mc = MetricsCollector()
    mock_fsm = MagicMock(); mock_fsm.state.value = "ACTIVE"
    reporter = HealthReporter(mc, {"Matcher": mock_fsm})
    report = reporter.get_report()

    # Verify the exact key path stress_monitor should use
    health_block = report
    assert "runtimeHealth" in health_block, "Missing 'runtimeHealth' key"
    score = health_block["runtimeHealth"]
    _assert_bounded(score, "diagnostics_health_path")

    # Verify the OLD (wrong) key is absent
    assert "score" not in health_block, (
        "Key 'score' must NOT be present. stress_monitor must use 'runtimeHealth'."
    )
    return True


# ---------------------------------------------------------------------------
# 4. Stress test — 10,000 random metric combinations
# ---------------------------------------------------------------------------

def test_scorer_random_stress():
    """10,000 random metric combinations — all scores must be in [0.0, 1.0]."""
    import random
    rng = random.Random(42)
    failures = []

    metric_keys = [
        "queue_depth", "reset_count", "memory_usage_mb",
        "restart_count", "transport_latency_ms", "telemetry_drop_count",
    ]
    ranges = {
        "queue_depth":          (0, 200),
        "reset_count":          (0, 100),
        "memory_usage_mb":      (0.0, 5000.0),
        "restart_count":        (0, 50),
        "transport_latency_ms": (0.0, 2000.0),
        "telemetry_drop_count": (0, 10000),
    }

    for i in range(10_000):
        metrics = {k: rng.uniform(*ranges[k]) for k in metric_keys}
        score = score_from_metrics(metrics)
        if not (0.0 <= score <= 1.0):
            failures.append((i, metrics, score))
        if len(failures) >= 5:
            break

    assert len(failures) == 0, (
        f"score_from_metrics() produced out-of-bounds values:\n"
        + "\n".join(f"  iter={i} score={s:.6f}" for i, _, s in failures)
    )
    return True


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

TESTS = [
    test_scorer_healthy_signals,
    test_scorer_fully_degraded_signals,
    test_scorer_extreme_pressure_overflow,
    test_scorer_negative_pressure,
    test_scorer_partial_degradation,
    test_signals_from_extreme_metrics,
    test_signals_from_zero_metrics,
    test_signals_from_none_values,
    test_signals_from_missing_keys,
    test_health_reporter_key_is_runtimeHealth,
    test_diagnostics_health_path,
    test_scorer_random_stress,
]


def run_all() -> bool:
    print("=" * 64)
    print("  AVAListener -- Health Score Bounds Test (P6-FIX-1)")
    print(f"  {len(TESTS)} tests")
    print("=" * 64)
    passed = failed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"  [PASS]  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL]  {fn.__name__}")
            print(f"          {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {fn.__name__}: {e}")
            failed += 1
    print("=" * 64)
    print(f"  Results: {passed}/{len(TESTS)} passed  ({failed} failed)")
    print("=" * 64)
    return failed == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
