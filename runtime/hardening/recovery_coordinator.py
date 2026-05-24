"""
AVAListener — Recovery Coordinator (Phase 4.4)
===============================================
Observes subsystem state, health score, watchdog events, and fault
classification, then decides between recover / restart / escalate / shutdown.

This layer sits above RestartManager and uses FaultClassifier output to
select the right action. It does NOT touch wake logic, matcher, or ASR decoding.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Dict, Optional, TYPE_CHECKING

from runtime.hardening.fault_classifier import FaultType, classify
from runtime.hardening.restart_manager import RestartManager
from runtime.telemetry.events import emit_structured_event

if TYPE_CHECKING:
    from runtime.kernel.lifecycle import SubsystemLifecycle

log = logging.getLogger("recovery_coordinator")


class RecoveryAction(str):
    RECOVER   = "recover"
    RESTART   = "restart"
    ESCALATE  = "escalate"
    SHUTDOWN  = "shutdown"


class RecoveryCoordinator:
    """
    Central decision-maker for runtime recovery.

    Wired into:
      - RuntimeWatchdog (watchdog events)
      - SubsystemLifecycle FSMs (state change observations)
      - HealthReport (health score)
      - RestartManager (executes restarts with backoff)

    Usage
    -----
    coord = RecoveryCoordinator(restart_manager)
    coord.observe_fault("asr", exc, correlation_id="...")
    """

    def __init__(
        self,
        restart_manager: RestartManager,
        shutdown_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self._restart_mgr = restart_manager
        self._shutdown_cb = shutdown_callback
        self._escalation_log: Dict[str, int] = {}   # subsystem → escalation count

    # ------------------------------------------------------------------
    # Primary entry-points
    # ------------------------------------------------------------------

    def observe_fault(
        self,
        subsystem: str,
        cause,
        *,
        is_timeout: bool = False,
        is_queue_overflow: bool = False,
        is_watchdog: bool = False,
        correlation_id: str = "",
    ) -> RecoveryAction:
        """
        Classify the fault and dispatch the appropriate recovery action.

        Returns the RecoveryAction taken.
        """
        fault_type = classify(
            cause,
            is_timeout=is_timeout,
            is_queue_overflow=is_queue_overflow,
            is_watchdog=is_watchdog,
        )

        log.info(
            "[RECOVERY] %s fault classified as %s | cause=%r",
            subsystem, fault_type.value, cause,
        )

        emit_structured_event(
            correlation_id=correlation_id,
            subsystem=subsystem,
            event_type="fault_classified",
            payload={
                "fault_type": fault_type.value,
                "cause": str(cause),
                "is_watchdog": is_watchdog,
                "is_timeout": is_timeout,
            },
        )

        if fault_type == FaultType.CRITICAL:
            return self._do_shutdown(subsystem, cause, correlation_id)

        if fault_type == FaultType.TRANSIENT:
            return self._do_recover(subsystem, cause, correlation_id)

        # RECOVERABLE — attempt restart, escalate if policy exhausted
        if self._restart_mgr.should_escalate(subsystem):
            return self._do_escalate(subsystem, cause, correlation_id)

        return self._do_restart(subsystem, str(cause), correlation_id)

    def observe_watchdog_event(
        self,
        subsystem: str,
        reason: str,
        correlation_id: str = "",
    ) -> RecoveryAction:
        """Shortcut for watchdog-originated events (reason is a string)."""
        return self.observe_fault(
            subsystem,
            reason,
            is_watchdog=True,
            correlation_id=correlation_id,
        )

    def record_recovery_success(self, subsystem: str) -> None:
        """Call after a successful recovery to reset backoff state."""
        self._restart_mgr.record_success(subsystem)
        self._escalation_log.pop(subsystem, None)
        log.info("[RECOVERY] %s recovered successfully — backoff reset", subsystem)
        emit_structured_event(
            correlation_id="",
            subsystem=subsystem,
            event_type="recovery_success",
            payload={},
        )

    # ------------------------------------------------------------------
    # Internal actions
    # ------------------------------------------------------------------

    def _do_recover(
        self, subsystem: str, cause, correlation_id: str
    ) -> RecoveryAction:
        """Lightweight in-place recovery (no full restart)."""
        log.info("[RECOVERY] %s → RECOVER (transient fault)", subsystem)
        emit_structured_event(
            correlation_id=correlation_id,
            subsystem=subsystem,
            event_type="recovery_action",
            payload={"action": RecoveryAction.RECOVER, "cause": str(cause)},
        )
        return RecoveryAction.RECOVER

    def _do_restart(
        self, subsystem: str, reason: str, correlation_id: str
    ) -> RecoveryAction:
        """Full subsystem restart with backoff enforcement."""
        log.warning("[RECOVERY] %s → RESTART", subsystem)
        self._restart_mgr.request_restart(
            subsystem, reason=reason, correlation_id=correlation_id
        )
        emit_structured_event(
            correlation_id=correlation_id,
            subsystem=subsystem,
            event_type="recovery_action",
            payload={"action": RecoveryAction.RESTART, "reason": reason},
        )
        return RecoveryAction.RESTART

    def _do_escalate(
        self, subsystem: str, cause, correlation_id: str
    ) -> RecoveryAction:
        """Policy exhausted — escalate (notify supervisor/operator)."""
        self._escalation_log[subsystem] = self._escalation_log.get(subsystem, 0) + 1
        log.error(
            "[RECOVERY] %s → ESCALATE (policy exhausted, escalations=%d)",
            subsystem, self._escalation_log[subsystem],
        )
        emit_structured_event(
            correlation_id=correlation_id,
            subsystem=subsystem,
            event_type="recovery_escalated",
            payload={
                "cause": str(cause),
                "escalation_count": self._escalation_log[subsystem],
            },
        )
        return RecoveryAction.ESCALATE

    def _do_shutdown(
        self, subsystem: str, cause, correlation_id: str
    ) -> RecoveryAction:
        """Critical fault — initiate controlled engine shutdown."""
        log.critical(
            "[RECOVERY] %s → SHUTDOWN (critical fault: %s)", subsystem, cause
        )
        emit_structured_event(
            correlation_id=correlation_id,
            subsystem=subsystem,
            event_type="critical_shutdown",
            payload={"cause": str(cause)},
        )
        if self._shutdown_cb is not None:
            try:
                self._shutdown_cb()
            except Exception as exc:
                log.error("[RECOVERY] shutdown callback raised: %s", exc)
        return RecoveryAction.SHUTDOWN
