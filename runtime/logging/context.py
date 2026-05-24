"""
AVAListener — Logging Context (Phase 5.1)
==========================================
Owner: context.py
Responsibility: LogContext ONLY — session IDs, correlation IDs, subsystem tags.

No formatter logic. No logger construction. No sink logic.
"""
from __future__ import annotations
import uuid
from typing import Dict


class LogContext:
    """
    Process-global logging context holder.
    Carries session_id, correlation_id, and subsystem tag through the log pipeline.

    Usage
    -----
    LogContext.new_session()           # at engine startup
    LogContext.set_correlation(cid)    # at utterance start
    LogContext.set_subsystem("ASR")    # at subsystem entry
    """
    _session_id: str = ""
    _correlation_id: str = ""
    _subsystem: str = ""

    @classmethod
    def set_session(cls, session_id: str) -> None:
        cls._session_id = session_id

    @classmethod
    def set_correlation(cls, correlation_id: str) -> None:
        cls._correlation_id = correlation_id

    @classmethod
    def set_subsystem(cls, subsystem: str) -> None:
        cls._subsystem = subsystem

    @classmethod
    def get(cls) -> Dict[str, str]:
        return {
            "session_id": cls._session_id,
            "correlation_id": cls._correlation_id,
            "subsystem": cls._subsystem,
        }

    @classmethod
    def new_session(cls) -> str:
        """Generate a new session ID and store it. Returns the new ID."""
        cls._session_id = f"sess_{uuid.uuid4().hex[:12]}"
        return cls._session_id

    @classmethod
    def clear(cls) -> None:
        cls._session_id = ""
        cls._correlation_id = ""
        cls._subsystem = ""
