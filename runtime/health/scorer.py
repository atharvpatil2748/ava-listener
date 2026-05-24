"""
AVAListener — Health Scorer (Phase 5.3 — revised)
===================================================
P5-BLOCK-005 compliance: weights declared alongside signal names — no hidden magic.

Each HEALTH_SIGNAL_MAP entry has an explicit weight. Weights are documented.
Total max penalty = sum(WEIGHTS.values()) = 1.0.
"""
from __future__ import annotations
from typing import Dict, Any

from runtime.health.signals import HealthSignals, compute_signals


# ── Explicit weight map — must match HEALTH_SIGNAL_MAP keys ────────────────────
# Weights represent the maximum score penalty each signal can contribute.
# Rationale documented inline.

SIGNAL_WEIGHTS: Dict[str, float] = {
    "queue_overruns":          0.20,  # Audio overruns directly degrade ASR quality
    "vad_lag":                 0.15,  # Resets indicate pipeline not keeping up
    "memory_pressure":         0.20,  # OOM risk is high-impact
    "restart_frequency":       0.25,  # Frequent restarts = unstable runtime
    "transport_latency":       0.10,  # High latency degrades UX but not correctness
    "dropped_wake_candidates": 0.10,  # Any dropped wake events is a bug
}

assert abs(sum(SIGNAL_WEIGHTS.values()) - 1.0) < 1e-9, \
    f"SIGNAL_WEIGHTS must sum to 1.0, got {sum(SIGNAL_WEIGHTS.values())}"


def compute_health_score(signals: HealthSignals) -> float:
    """
    Compute overall health score [0.0, 1.0] from HealthSignals.
    1.0 = fully healthy. 0.0 = fully degraded.

    Each signal contributes at most its weight as a penalty.
    Score = 1.0 - sum(min(signal_pressure * weight, weight) for each signal)
    """
    sig_dict = signals.to_dict()
    penalty = 0.0
    for name, weight in SIGNAL_WEIGHTS.items():
        pressure = sig_dict.get(name, 0.0)
        penalty += min(pressure * weight, weight)
    return max(0.0, min(1.0, 1.0 - penalty))


def score_from_metrics(metrics: Dict[str, Any]) -> float:
    """Convenience: compute score directly from raw MetricsCollector output."""
    signals = compute_signals(metrics)
    return compute_health_score(signals)
