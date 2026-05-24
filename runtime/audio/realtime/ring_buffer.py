"""
AVAListener — Hypothesis Buffer
Rolling time-window buffer. Stores (timestamp, text, stability) tuples.
Entries older than WINDOW_SECONDS are automatically purged.

Key behaviour: growing-prefix deduplication.
  Sherpa streaming emits incremental partials: "a" → "as" → "assistant".
  Each extends the previous. push() replaces the last entry in-place when
  the new text is a prefix extension of it, preventing fragment pollution.
"""
import time
from collections import deque
from typing import List, Tuple
from config.settings import WINDOW_SECONDS


class HypothesisBuffer:
    """
    Thread-safe rolling buffer of ASR hypotheses.

    Each entry: (monotonic_timestamp, text, stability_frames)
    stability_frames: how many consecutive ASR callbacks returned identical text.
                      Higher = more reliable hypothesis.
    """

    def __init__(self):
        self._buf: deque = deque()

    def push(self, text: str, stability: int = 0) -> None:
        """
        Add a new hypothesis, purging stale entries.

        Deduplication: if the new text is a prefix extension of the last entry
        (i.e., one starts with the other — typical of Sherpa incremental output),
        replace the last entry in-place rather than appending.  This prevents
        the window from filling with growing-prefix fragments like:
          "a", "as", "assist", "assistant"
        and keeps the window clean for anchor gate evaluation.
        """
        if self._buf:
            _, last_text, _ = self._buf[-1]
            if last_text and (
                text.startswith(last_text) or last_text.startswith(text)
            ):
                # Replace in-place — update timestamp and stability
                self._buf[-1] = (time.monotonic(), text, stability)
                self._purge()
                return
        self._buf.append((time.monotonic(), text, stability))
        self._purge()

    def get_window(self) -> List[Tuple[str, int]]:
        """Return list of (text, stability) for all entries still in window."""
        self._purge()
        return [(text, stab) for _, text, stab in self._buf]

    def clear(self) -> None:
        """Clear all entries (called after a successful trigger)."""
        self._buf.clear()

    def __len__(self) -> int:
        self._purge()
        return len(self._buf)

    def _purge(self) -> None:
        cutoff = time.monotonic() - WINDOW_SECONDS
        while self._buf and self._buf[0][0] < cutoff:
            self._buf.popleft()
