"""
AVAListener — Logger Construction (Phase 5.1)
==============================================
Owner: logger.py
Responsibility: Logger factory and configuration ONLY.

Wires LogContext + StructuredFormatter + Sinks into named loggers.
No context management. No formatter logic. No sink implementations.
"""
from __future__ import annotations
import logging
from typing import Optional

from runtime.logging.sinks import ConsoleSink, FileSink, LogSink


# ── Runtime logger registry ─────────────────────────────────────────────────────

_configured: bool = False


def configure_runtime_logging(
    level: int = logging.INFO,
    file_path: Optional[str] = None,
    json_console: bool = False,
) -> None:
    """
    Configure the root runtime logger with the specified sinks.
    Should be called once at process startup.

    Parameters
    ----------
    level : int
        Logging level (e.g. logging.DEBUG, logging.INFO).
    file_path : str or None
        If set, also write JSON logs to this file path.
    json_console : bool
        If True, emit JSON on stderr instead of human-readable text.
    """
    global _configured
    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers if called more than once
    if not root.handlers:
        console = ConsoleSink()
        root.addHandler(console.get_handler())

    if file_path and not _configured:
        file_sink = FileSink(file_path)
        root.addHandler(file_sink.get_handler())

    _configured = True


def get_runtime_logger(name: str) -> logging.Logger:
    """
    Return a named logger for a runtime subsystem.
    Caller should NOT configure handlers — use configure_runtime_logging() instead.
    """
    return logging.getLogger(name)
