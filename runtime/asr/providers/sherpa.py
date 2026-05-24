"""
AVAListener — Sherpa ONNX ASR Provider (Phase S+, S+3)
=======================================================
Owns the Sherpa ONNX recognizer session and the per-utterance stream
context. Extracted from SherpaStreamer._worker() / _load_recognizer()
in Phase S+3.

Ownership contract
------------------
    SherpaProvider
      - creates and owns the OnlineRecognizer (ONNX session)
      - creates and owns per-utterance OnlineStream
      - exposes accept(sample_rate, chunk), decode(), result()
      - exposes reset(reason), shutdown()
      - is the ONLY module that holds a reference to
        sherpa_onnx.OnlineRecognizer / OnlineStream

Usage
-----
    provider = SherpaProvider(recognizer)
    provider.reset()            # start first stream
    provider.accept(16000, chunk)
    n = provider.decode()
    text = provider.result()
    provider.reset(reason="wake")   # utterance boundary
    provider.shutdown()
"""
from __future__ import annotations

import time
import logging
from typing import Optional

log = logging.getLogger("sherpa_provider")


class SherpaProvider:
    """
    Owns the Sherpa ONNX recognizer and per-utterance decode stream.

    Thread-safety: all methods are called exclusively from the
    AudioWorker thread — no locking needed.
    """

    def __init__(self, recognizer) -> None:
        """
        Parameters
        ----------
        recognizer : sherpa_onnx.OnlineRecognizer
            Created externally by SherpaResources.create_recognizer().
            This class takes ownership — caller must not hold references.
        """
        self._recognizer = recognizer
        self._stream: Optional[object] = None   # sherpa_onnx.OnlineStream

        # Stream lifecycle telemetry
        self._stream_start_time: float = time.monotonic()
        self._last_reset_time:   float = self._stream_start_time
        self._reset_count:       int   = 0
        self._stream_lifetimes:  list[float] = []

        # Generation counter — increments on every reset.
        # Used by the engine for utterance-level duplicate suppression.
        self._generation_id: int = 0

    # ------------------------------------------------------------------
    # Stream lifecycle
    # ------------------------------------------------------------------

    def reset(self, reason: str = "manual") -> None:
        """
        Create a fresh OnlineStream (new utterance boundary).

        Increments generation_id FIRST so any hypothesis emitted after
        this call belongs to the new generation.

        Parameters
        ----------
        reason : str  — label for telemetry ("wake", "inactivity", etc.)
        """
        now = time.monotonic()
        if self._stream is not None:
            lifetime = now - self._stream_start_time
            self._stream_lifetimes.append(lifetime)

        self._generation_id += 1
        self._last_reset_time  = now
        self._stream_start_time = now
        self._reset_count      += 1

        self._stream = self._recognizer.create_stream()
        log.info(
            "[ASR_PROVIDER] stream reset -> generation=%d reason=%s resets=%d",
            self._generation_id, reason, self._reset_count,
        )

    def shutdown(self) -> None:
        """Release the stream context (recognizer itself is long-lived)."""
        self._stream = None
        log.debug("[ASR_PROVIDER] shutdown")

    # ------------------------------------------------------------------
    # Per-frame operations (hot path — called from AudioWorker thread)
    # ------------------------------------------------------------------

    def accept(self, sample_rate: int, samples) -> None:
        """
        Feed a frame of audio to the ASR decode stream.
        Auto-creates a stream if none exists.
        """
        if self._stream is None:
            self.reset(reason="auto-init")
        self._stream.accept_waveform(sample_rate, samples)

    def decode(self) -> int:
        """
        Decode all ready frames.

        Returns
        -------
        int : number of decode cycles performed (0 if stream is None or not ready)
        """
        if self._stream is None:
            return 0
        count = 0
        while self._recognizer.is_ready(self._stream):
            self._recognizer.decode_stream(self._stream)
            count += 1
        return count

    def result(self) -> str:
        """
        Return the current partial hypothesis.

        Returns
        -------
        str : lower-cased, stripped text — empty string if stream is None
        """
        if self._stream is None:
            return ""
        return self._recognizer.get_result(self._stream).strip().lower()

    # ------------------------------------------------------------------
    # Properties used by AudioWorker and watchdog proxies
    # ------------------------------------------------------------------

    @property
    def generation_id(self) -> int:
        return self._generation_id

    @property
    def reset_count(self) -> int:
        return self._reset_count

    @property
    def last_reset_time(self) -> float:
        return self._last_reset_time

    @property
    def stream_start_time(self) -> float:
        return self._stream_start_time

    @property
    def has_stream(self) -> bool:
        return self._stream is not None
