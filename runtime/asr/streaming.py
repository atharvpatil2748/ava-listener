"""
AVAListener — SherpaStreamer Coordinator (Phase S+)
====================================================
Coordinator only. Wires AudioResources, QueueManager, AudioWorker,
SherpaProvider, and HybridVAD together. Contains NO pipeline logic.

Data flow
---------
  sounddevice callback  ->  QueueManager.enqueue(chunk)
                                   |
                            AudioWorker._run()
                                   |
                     VAD (HybridVAD.process_chunk)
                                   |
                     ASR (SherpaProvider.accept/decode/result)
                                   |
                          on_hypothesis(text, stab, peak, gen_id, corr_id)
                                   |
                            WakeEngine._on_hypothesis()

Callback signature (on_hypothesis)
-----------------------------------
  text          — partial hypothesis (lower-cased, stripped)
  stability     — consecutive unchanged frames (0 = just changed)
  peak          — longest hypothesis since last stream reset
  generation_id — increments on every stream reset
  correlation_id — per-utterance UUID

Watchdog surface (preserved for backward compatibility)
-------------------------------------------------------
  _audio_queue  — proxied to QueueManager (qsize())
  _worker_thread / _worker_heartbeat / _processing_active — proxied to AudioWorker
  avg_worker_idle_ms / avg_worker_processing_ms — proxied to AudioWorker
  _vad          — direct attribute (HybridVAD)
  _asr_fsm / _audio_fsm — direct SubsystemLifecycle attributes
  _reset_stream(reason) — coordinator method, delegates to provider + worker
"""

import time

from config.settings import (
    SAMPLE_RATE, BLOCK_SIZE, NUM_THREADS, MODELS_DIR,
    ENDPOINT_RULE1_SILENCE, ENDPOINT_RULE2_SILENCE,
    ENDPOINT_RULE3_UTTERANCE,
    AUDIO_QUEUE_MAX,
)
from runtime.kernel.lifecycle import SubsystemLifecycle, SubsystemState
from audio.vad import HybridVAD
from utils.logger import get_logger

from runtime.resources.audio_resources import AudioResources
from runtime.resources.asr_resources   import SherpaResources
from runtime.audio.queue_manager       import QueueManager
from runtime.audio.worker              import AudioWorker
from runtime.asr.providers.sherpa      import SherpaProvider

log = get_logger("sherpa_stream")


