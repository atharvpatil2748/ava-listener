"""IPC message definitions for Supervisor <-> Worker communication."""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class IPCMessage:
    type: str
    payload: Dict[str, Any]


# Standard message type constants
START = "START"
STOP = "STOP"
HEALTH = "HEALTH"
WAKE = "WAKE"
ERROR = "ERROR"
STATUS = "STATUS"
HEARTBEAT = "HEARTBEAT"
DIAGNOSTICS = "DIAGNOSTICS"
SHUTDOWN = "SHUTDOWN"


__all__ = [
    "IPCMessage",
    "START",
    "STOP",
    "HEALTH",
    "WAKE",
    "ERROR",
    "STATUS",
    "HEARTBEAT",
    "DIAGNOSTICS",
    "SHUTDOWN",
]
