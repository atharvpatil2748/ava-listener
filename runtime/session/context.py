"""
Session Context (Phase S)
=========================
Tracks in-progress wake candidates and utterance correlation.
"""
import time
from dataclasses import dataclass, field

@dataclass
class CandidateSession:
    phrase: str
    variant: str
    canonical: str
    start_time: float
    last_update: float
    peak_raw: float = 0.0
    peak_smooth: float = 0.0
    transcript_evolution: list[str] = field(default_factory=list)
    stabilization_frames: int = 0
    state: str = "CANDIDATE_STARTED"

    def update(self, text: str, raw_conf: float, smooth_conf: float, frames: int) -> None:
        self.last_update = time.monotonic()
        self.transcript_evolution.append(text)
        self.peak_raw = max(self.peak_raw, raw_conf)
        self.peak_smooth = max(self.peak_smooth, smooth_conf)
        self.stabilization_frames = max(self.stabilization_frames, frames)
        self.state = "CANDIDATE_UPDATED"

    def confirm(self) -> None:
        self.state = "CANDIDATE_CONFIRMED"

    def drop(self) -> None:
        self.state = "CANDIDATE_DROPPED"

    @property
    def duration_ms(self) -> float:
        return (self.last_update - self.start_time) * 1000.0

class SessionContext:
    """Manages active CandidateSession logic."""
    def __init__(self):
        self.current = None

    def add(self, session: CandidateSession) -> None:
        self.current = session

    def clear(self) -> None:
        self.current = None

    def window(self) -> CandidateSession:
        return self.current
