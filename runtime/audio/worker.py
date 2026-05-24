"""
AVAListener — Audio Worker (Phase S+, S+2)
==========================================
Owns the ASR consumer thread: reads audio frames from QueueManager,
drives the VAD + ASR pipeline, and delivers hypotheses via callback.

Extracted from SherpaStreamer._worker() in Phase S+2.

Ownership contract
------------------
    AudioWorker
      - owns all hysteresis / speech-state tracking
      - owns silence timeout + stream-reset coordination
      - owns peak / stability tracking
      - drives SherpaProvider.accept() / decode() / result()
      - drives VAD (HybridVAD.process_chunk())
      - calls on_hypothesis() to deliver results upstream
      - owns generation_id and correlation_id

Thread model
------------
    The AudioWorker spawns exactly one daemon thread (the consumer).
    The run() method IS that thread target — not called from outside.
    External interface: start() / stop() / reset_state().

Watchdog surface
----------------
    The following properties are read by RuntimeWatchdog:
      .heartbeat         — monotonic timestamp of last queue dequeue
      .processing_active — True while a chunk is being processed
      .avg_idle_ms       — rolling average idle time per chunk (ms)
      .avg_processing_ms — rolling average processing time per chunk (ms)
      ._thread           — the underlying Thread (alive check)
"""
from __future__ import annotations

import time
import threading
import uuid
from typing import Callable, Optional

import numpy as np

from config.settings import (
    SAMPLE_RATE, BLOCK_SIZE,
    SILENCE_RESET_FRAMES, TRAILING_PAD_FRAMES,
    WORKER_QUEUE_TIMEOUT, AUDIO_QUEUE_MAX,
    MIN_SPEECH_FRAMES, MIN_SILENCE_FRAMES,
    MIN_VALID_UTTERANCE_MS,
    RESET_COOLDOWN_SECONDS,
)
from utils.logger import (
    get_logger, DEBUG_VAD, DEBUG_SHERPA,
    DEBUG_TRANSCRIPT_PARTIAL, DEBUG_TRANSCRIPT_FINAL,
)

log = get_logger("audio_worker")


