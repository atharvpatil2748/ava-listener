"""
AVAListener — Linear Pipeline Skeleton (Phase S, S3)
=====================================================
Scaffolding only. This module defines the LinearPipeline data contract
and wires AudioFrame → VAD → ASR → callback in a formal pipeline shape.

Current implementation: internally delegates to the existing SherpaStreamer
logic. NO logic has been moved — this is scaffolding and structural
ownership declaration only.

Future phases will incrementally replace the delegation with direct
provider calls once VAD and ASR providers are fully extracted.

Pipeline contract
-----------------
    AudioFrame
       → VAD stage  (gate — decides whether frame has speech)
       → ASR stage  (decode — produces hypothesis text)
       → callback   (on_hypothesis(text, stability, peak, generation_id, correlation_id))

Matcher integration is intentionally excluded from this pipeline.
The orchestrator (WakeEngine) remains the sole integration point
for matcher logic, as required by the architecture contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional
import numpy as np


# ---------------------------------------------------------------------------
# AudioFrame — the unit flowing through the pipeline
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AudioFrame:
    """
    Immutable audio chunk travelling through the linear pipeline.

    Attributes
    ----------
    samples     : float32 numpy array, shape (BLOCK_SIZE,), mono
    sample_rate : audio sample rate in Hz (e.g. 16000)
    timestamp   : monotonic time at capture, seconds
    """
    samples: np.ndarray
    sample_rate: int
    timestamp: float


# ---------------------------------------------------------------------------
# HypothesisResult — produced by the ASR stage
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class HypothesisResult:
    """
    Minimal ASR output produced per processed frame.

    Attributes
    ----------
    text          : current partial hypothesis (lower-cased, stripped)
    stability     : consecutive frames this text was unchanged
    peak          : longest hypothesis since last stream reset
    generation_id : utterance-level generation counter
    correlation_id: per-utterance UUID for logging correlation
    """
    text: str
    stability: int
    peak: str
    generation_id: int
    correlation_id: str


# ---------------------------------------------------------------------------
# LinearPipeline — scaffolding coordinator
# ---------------------------------------------------------------------------

class LinearPipeline:
    """
    Scaffolding coordinator for the AudioFrame → VAD → ASR → callback path.

    Phase S status: process() delegates entirely to the caller-supplied
    streamer instance (SherpaStreamer). No logic has been relocated.
    The class exists to:
      1. Establish the public process(frame: AudioFrame) interface.
      2. Declare ownership intent for the pipeline stages.
      3. Provide a stable import surface for future phase refactoring.

    Matcher integration is NOT included here. The orchestrator remains
    the sole integration point for wake detection logic.
    """

    def __init__(self, streamer) -> None:
        """
        Parameters
        ----------
        streamer : SherpaStreamer
            The current monolithic streamer. Used for delegation only.
            Will be replaced by discrete VAD/ASR provider instances
            in future decomposition phases.
        """
        self._streamer = streamer
        # Future: self._vad_provider = ...
        # Future: self._asr_provider = ...

    def process(self, frame: AudioFrame, callback: Callable) -> Optional[HypothesisResult]:
        """
        Process a single AudioFrame through the pipeline.

        Currently a no-op delegation stub. The actual VAD + ASR processing
        still occurs inside SherpaStreamer._worker(). This method exists
        to anchor the future refactoring target.

        Parameters
        ----------
        frame    : AudioFrame — the audio chunk to process
        callback : on_hypothesis callable — called with HypothesisResult if
                   a hypothesis is produced and VAD passes

        Returns
        -------
        HypothesisResult if a hypothesis was produced, else None.
        (Phase S: always returns None — processing is still in the worker thread.)
        """
        # Phase S stub: no delegation needed.
        # The SherpaStreamer._worker() loop calls on_hypothesis directly.
        # Future phases will wire:
        #   vad_result = self._vad_provider.process(frame)
        #   if vad_result.is_speech:
        #       hyp = self._asr_provider.decode(frame)
        #       callback(hyp)
        #       return hyp
        return None

    # ------------------------------------------------------------------
    # Stage stubs — to be filled by future decomposition phases
    # ------------------------------------------------------------------

    def _run_vad(self, frame: AudioFrame) -> bool:
        """
        VAD stage stub. Returns True if the frame contains speech.
        Phase S: not called. Future: delegates to VADProvider.
        """
        raise NotImplementedError("VAD stage not yet extracted from SherpaStreamer")

    def _run_asr(self, frame: AudioFrame) -> Optional[str]:
        """
        ASR decode stage stub. Returns hypothesis text or None.
        Phase S: not called. Future: delegates to ASRProvider.
        """
        raise NotImplementedError("ASR stage not yet extracted from SherpaStreamer")
