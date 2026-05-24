"""
AVAListener — Health Signal Definitions (Phase 5.3 — revised)
=============================================================
P5-BLOCK-005 compliance: explicit HEALTH_SIGNAL_MAP — no hidden magic weighting.

Every signal has:
  - name          canonical name
  - metric_key    key in MetricsCollector.get_all_metrics()
  - normalizer    lambda raw_value → [0.0, 1.0] pressure
  - description   human-readable explanation
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, List


# ── Explicit signal map ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SignalDefinition:
    name: str
    metric_key: str
    normalizer: Callable[[float], float]
    description: str


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


HEALTH_SIGNAL_MAP: Dict[str, SignalDefinition] = {
    "queue_overruns": SignalDefinition(
        name="queue_overruns",
        metric_key="queue_depth",
        normalizer=lambda v: _clamp(v / 100.0),
        description="Audio queue depth as fraction of saturation (100 = full overrun)",
    ),
    "vad_lag": SignalDefinition(
        name="vad_lag",
        metric_key="reset_count",
        normalizer=lambda v: _clamp(v / 20.0),
        description="ASR stream resets as proxy for VAD/ASR processing lag (>20 = degraded)",
    ),
    "memory_pressure": SignalDefinition(
        name="memory_pressure",
        metric_key="memory_usage_mb",
        normalizer=lambda v: _clamp((v or 0.0) / 2048.0),
        description="RSS memory usage as fraction of 2 GB budget ceiling",
    ),
    "restart_frequency": SignalDefinition(
        name="restart_frequency",
        metric_key="restart_count",
        normalizer=lambda v: _clamp(v / 5.0),
        description="Subsystem restart count — >5 in session = fully degraded",
    ),
    "transport_latency": SignalDefinition(
        name="transport_latency",
        metric_key="transport_latency_ms",
        normalizer=lambda v: _clamp((v or 0.0) / 500.0),
        description="Transport round-trip latency as fraction of 500ms threshold",
    ),
    "dropped_wake_candidates": SignalDefinition(
        name="dropped_wake_candidates",
        metric_key="telemetry_drop_count",
        normalizer=lambda v: _clamp(v / 500.0),
        description="Telemetry/event drop count — should always be 0 in healthy state",
    ),
}


# ── HealthSignals container ────────────────────────────────────────────────────

@dataclass
class HealthSignals:
    """
    Named health signal pressures derived from HEALTH_SIGNAL_MAP.
    All values are [0.0 = healthy, 1.0 = fully degraded].
    """
    queue_overruns: float = 0.0
    vad_lag: float = 0.0
    memory_pressure: float = 0.0
    restart_frequency: float = 0.0
    transport_latency: float = 0.0
    dropped_wake_candidates: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "queue_overruns": self.queue_overruns,
            "vad_lag": self.vad_lag,
            "memory_pressure": self.memory_pressure,
            "restart_frequency": self.restart_frequency,
            "transport_latency": self.transport_latency,
            "dropped_wake_candidates": self.dropped_wake_candidates,
        }


def compute_signals(metrics: Dict) -> HealthSignals:
    """
    Convert MetricsCollector output → HealthSignals using HEALTH_SIGNAL_MAP.
    Every normalization is explicit and traceable.
    """
    def apply(sig_name: str) -> float:
        sig = HEALTH_SIGNAL_MAP[sig_name]
        raw = metrics.get(sig.metric_key, 0) or 0
        return sig.normalizer(float(raw))

    return HealthSignals(
        queue_overruns=apply("queue_overruns"),
        vad_lag=apply("vad_lag"),
        memory_pressure=apply("memory_pressure"),
        restart_frequency=apply("restart_frequency"),
        transport_latency=apply("transport_latency"),
        dropped_wake_candidates=apply("dropped_wake_candidates"),
    )