class AudioWorker:
    """
    Consumer thread: reads audio from QueueManager, drives VAD + ASR,
    calls on_hypothesis(text, stability, peak, generation_id, correlation_id).

    Key invariants (preserved from original SherpaStreamer._worker()):
      - Every chunk from the queue reaches accept_waveform() — no drops.
      - VAD only gates on_hypothesis() invocation, not ASR feeding.
      - Stream resets only after SILENCE_RESET_FRAMES consecutive silent chunks.
      - generation_id increments on EVERY stream reset.
    """

    def __init__(
        self,
        queue_manager,          # QueueManager
        sherpa_provider,        # SherpaProvider
        vad,                    # HybridVAD
        stop_event: threading.Event,
        asr_fsm,                # SubsystemLifecycle — for FSM transitions on reset
    ) -> None:
        self._qmgr       = queue_manager
        self._provider   = sherpa_provider
        self._vad        = vad
        self._stop_event = stop_event
        self._asr_fsm    = asr_fsm

        # Thread handle
        self._thread: Optional[threading.Thread] = None

        # ── Speech state (hysteresis) ──────────────────────────────────────
        self._is_speaking:          bool  = False
        self._consecutive_speech:   int   = 0
        self._consecutive_silence:  int   = 0
        self._has_spoken_in_generation: bool = False
        self._utterance_start_time: float = time.monotonic()
        self._last_valid_speech_duration: float = 0.0

        # ── ASR frame state ────────────────────────────────────────────────
        self._trailing_pad:   int   = 0
        self._last_hypothesis: str  = ""
        self._stable_frames:   int  = 0
        self._peak_hypothesis: str  = ""
        self._peak_length:     int  = 0

        # ── Pre-roll buffer (Phase 1) ─────────────────────────────────────
        import collections
        self._pre_buffer = collections.deque(maxlen=5) # 500ms

        # ── Correlation tracking ──────────────────────────────────────────
        self._correlation_id: str = "init-0"

        # ── Watchdog surface ──────────────────────────────────────────────
        self._heartbeat:          float = time.monotonic()
        self._processing_active:  bool  = False

        # ── Performance telemetry ─────────────────────────────────────────
        self._total_idle_time_s:       float = 0.0
        self._idle_count:              int   = 0
        self._total_processing_time_s: float = 0.0
        self._processing_count:        int   = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, on_hypothesis: Callable, name: str = "asr-worker") -> threading.Thread:
        """
        Spawn the consumer thread. Returns the Thread so the caller can
        join it on shutdown.
        """
        t = threading.Thread(
            target=self._run,
            args=(on_hypothesis,),
            daemon=True,
            name=name,
        )
        self._thread = t
        t.start()
        log.debug("AudioWorker thread started")
        return t

    def stop(self) -> None:
        """Signal the worker to stop (stop_event is set by the coordinator)."""
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                log.warning("AudioWorker did not exit cleanly within 5s")

    def reset_state(self, reason: str = "manual") -> None:
        """
        Reset all speech-state and ASR-frame state to match a new stream
        generation. Called by SherpaStreamer._reset_stream() which coordinates
        the provider.reset() call first, then calls this.
        """
        now = time.monotonic()
        self._is_speaking           = False
        self._consecutive_speech    = 0
        self._consecutive_silence   = 0
        self._has_spoken_in_generation = False
        self._utterance_start_time  = now
        self._trailing_pad          = 0
        self._last_hypothesis       = ""
        self._stable_frames         = 0
        self._peak_hypothesis       = ""
        self._peak_length           = 0

    # ------------------------------------------------------------------
    # Watchdog surface (read by RuntimeWatchdog via getattr on streamer)
    # ------------------------------------------------------------------

    @property
    def heartbeat(self) -> float:
        return self._heartbeat

    @property
    def processing_active(self) -> bool:
        return self._processing_active

    @property
    def avg_idle_ms(self) -> float:
        if self._idle_count == 0:
            return 0.0
        return (self._total_idle_time_s / self._idle_count) * 1000.0

    @property
    def avg_processing_ms(self) -> float:
        if self._processing_count == 0:
            return 0.0
        return (self._total_processing_time_s / self._processing_count) * 1000.0

    # ------------------------------------------------------------------
    # Internal: worker loop (runs in dedicated thread)
    # ------------------------------------------------------------------

    def _run(self, on_hypothesis: Callable) -> None:
        """
        Consumer thread body. Mirrors the original SherpaStreamer._worker()
        exactly — no behavior changes.

        Key invariants preserved:
          - Every chunk reaches accept_waveform() (no drops).
          - VAD only gates on_hypothesis(), not ASR feeding.
          - Stream resets after SILENCE_RESET_FRAMES consecutive silent chunks.
        """
        from runtime.kernel.lifecycle import SubsystemState

        log.debug("AudioWorker: entering processing loop")
        log.info("[ASR_FSM] entering worker, state=%s", self._asr_fsm.state.value)
        self._processing_active = False

        if self._asr_fsm.state == SubsystemState.READY:
            self._asr_fsm.transition(SubsystemState.ACTIVE)
        elif self._asr_fsm.state == SubsystemState.ACTIVE:
            pass
        else:
            raise RuntimeError(
                f"AudioWorker started in invalid FSM state: {self._asr_fsm.state.value}. "
                f"Expected READY or ACTIVE."
            )
        log.info("[ASR_FSM] worker entered ACTIVE state")

        last_qsize_log = time.monotonic()
        chunk_count    = 0
        vad_latency    = 0.0

        while not self._stop_event.is_set():
            # ── Drain queue ──────────────────────────────────────────────
            t_idle_start = time.perf_counter()
            self._processing_active = False
            self._heartbeat = time.monotonic()

            chunk = self._qmgr.dequeue(timeout=WORKER_QUEUE_TIMEOUT)

            idle_duration = time.perf_counter() - t_idle_start
            self._total_idle_time_s += idle_duration
            self._idle_count        += 1
            self._heartbeat          = time.monotonic()

            if chunk is None:
                # queue.Empty — normal during silence
                continue

            self._processing_active = True
            self._heartbeat         = time.monotonic()
            t_proc_start            = time.perf_counter()
            chunk_count            += 1

            # ── VAD decision (does NOT gate audio delivery immediately) ──
            t0 = time.perf_counter()
            vad_res     = self._vad.process_chunk(chunk)
            vad_latency = (time.perf_counter() - t0) * 1000
            chunk_speech = vad_res["pass"]

            if DEBUG_VAD and vad_res["rms"] >= 0.0001:
                log.debug(
                    "[VAD] webrtc=%s silero_prob=%.2f silero_pass=%s rms=%.4f peak=%.3f pass=%s",
                    vad_res["webrtc"], vad_res["silero_prob"], vad_res["silero_pass"],
                    vad_res["rms"], vad_res["peak"], chunk_speech,
                )

            # ── Speech state hysteresis ──────────────────────────────────

            if chunk_speech:
                self._consecutive_speech   += 1
                self._consecutive_silence   = 0
                if self._consecutive_speech >= MIN_SPEECH_FRAMES and not self._is_speaking:
                    self._is_speaking       = True
                    self._utterance_start_time = time.monotonic()
                    self._has_spoken_in_generation = True
                    self._correlation_id    = str(uuid.uuid4())
                    log.info("\U0001f3a4 Speech started")
                    
                    # Flush pre-buffer to capture leading phonemes
                    flushed = 0
                    for old_chunk in self._pre_buffer:
                        self._provider.accept(SAMPLE_RATE, old_chunk)
                        flushed += 1
                    self._pre_buffer.clear()
                    log.trace("[PREBUFFER] flushed %d frames", flushed)
            else:
                self._consecutive_silence  += 1
                self._consecutive_speech    = 0
                if self._consecutive_silence >= MIN_SILENCE_FRAMES and self._is_speaking:
                    self._is_speaking       = False
                    duration_ms = (
                        (time.monotonic() - self._utterance_start_time) * 1000.0
                        if hasattr(self, "_utterance_start_time") else 0.0
                    )
                    if duration_ms < MIN_VALID_UTTERANCE_MS:
                        log.info(
                            "\U0001f515 Ignored ultra-short burst: %.0fms (noise threshold)",
                            duration_ms,
                        )
                    else:
                        log.info("\U0001f507 Speech ended")
                    self._last_valid_speech_duration = duration_ms

            effective_speech = self._is_speaking
            if not effective_speech:
                self._pre_buffer.append(chunk)

            # ── Silence timeout → stream reset ───────────────────────────
            partial_tokens  = ["wake", "listen", "hey", "ar", "arv", "arbe", "wake up"]
            is_partial      = any(tok in self._last_hypothesis for tok in partial_tokens)
            silence_timeout = 25 if is_partial else 18

            if self._consecutive_silence >= silence_timeout:
                now = time.monotonic()
                if (
                    self._consecutive_silence == silence_timeout
                    and self._has_spoken_in_generation
                ):
                    # Delegate reset to provider (owns stream lifecycle)
                    if now - self._provider.last_reset_time >= RESET_COOLDOWN_SECONDS:
                        lifetime = now - self._provider.stream_start_time
                        log.debug(
                            "[VAD] non_speech_duration > %.1fs -> forced stream reset",
                            silence_timeout * (BLOCK_SIZE / SAMPLE_RATE),
                        )
                        self._do_stream_reset(reason="inactivity")

                self._total_processing_time_s += time.perf_counter() - t_proc_start
                self._processing_count        += 1
                continue

            # ── Feed Sherpa — only during speech or trailing pad ─────────
            if effective_speech:
                self._provider.accept(SAMPLE_RATE, chunk)
                self._trailing_pad = 0
            else:
                if self._trailing_pad < TRAILING_PAD_FRAMES:
                    self._provider.accept(SAMPLE_RATE, chunk)
                    self._trailing_pad += 1

            # ── Periodic diagnostics (every 30s) ─────────────────────────
            now = time.monotonic()
            if now - last_qsize_log >= 30.0:
                if DEBUG_SHERPA:
                    log.debug(
                        "worker: chunks=%d qsize=%d vad_ms=%.1f "
                        "drops[webrtc=%d silero=%d] passed=%d",
                        chunk_count, self._qmgr.depth, vad_latency,
                        self._vad.stats["webrtc_dropped"],
                        self._vad.stats["silero_dropped"],
                        self._vad.stats["speech_passed"],
                    )
                last_qsize_log = now
                self._qmgr.reset_warn()

            # ── Decode ───────────────────────────────────────────────────
            ready_count = self._provider.decode()
            if ready_count > 0:
                log.trace("[ASR_DECODE] Decoded %d times", ready_count)

            result = self._provider.result()

            if not result:
                if DEBUG_TRANSCRIPT_PARTIAL:
                    log.debug("[ASR_PARTIAL] result is empty")
                else:
                    log.trace("[ASR_PARTIAL] result is empty")
                self._total_processing_time_s += time.perf_counter() - t_proc_start
                self._processing_count        += 1
                continue

            # ── Transcript logging ────────────────────────────────────────
            is_final = not effective_speech and self._trailing_pad <= TRAILING_PAD_FRAMES
            if DEBUG_TRANSCRIPT_PARTIAL:
                log.debug("[ASR_PARTIAL] %r", result)
            else:
                log.trace("[ASR_PARTIAL] %r", result)

            if DEBUG_TRANSCRIPT_PARTIAL and not is_final:
                log.debug(
                    "[ASR] partial | gen=%d stab=%d | '%s'",
                    self._provider.generation_id, self._stable_frames, result,
                )
            elif DEBUG_TRANSCRIPT_FINAL and is_final:
                log.info(
                    "[ASR] final | gen=%d stab=%d len=%d | '%s'",
                    self._provider.generation_id, self._stable_frames, len(result), result,
                )

            # ── Peak tracking ─────────────────────────────────────────────
            if len(result) > self._peak_length:
                self._peak_hypothesis = result
                self._peak_length     = len(result)

            # ── Stability tracking ────────────────────────────────────────
            if result == self._last_hypothesis:
                self._stable_frames += 1
            else:
                self._stable_frames   = 0
                self._last_hypothesis = result

            # ── Deliver to engine — only during speech / trailing pad ─────
            gen_id  = self._provider.generation_id
            corr_id = self._correlation_id
            if effective_speech:
                on_hypothesis(result, self._stable_frames, self._peak_hypothesis,
                              gen_id, corr_id)
            elif self._trailing_pad <= TRAILING_PAD_FRAMES:
                on_hypothesis(result, self._stable_frames, self._peak_hypothesis,
                              gen_id, corr_id)

            self._total_processing_time_s += time.perf_counter() - t_proc_start
            self._processing_count        += 1

        log.debug("AudioWorker: stop event received, exiting")

    def _do_stream_reset(self, reason: str) -> None:
        """
        Reset stream state on this worker and on the Sherpa provider.
        Also recovers VAD FSM if applicable.

        This is the INTERNAL reset path (inactivity). The external reset
        path (wake event) goes through SherpaStreamer._reset_stream() which
        calls reset_state() on this object.
        """
        from runtime.kernel.lifecycle import SubsystemState

        # Provider owns stream lifecycle
        self._provider.reset(reason=reason)

        # Reset FSMs (only for non-silence reasons in the original logic)
        if reason != "silence":
            self._asr_fsm.recover(reason)
            if hasattr(self._vad, "_vad_fsm"):
                self._vad._vad_fsm.recover(reason)

        # Reset this worker's speech state
        self.reset_state(reason=reason)

        log.info(
            "\U0001f504 ASR stream reset -> generation %d reason=%s resets=%d",
            self._provider.generation_id,
            reason,
            self._provider.reset_count,
        )

        # After recover() the FSM is in RECOVERING state — transition back to ACTIVE
        if reason != "silence":
            if self._asr_fsm.state == SubsystemState.RECOVERING:
                self._asr_fsm.transition(SubsystemState.ACTIVE)
            if hasattr(self._vad, "_vad_fsm") and \
               self._vad._vad_fsm.state == SubsystemState.RECOVERING:
                self._vad._vad_fsm.transition(SubsystemState.ACTIVE)
