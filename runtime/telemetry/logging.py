"""
AVAListener — Centralized Logger Config
CRITICAL: All output goes to stderr. stdout is owned exclusively by stdout_bridge.py.
"""
import logging
import sys

import json
from datetime import datetime

TRACE = 5
LEVEL_MAP = {
    "silent": logging.CRITICAL + 10,
    "error": logging.ERROR,
    "warn": logging.WARNING,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
    "trace": TRACE,
}

logging.addLevelName(TRACE, "TRACE")

# Global Subsystem flags
DEBUG_VAD = False
DEBUG_ONNX = False
DEBUG_SHERPA = False
DEBUG_WAKE = False
DEBUG_TRANSPORT = False
DEBUG_TELEMETRY = False

DEBUG_TRANSCRIPTS = False
DEBUG_TRANSCRIPT_PARTIAL = False
DEBUG_TRANSCRIPT_FINAL = False

_ROOT_LEVEL = logging.INFO
_loggers = []

class JsonFormatter(logging.Formatter):
    def format(self, record):
        msg = record.getMessage()
        if msg.startswith("{") and msg.endswith("}"):
            # Assume it's already JSON from telemetry emit_... functions
            return msg
        return json.dumps({
            "level": record.levelname,
            "event": "log",
            "message": msg,
            "ts": record.created
        })

_pretty_formatter = logging.Formatter("%(asctime)s [%(levelname)-7s] %(name)s: %(message)s", datefmt="%H:%M:%S")
_json_formatter = JsonFormatter()

_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(_pretty_formatter)

_file_handler = None

def _trace(self, message, *args, **kwargs):
    if self.isEnabledFor(TRACE):
        self._log(TRACE, message, args, **kwargs)

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(_handler)
        logger.setLevel(_ROOT_LEVEL)
        _loggers.append(logger)
    if not hasattr(logger, "trace"):
        setattr(logger, "trace", _trace.__get__(logger, logging.Logger))
    return logger

def set_log_level(level_name: str) -> None:
    global _ROOT_LEVEL
    _ROOT_LEVEL = LEVEL_MAP.get(level_name.lower(), logging.INFO)
    for logger in _loggers:
        logger.setLevel(_ROOT_LEVEL)

def set_log_format(fmt: str) -> None:
    if fmt == "json":
        _handler.setFormatter(_json_formatter)
        if _file_handler:
            _file_handler.setFormatter(_json_formatter)
    else:
        _handler.setFormatter(_pretty_formatter)
        if _file_handler:
            _file_handler.setFormatter(_pretty_formatter)

def enable_file_logging() -> None:
    global _file_handler
    if _file_handler:
        return
    import os
    from logging.handlers import RotatingFileHandler
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "runtime", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "ava_listener.log")
    
    _file_handler = RotatingFileHandler(
        log_path, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
    )
    # Inherit current formatter
    _file_handler.setFormatter(_handler.formatter)
    
    for logger in _loggers:
        logger.addHandler(_file_handler)

def enable_trace() -> None:
    set_log_level("trace")
    global DEBUG_VAD, DEBUG_WAKE, DEBUG_TRANSCRIPT_PARTIAL, DEBUG_TRANSCRIPT_FINAL, DEBUG_ONNX, DEBUG_SHERPA, DEBUG_TRANSPORT, DEBUG_TELEMETRY, DEBUG_TRANSCRIPTS
    DEBUG_VAD = True
    DEBUG_ONNX = True
    DEBUG_SHERPA = True
    DEBUG_WAKE = True
    DEBUG_TRANSPORT = True
    DEBUG_TELEMETRY = True
    DEBUG_TRANSCRIPTS = True
    DEBUG_TRANSCRIPT_PARTIAL = True
    DEBUG_TRANSCRIPT_FINAL = True

def enable_subsystem_debug(subsystem: str) -> None:
    global DEBUG_VAD, DEBUG_WAKE, DEBUG_TRANSCRIPT_PARTIAL, DEBUG_TRANSCRIPT_FINAL, DEBUG_ONNX, DEBUG_SHERPA, DEBUG_TRANSPORT, DEBUG_TELEMETRY
        
    if subsystem == "vad":
        DEBUG_VAD = True
        logging.getLogger("vad").setLevel(logging.DEBUG)
    elif subsystem == "asr":
        DEBUG_SHERPA = True
        DEBUG_TRANSCRIPT_FINAL = True
        DEBUG_TRANSCRIPT_PARTIAL = True
        logging.getLogger("sherpa_stream").setLevel(logging.DEBUG)
    elif subsystem == "matcher":
        DEBUG_WAKE = True
        logging.getLogger("engine").setLevel(logging.DEBUG)
    elif subsystem == "pipeline":
        DEBUG_VAD = True
        DEBUG_WAKE = True
        DEBUG_TRANSCRIPT_FINAL = True
        DEBUG_TRANSCRIPT_PARTIAL = True
        logging.getLogger("vad").setLevel(logging.DEBUG)
        logging.getLogger("sherpa_stream").setLevel(logging.DEBUG)
        logging.getLogger("engine").setLevel(logging.DEBUG)

def disable_subsystem_debug(subsystem: str) -> None:
    global DEBUG_VAD, DEBUG_WAKE, DEBUG_TRANSCRIPT_PARTIAL, DEBUG_TRANSCRIPT_FINAL, DEBUG_ONNX, DEBUG_SHERPA, DEBUG_TRANSPORT, DEBUG_TELEMETRY
    if subsystem == "vad":
        DEBUG_VAD = False
    elif subsystem == "asr":
        DEBUG_SHERPA = False
        DEBUG_TRANSCRIPT_FINAL = False
        DEBUG_TRANSCRIPT_PARTIAL = False
    elif subsystem == "matcher":
        DEBUG_WAKE = False
    elif subsystem == "pipeline":
        DEBUG_VAD = False
        DEBUG_WAKE = False
        DEBUG_TRANSCRIPT_FINAL = False
        DEBUG_TRANSCRIPT_PARTIAL = False

def disable_trace() -> None:
    set_log_level("info")
    global DEBUG_VAD, DEBUG_WAKE, DEBUG_TRANSCRIPT_PARTIAL, DEBUG_TRANSCRIPT_FINAL, DEBUG_ONNX, DEBUG_SHERPA, DEBUG_TRANSPORT, DEBUG_TELEMETRY, DEBUG_TRANSCRIPTS
    DEBUG_VAD = False
    DEBUG_ONNX = False
    DEBUG_SHERPA = False
    DEBUG_WAKE = False
    DEBUG_TRANSPORT = False
    DEBUG_TELEMETRY = False
    DEBUG_TRANSCRIPTS = False
    DEBUG_TRANSCRIPT_PARTIAL = False
    DEBUG_TRANSCRIPT_FINAL = False
