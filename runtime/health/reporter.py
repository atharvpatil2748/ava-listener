"""
AVAListener — Health Reporter (Phase 5.3 — revised)
=====================================================
Formats the full health report for the diagnostics API.

Output matches the architecture spec:
{
  "runtimeHealth": 0.91,
  "status": "HEALTHY",
  "subsystems": { "vad": "ACTIVE", ... },
  "signals": { "queue_overruns": 0.0, ... },
  "signal_map": { ... HEALTH_SIGNAL_MAP descriptions ... },
  "metrics": { ... raw MetricsCollector values ... }
}
"""
from __future__ import annotations
import copy
from typing import Any, Dict

from runtime.health.signals import compute_signals, HEALTH_SIGNAL_MAP
from runtime.health.scorer import compute_health_score, SIGNAL_WEIGHTS


class HealthReporter:
    def __init__(self, metrics_collector, subsystem_fsms: Dict[str, Any]) -> None:
        """
        Parameters
        ----------
        metrics_collector : MetricsCollector
        subsystem_fsms : dict mapping subsystem name → SubsystemLifecycle instance
        """
        self._metrics = metrics_collector
        self._fsms = subsystem_fsms

    def get_report(self) -> Dict[str, Any]:
        """
        Returns a deep-copied health report dict safe for external consumers.
        """
        raw_metrics = self._metrics.get_all_metrics()
        signals = compute_signals(raw_metrics)
        score = compute_health_score(signals)

        subsystem_states: Dict[str, str] = {}
        for name, fsm in self._fsms.items():
            try:
                subsystem_states[name] = fsm.state.value
            except Exception:
                subsystem_states[name] = "UNKNOWN"

        status = "HEALTHY" if score > 0.8 else ("DEGRADED" if score > 0.5 else "CRITICAL")

        report = {
            "runtimeHealth": round(score, 4),
            "status": status,
            "subsystems": subsystem_states,
            "signals": signals.to_dict(),
            "signal_weights": dict(SIGNAL_WEIGHTS),
            "signal_descriptions": {k: v.description for k, v in HEALTH_SIGNAL_MAP.items()},
            "metrics": raw_metrics,
        }
        return copy.deepcopy(report)
