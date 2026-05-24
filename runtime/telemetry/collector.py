"""
AVAListener — Telemetry Collector
=================================
Collect runtime metrics and optionally persist them to disk.
"""

from __future__ import annotations
import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from utils.logger import get_logger
from config.settings import METRICS_TO_DISK, METRICS_FILE_PATH

log = get_logger("telemetry")


@dataclass
class CandidateSession:
    phrase: str
    variant: str
    canonical: str
    start_time: float
    last_update: float
    peak_raw: float = 0.0
    peak_smooth: float = 0.0
    transcript_evolution: list[str] = field(default_factory=list)
    stabilization_frames: int = 0
    state: str = "CANDIDATE_STARTED"

    def update(self, text: str, raw_conf: float, smooth_conf: float, frames: int) -> None:
        self.last_update = time.monotonic()
        self.transcript_evolution.append(text)
        self.peak_raw = max(self.peak_raw, raw_conf)
        self.peak_smooth = max(self.peak_smooth, smooth_conf)
        self.stabilization_frames = max(self.stabilization_frames, frames)
        self.state = "CANDIDATE_UPDATED"

    def confirm(self) -> None:
        self.state = "CANDIDATE_CONFIRMED"

    def drop(self) -> None:
        self.state = "CANDIDATE_DROPPED"

    @property
    def duration_ms(self) -> float:
        return (self.last_update - self.start_time) * 1000.0


class TelemetryCollector:
    def __init__(self, metrics_to_disk: bool = METRICS_TO_DISK, metrics_path: str = METRICS_FILE_PATH) -> None:
        self.metrics_to_disk = metrics_to_disk
        self.metrics_path = metrics_path
        self.reset()

    def reset(self) -> None:
        self.wake_count = 0
        self.false_wake_count = 0
        self.trigger_latency_ms = []
        self.speech_durations_ms = []
        self.silence_durations_ms = []
        self.asr_latencies_ms = []
        self.inference_latencies_ms = []
        self.queue_depths = []
        self.stream_resets: list[dict[str, Any]] = []
        self.candidate_sessions: list[dict[str, Any]] = []
        self.active_candidate: CandidateSession | None = None

    def register_wake(self, latency_ms: float) -> None:
        self.wake_count += 1
        self.trigger_latency_ms.append(latency_ms)
        self._persist_if_enabled()

    def register_false_wake(self) -> None:
        self.false_wake_count += 1
        self._persist_if_enabled()

    def register_speech_duration(self, duration_ms: float) -> None:
        self.speech_durations_ms.append(duration_ms)
        self._persist_if_enabled()

    def register_silence_duration(self, duration_ms: float) -> None:
        self.silence_durations_ms.append(duration_ms)
        self._persist_if_enabled()

    def register_asr_latency(self, latency_ms: float) -> None:
        self.asr_latencies_ms.append(latency_ms)

    def register_inference_latency(self, latency_ms: float) -> None:
        self.inference_latencies_ms.append(latency_ms)

    def register_queue_depth(self, depth: int) -> None:
        self.queue_depths.append(depth)

    def register_stream_reset(self, reason: str, lifetime_s: float) -> None:
        self.stream_resets.append({
            "when": time.time(),
            "reason": reason,
            "lifetime_s": round(lifetime_s, 2),
        })
        self._persist_if_enabled()

    def start_candidate(self, phrase: str, variant: str, canonical: str, text: str, raw_conf: float, smooth_conf: float, frames: int) -> None:
        if self.active_candidate is not None:
            self._archive_candidate("replaced")
        self.active_candidate = CandidateSession(
            phrase=phrase,
            variant=variant,
            canonical=canonical,
            start_time=time.monotonic(),
            last_update=time.monotonic(),
            peak_raw=raw_conf,
            peak_smooth=smooth_conf,
            transcript_evolution=[text],
            stabilization_frames=frames,
        )
        log.debug("[TELEMETRY] candidate started %r", phrase)

    def update_candidate(self, text: str, raw_conf: float, smooth_conf: float, frames: int) -> None:
        if self.active_candidate is None:
            return
        self.active_candidate.update(text, raw_conf, smooth_conf, frames)
        log.debug("[TELEMETRY] candidate updated %r peak_raw=%.2f peak_smooth=%.2f", self.active_candidate.phrase, self.active_candidate.peak_raw, self.active_candidate.peak_smooth)

    def confirm_candidate(self) -> None:
        if self.active_candidate is None:
            return
        self.active_candidate.confirm()
        self.candidate_sessions.append(self._candidate_snapshot(self.active_candidate))
        self.active_candidate = None
        log.debug("[TELEMETRY] candidate confirmed")

    def drop_candidate(self) -> None:
        if self.active_candidate is None:
            return
        self.active_candidate.drop()
        self.candidate_sessions.append(self._candidate_snapshot(self.active_candidate))
        self.active_candidate = None
        self.register_false_wake()
        log.debug("[TELEMETRY] candidate dropped")

    def _archive_candidate(self, reason: str) -> None:
        if self.active_candidate is None:
            return
        self.active_candidate.drop()
        snapshot = self._candidate_snapshot(self.active_candidate)
        snapshot["archived_reason"] = reason
        self.candidate_sessions.append(snapshot)
        self.active_candidate = None
        self.register_false_wake()

    def _candidate_snapshot(self, candidate: CandidateSession) -> dict[str, Any]:
        return {
            "phrase": candidate.phrase,
            "variant": candidate.variant,
            "canonical": candidate.canonical,
            "state": candidate.state,
            "duration_ms": round(candidate.duration_ms, 1),
            "peak_raw": round(candidate.peak_raw, 3),
            "peak_smooth": round(candidate.peak_smooth, 3),
            "stabilization_frames": candidate.stabilization_frames,
            "transcript_evolution": candidate.transcript_evolution,
            "last_update": round(candidate.last_update, 3),
        }

    def get_metrics(self) -> dict[str, Any]:
        return {
            "wake_count": self.wake_count,
            "false_wake_count": self.false_wake_count,
            "avg_trigger_latency_ms": round(self._mean(self.trigger_latency_ms), 2),
            "avg_asr_latency_ms": round(self._mean(self.asr_latencies_ms), 2),
            "avg_inference_latency_ms": round(self._mean(self.inference_latencies_ms), 2),
            "avg_queue_depth": round(self._mean(self.queue_depths), 2),
            "avg_speech_duration_ms": round(self._mean(self.speech_durations_ms), 2),
            "avg_silence_duration_ms": round(self._mean(self.silence_durations_ms), 2),
            "stream_resets": self.stream_resets,
            "candidate_sessions": self.candidate_sessions,
        }

    def export_metrics_json(self, path: str | None = None) -> str:
        path = path or self.metrics_path
        metrics = self.get_metrics()
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(metrics, handle, indent=2)
        log.info("[TELEMETRY] exported metrics to %s", path)
        return path

    def _mean(self, values: list[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / len(values)

    def _persist_if_enabled(self) -> None:
        if self.metrics_to_disk:
            try:
                self.export_metrics_json()
            except Exception as exc:
                log.exception("[TELEMETRY] failed to persist metrics: %s", exc)
