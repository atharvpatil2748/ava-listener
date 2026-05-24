"""
AVAListener — Log Sinks (Phase 5.1)
=====================================
Owner: sinks.py
Responsibility: Sink abstractions ONLY — stdout, file, and future transport sinks.

No context management. No formatter logic. No logger construction.
"""
from __future__ import annotations
import logging
import os
import sys
from abc import ABC, abstractmethod
from typing import Optional

from runtime.logging.formatters import StructuredFormatter


class LogSink(ABC):
    """Abstract base for all log output destinations."""

    @abstractmethod
    def get_handler(self) -> logging.Handler:
        ...


class ConsoleSink(LogSink):
    """
    Human-readable text output to stderr.
    Uses StructuredFormatter in text mode (json_mode=False).
    """

    def get_handler(self) -> logging.Handler:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(StructuredFormatter(json_mode=False))
        return handler


class FileSink(LogSink):
    """
    JSON-line output to a log file.
    Uses StructuredFormatter in JSON mode (json_mode=True).
    Rotates files by creating parent directories as needed.
    """

    def __init__(self, path: str) -> None:
        self._path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    def get_handler(self) -> logging.Handler:
        handler = logging.FileHandler(self._path, encoding="utf-8")
        handler.setFormatter(StructuredFormatter(json_mode=True))
        return handler


class NullSink(LogSink):
    """Discards all log output. Useful for tests and benchmarks."""

    def get_handler(self) -> logging.Handler:
        return logging.NullHandler()
