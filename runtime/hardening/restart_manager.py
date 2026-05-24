"""
AVAListener — Restart Manager (Phase 4.2)
==========================================
Tracks restart counts per subsystem, enforces cooldown windows,
and emits structured telemetry for every restart action.

Subsystems managed: audio, asr, vad, matcher
Never touches wake logic, phrase registry, or ASR decoding.
"""

from __future__ import annotations

import time
import logging
from typing import Callable, Dict, Optional

from runtime.hardening.recovery_policy import RecoveryPolicy
from runtime.telemetry.events import emit_structured_event

log = logging.getLogger("restart_manager")

# Subsystems managed by this layer
MANAGED_SUBSYSTEMS = ("audio", "asr", "vad", "matcher")

# Default recovery policy per subsystem
_DEFAULT_POLICIES: Dict[str, dict] = {
    "audio":   dict(max_retries=5, backoff_initial_ms=200.0,  backoff_max_ms=8000.0,  escalation_threshold=3),
    "asr":     dict(max_retries=5, backoff_initial_ms=100.0,  backoff_max_ms=4000.0,  escalation_threshold=3),
    "vad":     dict(max_retries=3, backoff_initial_ms=200.0,  backoff_max_ms=3200.0,  escalation_threshold=2),
    "matcher": dict(max_retries=3, backoff_initial_ms=50.0,   backoff_max_ms=800.0,   escalation_threshold=2),
}


class SubsystemRestartRecord:
    def __init__(self, name: str, policy_kwargs: dict) -> None:
        self.name = name
        self.policy = RecoveryPolicy(**policy_kwargs)
        self.restart_count: int = 0
        self.last_restart_ts: float = 0.0
        self.cooldown_s: float = 2.0


class RestartManager:
    """
    Manages restart lifecycle for each managed subsystem.

    Usage
    -----
    mgr = RestartManager()
    mgr.register_restart_handler("asr", my_asr_restart_fn)

    # On failure:
    delay_ms = mgr.request_restart("asr", reason="worker_dead", correlation_id="...")
    time.sleep(delay_ms / 1000)
    """

    def __init__(self) -> None:
        self._records: Dict[str, SubsystemRestartRecord] = {
            name: SubsystemRestartRecord(name, _DEFAULT_POLICIES[name])
            for name in MANAGED_SUBSYSTEMS
        }
        self._handlers: Dict[str, Optional[Callable[[], None]]] = {
            name: None for name in MANAGED_SUBSYSTEMS
        }

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_restart_handler(self, subsystem: str, handler: Callable[[], None]) -> None:
        """Register the callable that performs the actual subsystem restart."""
        if subsystem not in MANAGED_SUBSYSTEMS:
            raise ValueError(f"Unknown subsystem: {subsystem!r}. Must be one of {MANAGED_SUBSYSTEMS}")
        self._handlers[subsystem] = handler

    # ------------------------------------------------------------------
    # Core operation
    # ------------------------------------------------------------------

    def request_restart(
        self,
        subsystem: str,
        reason: str = "unknown",
        correlation_id: str = "",
    ) -> float:
        """
        Record a failure, compute the backoff delay, check cooldown,
        invoke the registered handler (if any), and emit telemetry.

        Returns
        -------
        float
            The delay in **milliseconds** to wait before the next attempt.
            Callers should sleep for this duration before restarting.
        """
        if subsystem not in self._records:
            raise ValueError(f"Unknown subsystem: {subsystem!r}")

        rec = self._records[subsystem]
        rec.policy.record_failure()
        delay_ms = rec.policy.next_backoff()

        # Enforce cooldown — if last restart was too recent, add cooldown gap
        now = time.monotonic()
        since_last = now - rec.last_restart_ts
        if since_last < rec.cooldown_s and rec.last_restart_ts > 0:
            extra_ms = (rec.cooldown_s - since_last) * 1000
            delay_ms = max(delay_ms, extra_ms)
            log.debug(
                "[RESTART] %s cooldown active — extra %.0fms added",
                subsystem, extra_ms,
            )

        should_escalate = rec.policy.should_escalate()

        log.warning(
            "[RESTART] %s | reason=%s retries=%d/%d delay=%.0fms escalate=%s",
            subsystem, reason,
            rec.policy.retries, rec.policy.max_retries,
            delay_ms, should_escalate,
        )

        emit_structured_event(
            correlation_id=correlation_id,
            subsystem=subsystem,
            event_type="subsystem_restart_requested",
            payload={
                "reason": reason,
                "retries": rec.policy.retries,
                "max_retries": rec.policy.max_retries,
                "delay_ms": delay_ms,
                "should_escalate": should_escalate,
            },
        )

        # Invoke handler
        handler = self._handlers.get(subsystem)
        if handler is not None and not should_escalate:
            try:
                handler()
                rec.restart_count += 1
                rec.last_restart_ts = time.monotonic()
                emit_structured_event(
                    correlation_id=correlation_id,
                    subsystem=subsystem,
                    event_type="subsystem_restart_completed",
                    payload={"restart_count": rec.restart_count},
                )
            except Exception as exc:
                log.error("[RESTART] %s handler raised: %s", subsystem, exc)
                emit_structured_event(
                    correlation_id=correlation_id,
                    subsystem=subsystem,
                    event_type="subsystem_restart_failed",
                    payload={"error": str(exc)},
                )

        return delay_ms

    def record_success(self, subsystem: str) -> None:
        """Reset backoff after a successful recovery."""
        if subsystem in self._records:
            self._records[subsystem].policy.reset()

    def should_escalate(self, subsystem: str) -> bool:
        if subsystem in self._records:
            return self._records[subsystem].policy.should_escalate()
        return False

    def get_restart_count(self, subsystem: str) -> int:
        if subsystem in self._records:
            return self._records[subsystem].restart_count
        return 0

    def get_stats(self) -> Dict[str, dict]:
        return {
            name: {
                "restart_count": rec.restart_count,
                "policy": repr(rec.policy),
            }
            for name, rec in self._records.items()
        }
