"""
AVAListener — Fault Classifier (Phase 4.3)
==========================================
Classifies failures into triage categories so the recovery coordinator
can select the correct restart strategy.

Never touches matcher scoring, phrase registry, wake thresholds, or ASR decoding.
"""

from __future__ import annotations

import queue
from enum import Enum
from typing import Union


class FaultType(str, Enum):
    TRANSIENT    = "TRANSIENT"     # e.g. one-off timeout, brief queue spike
    RECOVERABLE  = "RECOVERABLE"   # e.g. audio device reset, ASR stream error
    CRITICAL     = "CRITICAL"      # e.g. model missing, unrecoverable crash


# ── Exception type → FaultType mapping ─────────────────────────────────────────

_TRANSIENT_EXCEPTIONS = (
    TimeoutError,
    queue.Empty,
    queue.Full,
    OSError,          # transient audio device errors
)

_CRITICAL_EXCEPTIONS = (
    FileNotFoundError,
    MemoryError,
    SystemExit,
    KeyboardInterrupt,
)


def classify_exception(exc: BaseException) -> FaultType:
    """
    Map an exception to a FaultType.

    Classification priority:
      1. CRITICAL   — unrecoverable failures (missing model, memory)
      2. TRANSIENT  — brief/sporadic errors (timeouts, queue blips)
      3. RECOVERABLE — everything else (treated as recoverable by default)
    """
    if isinstance(exc, _CRITICAL_EXCEPTIONS):
        return FaultType.CRITICAL
    if isinstance(exc, _TRANSIENT_EXCEPTIONS):
        return FaultType.TRANSIENT
    return FaultType.RECOVERABLE


def classify_watchdog_trigger(reason: str) -> FaultType:
    """
    Map watchdog trigger reasons to a FaultType.

    Known watchdog reasons:
      - worker_dead  → RECOVERABLE (thread died, can restart)
      - worker_hang  → TRANSIENT   (heartbeat stale, may self-resolve)
      - queue_overflow → TRANSIENT
      - vad_failure  → RECOVERABLE
    """
    _TRANSIENT_TRIGGERS = {"worker_hang", "queue_overflow", "inactivity"}
    _CRITICAL_TRIGGERS  = {"model_corrupted", "memory_exhausted"}

    if reason in _CRITICAL_TRIGGERS:
        return FaultType.CRITICAL
    if reason in _TRANSIENT_TRIGGERS:
        return FaultType.TRANSIENT
    return FaultType.RECOVERABLE   # worker_dead, vad_failure, etc.


def classify(
    cause: Union[BaseException, str, None],
    *,
    is_timeout: bool = False,
    is_queue_overflow: bool = False,
    is_watchdog: bool = False,
) -> FaultType:
    """
    Unified classifier entry-point.

    Parameters
    ----------
    cause:
        The exception, watchdog reason string, or None.
    is_timeout:
        Caller signals this was a timeout event.
    is_queue_overflow:
        Caller signals this was a queue overflow event.
    is_watchdog:
        Caller signals this originated from the watchdog monitor.
    """
    if is_timeout or is_queue_overflow:
        return FaultType.TRANSIENT

    if isinstance(cause, BaseException):
        return classify_exception(cause)

    if is_watchdog and isinstance(cause, str):
        return classify_watchdog_trigger(cause)

    return FaultType.RECOVERABLE
