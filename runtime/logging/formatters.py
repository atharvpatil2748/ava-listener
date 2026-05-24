"""
AVAListener — Log Formatters (Phase 5.1)
=========================================
Owner: formatters.py
Responsibility: JSON and pretty-print formatter logic ONLY.

No context management. No logger construction. No sink logic.
"""
from __future__ import annotations
import json
import logging
import time
from typing import Any, Dict

from runtime.logging.context import LogContext


class StructuredFormatter(logging.Formatter):
    """
    Dual-mode log formatter.

    json_mode=True  → emit each record as a JSON line (for file sinks, telemetry).
    json_mode=False → emit human-readable text with session context prefix (for console).

    JSON schema (schema_version: 1):
    {
      "schema_version": 1,
      "ts": <float epoch>,
      "level": "INFO",
      "logger": "engine",
      "message": "...",
      "session_id": "sess_...",
      "correlation_id": "...",
      "subsystem": "..."
    }
    """

    def __init__(self, json_mode: bool = False) -> None:
        super().__init__()
        self.json_mode = json_mode

    def format(self, record: logging.LogRecord) -> str:
        ctx = LogContext.get()
        if self.json_mode:
            return self._format_json(record, ctx)
        return self._format_text(record, ctx)

    def _format_json(self, record: logging.LogRecord, ctx: Dict[str, str]) -> str:
        payload: Dict[str, Any] = {
            "schema_version": 1,
            "ts": record.created,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "session_id": ctx["session_id"],
            "correlation_id": ctx["correlation_id"],
            "subsystem": ctx["subsystem"] or record.name,
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)

    def _format_text(self, record: logging.LogRecord, ctx: Dict[str, str]) -> str:
        ts = time.strftime("%H:%M:%S", time.localtime(record.created))
        ctx_str = ""
        if ctx["session_id"]:
            ctx_str = f" [{ctx['session_id'][:8]}]"
        if ctx["correlation_id"]:
            ctx_str += f"[{ctx['correlation_id'][:8]}]"
        return (
            f"{ts}{ctx_str} [{record.levelname:<7}] "
            f"{record.name}: {record.getMessage()}"
        )
