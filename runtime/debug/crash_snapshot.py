"""
AVAListener — Crash Snapshot System (Phase 5.4 — revised)
===========================================================
Captures a complete runtime state snapshot at crash moment.

P5-BLOCK-004 compliance:
  CrashSnapshot ONLY consumes exported debug contracts:
    - streamer.export_debug_state()
    - engine._matcher_fsm.state / engine._transport_fsm.state (lifecycle FSMs — public enums)
    - engine.metrics_collector.get_all_metrics() (public API)
    - engine._watchdog.watchdog_metrics (public property)

  Never reaches into private subsystem internals (_state, _silero_state, etc.)
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from runtime.timing.clock import now_ns, uptime_s as clock_uptime


class CrashSnapshot:
    def __init__(self, engine, output_dir: str = "logs/crashes") -> None:
        self._engine = engine
        self._output_dir = output_dir
        os.makedirs(self._output_dir, exist_ok=True)

    def capture(self, reason: str = "unhandled_exception") -> Dict[str, Any]:
        """
        Collect complete runtime state via exported contracts only.
        Returns the snapshot dict and writes it to disk.
        """
        snapshot: Dict[str, Any] = {
            "schema_version": 1,
            "capture_timestamp_ns": now_ns(),
            "uptime_s": clock_uptime(),
            "reason": reason,
            "session_id": self._get_session_id(),
            # ASR + VAD state via exported contract
            "streamer_state": self._get_streamer_state(),
            # EMA / pipeline state from public engine attrs
            "ema_state": self._get_ema_state(),
            # Last candidate scores from public experiment metrics
            "last_matcher_scores": self._get_matcher_scores(),
            # Subsystem FSM states (public .state.value)
            "subsystem_fsm_states": self._get_subsystem_fsm_states(),
            # MetricsCollector public API
            "metrics": self._get_metrics(),
            # System memory
            "memory_mb": self._get_memory_mb(),
            # Watchdog public property
            "watchdog_metrics": self._get_watchdog_metrics(),
        }

        self._write(snapshot, reason)
        return snapshot

    # ── Exported-contract collectors ───────────────────────────────────────────

    def _get_session_id(self) -> str:
        try:
            from runtime.logging.context import LogContext
            return LogContext.get().get("session_id", "")
        except Exception:
            return ""

    def _get_streamer_state(self) -> Dict[str, Any]:
        """Consumes SherpaStreamer.export_debug_state() ONLY."""
        try:
            return self._engine._streamer.export_debug_state()
        except Exception as e:
            return {"error": str(e)}

    def _get_ema_state(self) -> Dict[str, Any]:
        """Reads public/semi-public attributes from WakeEngine."""
        try:
            return {
                "smooth_conf": getattr(self._engine, "_smooth_conf", 0.0),
                "hit_count": getattr(self._engine, "_hit_count", 0),
                "last_matched_phrase": getattr(self._engine, "_last_matched_phrase", ""),
            }
        except Exception:
            return {}

    def _get_matcher_scores(self) -> list:
        """Reads public experiment_metrics from WakeEngine."""
        try:
            scores = getattr(self._engine, "_experiment_metrics", {})
            return scores.get("candidateScores", [])[-10:]
        except Exception:
            return []

    def _get_subsystem_fsm_states(self) -> Dict[str, str]:
        """Reads public .state.value from SubsystemLifecycle FSMs."""
        states: Dict[str, str] = {}
        try:
            states["Matcher"] = self._engine._matcher_fsm.state.value
            states["Transport"] = self._engine._transport_fsm.state.value
        except Exception:
            pass
        return states

    def _get_metrics(self) -> Dict[str, Any]:
        """Consumes MetricsCollector.get_all_metrics() public API."""
        try:
            return self._engine.metrics_collector.get_all_metrics()
        except Exception:
            return {}

    def _get_memory_mb(self) -> Optional[float]:
        if not HAS_PSUTIL:
            return None
        try:
            return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        except Exception:
            return None

    def _get_watchdog_metrics(self) -> Dict[str, Any]:
        """Consumes RuntimeWatchdog.watchdog_metrics public property."""
        try:
            return self._engine._watchdog.watchdog_metrics
        except Exception:
            return {}

    def _write(self, snapshot: Dict[str, Any], reason: str) -> str:
        ts = int(time.time())
        filename = os.path.join(self._output_dir, f"crash_{ts}_{reason[:32]}.json")
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2, default=str)
        except Exception:
            pass
        return filename
