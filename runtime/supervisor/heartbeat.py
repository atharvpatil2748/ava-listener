"""Heartbeat helpers for Supervisor/Worker coordination.

Small helpers to work with the JSON heartbeat contract emitted by the
worker process (an `event: "heartbeat"` object emitted on stdout).
"""

from typing import Any


def is_heartbeat(obj: Any) -> bool:
	try:
		return isinstance(obj, dict) and obj.get("event") == "heartbeat"
	except Exception:
		return False


__all__ = ["is_heartbeat"]
