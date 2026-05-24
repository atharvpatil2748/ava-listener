"""
AVAListener — Audio Queue Manager (Phase S, S4)
================================================
Extracted ownership stub for the inter-thread audio queue.

Phase S status: this module declares the ownership boundary and
interface for the audio queue that bridges the sounddevice callback
thread to the ASR worker thread. No logic has been moved from
SherpaStreamer. This is scaffolding only.

Ownership contract (future state)
----------------------------------
    QueueManager
      - creates and owns queue.Queue instance
      - exposes put_nowait() for the audio callback (hot path)
      - exposes get() for the worker thread
      - owns queue depth warnings and diagnostics

Current state
-------------
    SherpaStreamer owns queue.Queue directly as self._audio_queue.
    QueueManager stubs the future extraction target.
"""
from __future__ import annotations

import queue
from typing import Optional

import numpy as np


class QueueManager:
    """
    Scaffolding ownership stub for the inter-thread audio queue.

    Phase S: not yet active. SherpaStreamer._audio_queue is still the
    live queue. This class exists to:
      1. Declare the extraction target.
      2. Establish the public interface (enqueue / dequeue / depth).
      3. Co-locate queue diagnostic logic for future consolidation.
    """

    def __init__(self, maxsize: int = 0, warn_threshold: int = 50) -> None:
        self._queue: queue.Queue = queue.Queue(maxsize=maxsize)
        self._warn_threshold = warn_threshold
        self._warn_logged = False
        self._enqueue_count: int = 0

    # ------------------------------------------------------------------
    # Producer side (audio callback — must be O(1))
    # ------------------------------------------------------------------

    def enqueue(self, chunk: np.ndarray) -> None:
        """
        Enqueue an audio chunk. Must return in << 1ms.
        Called from the sounddevice audio callback thread.
        """
        self._queue.put_nowait(chunk)
        self._enqueue_count += 1

        depth = self._queue.qsize()
        if depth > self._warn_threshold and not self._warn_logged:
            self._warn_logged = True
            # Caller is responsible for logging (cannot import logger in hot path)

    # ------------------------------------------------------------------
    # Consumer side (ASR worker thread)
    # ------------------------------------------------------------------

    def dequeue(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        """
        Block until a chunk is available or timeout expires.
        Returns None on timeout (queue.Empty).
        """
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @property
    def depth(self) -> int:
        return self._queue.qsize()

    @property
    def enqueue_count(self) -> int:
        return self._enqueue_count

    def reset_warn(self) -> None:
        """Reset the queue-depth warning latch (call periodically)."""
        self._warn_logged = False
