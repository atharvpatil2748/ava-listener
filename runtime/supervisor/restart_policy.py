"""Restart policy utilities for Supervisor.

Provides a small `RestartPolicy` class used by the Supervisor to throttle
rapid restarts and avoid crash loops.
"""

from collections import deque
import time
from typing import Deque


class RestartPolicy:
	def __init__(self, max_restarts: int = 5, window_s: float = 60.0) -> None:
		self.max_restarts = max_restarts
		self.window_s = window_s
		self._timestamps: Deque[float] = deque()

	def record_restart(self) -> None:
		now = time.monotonic()
		self._timestamps.append(now)
		while self._timestamps and (now - self._timestamps[0]) > self.window_s:
			self._timestamps.popleft()

	def can_restart(self) -> bool:
		now = time.monotonic()
		while self._timestamps and (now - self._timestamps[0]) > self.window_s:
			self._timestamps.popleft()
		return len(self._timestamps) < self.max_restarts


__all__ = ["RestartPolicy"]


class RecoveryPolicy:
	"""Escalating recovery policy with discrete steps and exponential backoff.

	Steps (on successive failures):
	  1 -> worker restart
	  2 -> provider reload
	  3 -> runtime restart
	  4 -> degraded mode
	  5 -> fatal failure

	Backoff sequence (ms): 1000, 2000, 4000, 8000, 16000
	"""

	STEPS = [
		"worker_restart",
		"provider_reload",
		"runtime_restart",
		"degraded_mode",
		"fatal",
	]

	BACKOFF_MS = [1000, 2000, 4000, 8000, 16000]

	def __init__(self) -> None:
		self.failures = 0

	def record_failure(self) -> None:
		self.failures = min(self.failures + 1, len(self.STEPS))

	def reset(self) -> None:
		self.failures = 0

	def current_step(self) -> str:
		idx = max(0, min(self.failures - 1, len(self.STEPS) - 1))
		return self.STEPS[idx]

	def next_backoff_ms(self) -> int:
		idx = max(0, min(self.failures - 1, len(self.BACKOFF_MS) - 1))
		return self.BACKOFF_MS[idx]


__all__.append("RecoveryPolicy")
