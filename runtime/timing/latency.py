"""
AVAListener — Latency Tracker with Explicit Stages (Phase 5.2 — revised)
=========================================================================
Explicit pipeline stage names enforced by architecture contract.

Canonical stages:
  capture_to_queue  — audio chunk lands in audio_queue
  vad               — VAD decision completes
  asr               — ASR partial/final hypothesis emitted
  matcher           — matcher scores computed
  wake_total        — wake event fired (end-to-end)

Usage
-----
tracker = LatencyTracker(correlation_id)
tracker.mark("capture_to_queue")
# ... audio processing ...
tracker.mark("vad")
tracker.mark("asr")
tracker.mark("matcher")
tracker.mark("wake_total")

latencies = tracker.to_dict()
# {"capture_to_queue_to_vad_ms": 3.2, "vad_to_asr_ms": 12.1, ...}
"""
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Dict, Optional


# ── Architecture-mandated stage names ──────────────────────────────────────────

PIPELINE_STAGES = (
    "capture_to_queue",
    "vad",
    "asr",
    "matcher",
    "wake_total",
)

# Ordered pairs that define measured intervals
STAGE_INTERVALS = (
    ("capture_to_queue", "vad",         "capture_to_vad_ms"),
    ("vad",              "asr",         "vad_to_asr_ms"),
    ("asr",              "matcher",     "asr_to_matcher_ms"),
    ("matcher",          "wake_total",  "matcher_to_wake_ms"),
    ("capture_to_queue", "wake_total",  "end_to_end_ms"),
)


@dataclass
class LatencySample:
    label: str
    duration_ms: float


class LatencyTracker:
    """
    Tracks per-stage pipeline latency for a single utterance session.
    One instance per correlation_id; discard after wake event.
    """

    def __init__(self, correlation_id: str) -> None:
        self.correlation_id = correlation_id
        self._marks: Dict[str, int] = {}

    def mark(self, stage: str) -> None:
        """
        Record current time for a named pipeline stage.

        Parameters
        ----------
        stage : str
            Must be one of PIPELINE_STAGES (enforced with warning).
        """
        if stage not in PIPELINE_STAGES:
            # Warn but don't crash — future stages may be added
            import warnings
            warnings.warn(
                f"LatencyTracker: unknown stage {stage!r}. "
                f"Expected one of {PIPELINE_STAGES}",
                stacklevel=2,
            )
        self._marks[stage] = time.time_ns()

    def measure(self, from_stage: str, to_stage: str) -> Optional[float]:
        """Return duration ms between two stages, or None if either is missing."""
        start = self._marks.get(from_stage)
        end = self._marks.get(to_stage)
        if start is None or end is None:
            return None
        return (end - start) / 1_000_000.0

    def to_dict(self) -> Dict[str, Optional[float]]:
        """
        Return all defined interval measurements as a dict.
        Values are milliseconds or None if the stage was not marked.
        """
        result: Dict[str, Optional[float]] = {}
        for from_s, to_s, label in STAGE_INTERVALS:
            result[label] = self.measure(from_s, to_s)
        return result

    @property
    def end_to_end_ms(self) -> Optional[float]:
        """Convenience: total capture-to-wake latency in ms."""
        return self.measure("capture_to_queue", "wake_total")


class RollingLatency:
    """
    Keeps a rolling window of latency samples for one named stage interval.
    Used by health scorer and diagnostics API for avg/p99/max reporting.
    """

    def __init__(self, label: str, window: int = 200) -> None:
        self.label = label
        self._window = window
        self._samples: list[float] = []

    def record(self, ms: float) -> None:
        self._samples.append(ms)
        if len(self._samples) > self._window:
            self._samples.pop(0)

    @property
    def avg_ms(self) -> float:
        if not self._samples:
            return 0.0
        return sum(self._samples) / len(self._samples)

    @property
    def p99_ms(self) -> float:
        if not self._samples:
            return 0.0
        s = sorted(self._samples)
        idx = max(0, int(len(s) * 0.99) - 1)
        return s[idx]

    @property
    def max_ms(self) -> float:
        return max(self._samples) if self._samples else 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "label": self.label,
            "avg_ms": round(self.avg_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "samples": len(self._samples),
        }
