"""
AVAListener — Runtime Watchdog
==============================
Monitor microphone/ASR/VAD health and perform automatic recovery.
Phase 4: Integrated RecoveryPolicy backoff to prevent restart death loops.
"""

import threading
import time
import traceback
from utils.logger import get_logger
from runtime.hardening.recovery_policy import RecoveryPolicy
from runtime.hardening.fault_classifier import classify_watchdog_trigger, FaultType

log = get_logger("watchdog")


class RuntimeWatchdog:
    def __init__(self, streamer, interval_s: float = 5.0, worker_timeout_s: float = 4.0, queue_threshold: int = 18):
        self._streamer = streamer
        self._interval = interval_s
        self._worker_timeout = worker_timeout_s
        self._queue_threshold = queue_threshold
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        # Metrics (Phase 0.5 refinement)
        self._resets_total = 0
        self._resets_by_reason = {
            "worker_dead": 0,
            "worker_hang": 0,
            "queue_overflow": 0,
            "vad_failure": 0,
        }

        # Phase 4: RecoveryPolicy backoff — prevents restart death loops
        # CRITICAL faults are escalated; TRANSIENT/RECOVERABLE apply backoff.
        self._recovery_policy = RecoveryPolicy(
            max_retries=8,
            backoff_initial_ms=100.0,
            backoff_max_ms=8000.0,
            escalation_threshold=4,
        )
        self._escalated: bool = False
        self._next_allowed_reset: float = 0.0  # monotonic time

    @property
    def watchdog_metrics(self) -> dict:
        avg_idle = getattr(self._streamer, "avg_worker_idle_ms", 0.0)
        avg_processing = getattr(self._streamer, "avg_worker_processing_ms", 0.0)
        return {
            "resets_total": self._resets_total,
            "resets_by_reason": dict(self._resets_by_reason),
            "avg_worker_idle_ms": avg_idle,
            "avg_worker_processing_ms": avg_processing,
            "recovery_retries": self._recovery_policy.retries,
            "recovery_escalated": self._escalated,
        }

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="watchdog")
        self._thread.start()
        log.debug("[WATCHDOG] started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _monitor_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._check_worker()
                self._check_queue()
                self._check_vad()
            except Exception:
                log.exception("[WATCHDOG] unexpected error: %s", traceback.format_exc())
            time.sleep(self._interval)

    def _check_worker(self) -> None:
        worker = getattr(self._streamer, "_worker_thread", None)
        heartbeat = getattr(self._streamer, "_worker_heartbeat", None)
        processing_active = getattr(self._streamer, "_processing_active", False)
        if worker is None or heartbeat is None:
            return

        if not worker.is_alive():
            log.error("[WATCHDOG] ASR worker thread died — restarting stream")
            self._recover_stream("worker_dead")
            return

        age = time.monotonic() - heartbeat
        if processing_active and age > self._worker_timeout:
            log.warning("[WATCHDOG] ASR worker heartbeat stale %.1fs while processing — resetting stream", age)
            self._recover_stream("worker_hang")

    def _check_queue(self) -> None:
        qsize = self._streamer._audio_queue.qsize()
        if qsize > self._queue_threshold:
            log.warning(
                "[WATCHDOG] audio queue overflow: %d > %d — resetting stream",
                qsize, self._queue_threshold
            )
            self._recover_stream("queue_overflow")

    def _check_vad(self) -> None:
        vad = getattr(self._streamer, "_vad", None)
        if vad is None:
            return
        if vad._silero_sess is None and vad.stats.get("silero_dropped", 0) > 100:
            log.warning("[WATCHDOG] Silero VAD dropping too many frames — resetting stream")
            self._recover_stream("vad_failure")

    def _recover_stream(self, reason: str) -> None:
        # ── Phase 4: Backoff gate ───────────────────────────────────────────────
        fault_type = classify_watchdog_trigger(reason)

        if self._escalated:
            log.error(
                "[WATCHDOG] Recovery already ESCALATED after %d retries — "
                "suppressing further resets for reason=%s",
                self._recovery_policy.retries, reason,
            )
            return

        now = time.monotonic()
        if now < self._next_allowed_reset:
            wait = self._next_allowed_reset - now
            log.debug("[WATCHDOG] Backoff active — %.1fs until next reset allowed", wait)
            return

        # Record failure and compute next backoff delay
        self._recovery_policy.record_failure()
        delay_ms = self._recovery_policy.next_backoff()
        self._next_allowed_reset = now + (delay_ms / 1000.0)

        if self._recovery_policy.should_escalate():
            self._escalated = True
            log.error(
                "[WATCHDOG] Recovery policy ESCALATED after %d retries — "
                "manual intervention required. Last reason: %s",
                self._recovery_policy.retries, reason,
            )
            return

        log.debug(
            "[WATCHDOG] Recovery backoff: retry=%d delay=%.0fms fault=%s",
            self._recovery_policy.retries, delay_ms, fault_type.value,
        )

        # ── Perform the actual stream reset ─────────────────────────────────────
        self._resets_total += 1
        if reason in self._resets_by_reason:
            self._resets_by_reason[reason] += 1
        else:
            self._resets_by_reason[reason] = 1

        try:
            self._streamer._reset_stream(reason=reason)
            # Reset backoff on non-CRITICAL successful recovery
            if fault_type != FaultType.CRITICAL:
                self._recovery_policy.reset()
                self._escalated = False
        except Exception as exc:
            log.error("[WATCHDOG] recovery failed: %s", exc)

    def reset_recovery_state(self) -> None:
        """Call externally after a manual restart to clear escalation state."""
        self._recovery_policy.reset()
        self._escalated = False
        self._next_allowed_reset = 0.0
        log.info("[WATCHDOG] Recovery state cleared")