class SherpaStreamer:
    """
    Microphone -> queue -> ASR worker -> on_hypothesis callback.

    Coordinator only: owns no pipeline logic. Delegates to:
      - QueueManager   (audio queue)
      - AudioWorker    (consumer thread + VAD/ASR pipeline)
      - SherpaProvider (ONNX session + stream lifecycle)
      - HybridVAD      (two-stage voice activity detection)
    """

    def __init__(self) -> None:
        # ── Subsystem FSMs ────────────────────────────────────────────────
        self._asr_fsm   = SubsystemLifecycle("ASR")
        self._audio_fsm = SubsystemLifecycle("Audio")

        # ── ASR model + provider ──────────────────────────────────────────
        recognizer       = self._load_recognizer()
        self._provider   = SherpaProvider(recognizer)

        # ── VAD ───────────────────────────────────────────────────────────
        self._vad = HybridVAD()

        # ── Audio queue ───────────────────────────────────────────────────
        self._queue_manager = QueueManager(warn_threshold=AUDIO_QUEUE_MAX)

        # ── Stop event (shared between streamer and worker) ───────────────
        import threading
        self._stop_event = threading.Event()

        # ── Worker ────────────────────────────────────────────────────────
        self._audio_worker = AudioWorker(
            queue_manager   = self._queue_manager,
            sherpa_provider = self._provider,
            vad             = self._vad,
            stop_event      = self._stop_event,
            asr_fsm         = self._asr_fsm,
        )

        # ── Diagnostics ───────────────────────────────────────────────────
        self._callback_count: int = 0

    # ── Watchdog compatibility proxies ─────────────────────────────────────
    # RuntimeWatchdog accesses these via getattr(self._streamer, ...).
    # Proxy to the inner objects so callers need no changes.

    @property
    def _audio_queue(self):
        """Proxy: allows watchdog._check_queue() to call .qsize()."""
        return self._queue_manager._queue

    @property
    def _worker_thread(self):
        return self._audio_worker._thread

    @property
    def _worker_heartbeat(self) -> float:
        return self._audio_worker.heartbeat

    @property
    def _processing_active(self) -> bool:
        return self._audio_worker.processing_active

    @property
    def avg_worker_idle_ms(self) -> float:
        return self._audio_worker.avg_idle_ms

    @property
    def avg_worker_processing_ms(self) -> float:
        return self._audio_worker.avg_processing_ms

    # ── Public API ─────────────────────────────────────────────────────────

    def start(self, on_hypothesis) -> None:
        """
        Open microphone, start ASR worker thread, block until stop() is called.
        """
        self._stop_event.clear()

        # Initialize Sherpa stream (generation 0)
        self._provider.reset(reason="start")

        # Transition ASR FSM to READY before starting the worker thread
        self._asr_fsm.transition(SubsystemState.INITIALIZING)
        self._asr_fsm.transition(SubsystemState.READY)

        # Start worker thread
        self._audio_worker.start(on_hypothesis, name="asr-worker")
        log.debug("ASR worker thread started")

        # Open microphone
        self._audio_fsm.transition(SubsystemState.INITIALIZING)
        self._audio_fsm.transition(SubsystemState.READY)

        audio_stream = AudioResources.create_input_stream(
            channels    = 1,
            samplerate  = SAMPLE_RATE,
            dtype       = "float32",
            blocksize   = BLOCK_SIZE,
            callback    = self._audio_callback,
        )
        with audio_stream:
            self._audio_fsm.transition(SubsystemState.ACTIVE)
            log.info(
                "\U0001f3a4 Mic open | BLOCK=%d (%dms) | RATE=%d",
                BLOCK_SIZE, BLOCK_SIZE * 1000 // SAMPLE_RATE, SAMPLE_RATE,
            )
            while not self._stop_event.is_set():
                time.sleep(0.2)

        self._stop_event.set()
        self._audio_worker.stop()

    def stop(self) -> None:
        """Signal the stream to stop. start() will return shortly after."""
        self._stop_event.set()
        self._asr_fsm.shutdown()
        self._audio_fsm.shutdown()

    def export_debug_state(self) -> dict:
        """
        Export a safe, immutable snapshot of ASR/Audio streamer state.
        CrashSnapshot MUST consume this interface only.
        """
        return {
            "asr_fsm_state":    self._asr_fsm.state.value,
            "audio_fsm_state":  self._audio_fsm.state.value,
            "audio_queue_depth": self._queue_manager.depth,
            "generation_id":    self._provider.generation_id,
            "correlation_id":   self._audio_worker._correlation_id,
            "last_hypothesis":  self._audio_worker._last_hypothesis,
            "stable_frames":    self._audio_worker._stable_frames,
            "reset_count":      self._provider.reset_count,
            "is_speaking":      self._audio_worker._is_speaking,
            "processing_active": self._audio_worker.processing_active,
            "vad_state": (
                self._vad.export_debug_state()
                if hasattr(self._vad, "export_debug_state") else {}
            ),
        }

    # ── Stream reset (called by orchestrator and watchdog) ─────────────────

    def _reset_stream(self, reason: str = "manual") -> None:
        """
        Reset ASR stream after long silence, wake event, or recovery.
        Delegates to SherpaProvider (stream lifecycle) and AudioWorker
        (speech state). Preserves FSM recovery transitions.
        """
        from runtime.kernel.lifecycle import SubsystemState

        # Provider resets the ONNX stream and increments generation_id
        self._provider.reset(reason=reason)

        # VAD state reset
        self._vad.reset_state()

        # FSM recovery transitions (non-silence reasons only)
        if reason != "silence":
            self._asr_fsm.recover(reason)
            if hasattr(self._vad, "_vad_fsm"):
                self._vad._vad_fsm.recover(reason)

        # Worker speech-state reset
        self._audio_worker.reset_state(reason=reason)

        log.info(
            "\U0001f504 ASR stream reset -> generation %d reason=%s resets=%d",
            self._provider.generation_id,
            reason,
            self._provider.reset_count,
        )

        if reason != "silence":
            if self._asr_fsm.state == SubsystemState.RECOVERING:
                self._asr_fsm.transition(SubsystemState.ACTIVE)
            if hasattr(self._vad, "_vad_fsm") and \
               self._vad._vad_fsm.state == SubsystemState.RECOVERING:
                self._vad._vad_fsm.transition(SubsystemState.ACTIVE)

    # ── Audio callback (runs in sounddevice audio thread) ──────────────────

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        """
        Called by sounddevice on every audio block.
        CRITICAL: must return in << 1ms. Only enqueues the chunk.
        """
        if status:
            log.warning("sounddevice status: %s", status)

        chunk = indata[:, 0].copy()
        self._queue_manager.enqueue(chunk)
        self._callback_count += 1

        if self._queue_manager.depth > AUDIO_QUEUE_MAX and not self._queue_manager._warn_logged:
            self._queue_manager._warn_logged = True
            log.warning(
                "Audio queue depth %d > %d — ASR worker falling behind.",
                self._queue_manager.depth, AUDIO_QUEUE_MAX,
            )

    # ── Model loading ──────────────────────────────────────────────────────

    @staticmethod
    def _load_recognizer():
        log.info("Loading Sherpa ONNX model from %s", MODELS_DIR)
        recognizer = SherpaResources.create_recognizer(
            models_dir  = MODELS_DIR,
            num_threads = NUM_THREADS,
            sample_rate = SAMPLE_RATE,
            rule1       = ENDPOINT_RULE1_SILENCE,
            rule2       = ENDPOINT_RULE2_SILENCE,
            rule3       = ENDPOINT_RULE3_UTTERANCE,
        )
        log.info("Model loaded \u2713")
        return recognizer