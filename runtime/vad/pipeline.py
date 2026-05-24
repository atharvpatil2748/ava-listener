"""
AVAListener — Two-Stage Hybrid Voice Activity Detection (Phase 4A)
====================================================================
Commercial-grade VAD pipeline cascading a cheap prefilter with a heavy verifier.

Architecture:
  Stage 1: WebRTC VAD (Prefilter)
           Extremely cheap. Catches all noise. 
           Drops true digital silence instantly.
  
  Stage 2: Silero VAD (Verifier)
           Neural model (ONNX). Runs ONLY if Stage 1 passes.
           Accurately distinguishes human speech from ambient noise (fans, typing).

Statefulness:
  Silero VAD is stateful. It maintains an internal acoustic context across frames.
  This requires the VAD object to hold `_state` and be instantiated per-stream.
"""
import numpy as np
import webrtcvad
import onnxruntime as ort
import os
from collections import deque
import statistics

from config.settings import (
    VAD_AGGRESSIVENESS,
    VAD_FRAME_SAMPLES,
    SAMPLE_RATE,
    RMS_FLOOR,
    MODELS_DIR,
    SILERO_THRESHOLD,
    NOISE_FLOOR_MULTIPLIER,
    NOISE_HISTORY_FRAMES,
)
from runtime.kernel.lifecycle import SubsystemLifecycle, SubsystemState
from utils.logger import get_logger, DEBUG_VAD, DEBUG_ONNX

log = get_logger("vad")


class HybridVAD:
    """
    Stateful Two-Stage VAD pipeline.
    Must be instantiated once per ASR stream to maintain Silero's internal RNN state.
    """
    def __init__(self):
        # ── Stage 1: WebRTC (Prefilter) ──────────────────────────────────────
        self._webrtc = webrtcvad.Vad(VAD_AGGRESSIVENESS)
        self._vad_fsm = SubsystemLifecycle("VAD")
        self._vad_fsm.transition(SubsystemState.INITIALIZING)
        
        # ── Stage 2: Silero (Verifier) ───────────────────────────────────────
        try:
            from runtime.resources.vad_resources import SileroResources
            self._silero_sess = SileroResources.create_session()
            self._silero_sr = np.array(SAMPLE_RATE, dtype=np.int64)
            self.reset_state()
        except FileNotFoundError as e:
            log.warning("%s. Falling back to WebRTC-only.", e)
            self._silero_sess = None

        # Diagnostics tracking
        self.stats = {
            "webrtc_dropped": 0,
            "silero_dropped": 0,
            "speech_passed": 0,
            "silero_probs": [],
        }

        self._noise_rms_history = deque(maxlen=NOISE_HISTORY_FRAMES)
        
        self._vad_fsm.transition(SubsystemState.READY)
        self._vad_fsm.transition(SubsystemState.ACTIVE)

    def reset_state(self) -> None:
        """Clear Silero's internal RNN state. Call this on stream boundaries."""
        self._audio_buffer = np.array([], dtype=np.float32)
        if self._silero_sess:
            # Silero v4/v5 state shape: (2, batch_size, 128)
            self._silero_state = np.zeros((2, 1, 128), dtype=np.float32)
            # The CNN feature extractor requires a 64-sample overlapping context
            # to prevent boundary artifacts in streaming mode.
            self._silero_context = np.zeros((1, 64), dtype=np.float32)
            self._frame_count = 0
            self._last_speech_pass = False

    def _adaptive_noise_floor(self) -> float:
        """Return the rolling median silence RMS clamped to a safe minimum."""
        if not self._noise_rms_history:
            return RMS_FLOOR
        median = statistics.median(self._noise_rms_history)
        return max(median, RMS_FLOOR)

    def process_chunk(self, chunk: np.ndarray) -> dict:
        """
        Evaluate audio chunk and return full diagnostic state.
        Returns dict with: webrtc (bool), silero_prob (float), silero_pass (bool), rms (float), pass (bool).
        """
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        peak = float(np.max(np.abs(chunk)))
        
        result = {
            "webrtc": False,
            "silero_prob": 0.0,
            "silero_pass": False,
            "rms": rms,
            "peak": peak,
            "pass": False
        }

        # ── Gate 0: Extreme Silence ──────────────────────────────────────────
        if rms < 0.0001:
            self.stats["webrtc_dropped"] += 1
            return result

        # Buffer the incoming chunk to handle unaligned block sizes (1600 not divisible by 512)
        self._audio_buffer = np.concatenate([self._audio_buffer, chunk])

        # ── Gate 1: WebRTC Prefilter ─────────────────────────────────────────
        frame = chunk[:VAD_FRAME_SAMPLES]
        if len(frame) < VAD_FRAME_SAMPLES:
            frame = np.pad(frame, (0, VAD_FRAME_SAMPLES - len(frame)))
        
        pcm = (np.clip(frame, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
        try:
            webrtc_speech = self._webrtc.is_speech(pcm, SAMPLE_RATE)
        except Exception:
            webrtc_speech = True  # fail open
            
        result["webrtc"] = webrtc_speech

        if not webrtc_speech:
            self.stats["webrtc_dropped"] += 1
            # Even if WebRTC fails, we must drain the buffer to prevent memory leaks.
            # We feed zeros to Silero to let its LSTM internal state cool down.
            if self._silero_sess:
                # WebRTC acts as our prefilter. If it detects absolute silence/noise,
                # we drop the chunk and RESET the Silero state. 
                # This prevents the LSTM state from exploding (saturating) on long continuous room noise.
                self.reset_state()
            self._audio_buffer = np.array([], dtype=np.float32)

            energy_threshold = max(RMS_FLOOR, self._adaptive_noise_floor() * NOISE_FLOOR_MULTIPLIER)
            if rms >= energy_threshold:
                result["pass"] = True
                self.stats["speech_passed"] += 1
            else:
                self._noise_rms_history.append(rms)

            return result

        # ── Gate 2: Silero Verifier ──────────────────────────────────────────
        if not self._silero_sess:
            result["pass"] = True
            self.stats["speech_passed"] += 1
            return result

        probs = []
        while len(self._audio_buffer) >= 512:
            segment = self._audio_buffer[:512]
            self._audio_buffer = self._audio_buffer[512:]
                
            prob = self._run_silero(segment)
            probs.append(prob)
            
        # Aggregate probability over the 1600-sample chunk
        max_prob = max(probs) if probs else 0.0
        result["silero_prob"] = max_prob
        self.stats["silero_probs"].append(max_prob)
        
        if max_prob >= SILERO_THRESHOLD:
            result["silero_pass"] = True

        # The Final Gate: Silero is PRIMARY, WebRTC is PREFILTER, RMS is FALLBACK
        energy_threshold = max(RMS_FLOOR, self._adaptive_noise_floor() * NOISE_FLOOR_MULTIPLIER)
        if result["silero_pass"] or rms >= energy_threshold:
            result["pass"] = True
            self.stats["speech_passed"] += 1
        else:
            self.stats["silero_dropped"] += 1
            self._noise_rms_history.append(rms)

        # Track and log transitions
        if result["pass"] and not getattr(self, "_last_speech_pass", False):
            log.debug("[VAD] \ud83c\udfa4 SPEECH STARTED (webrtc=%s, silero_prob=%.4f)", result["webrtc"], result["silero_prob"])
            self._last_speech_pass = True
        elif not result["pass"] and getattr(self, "_last_speech_pass", False):
            log.debug("[VAD] \ud83d\udd07 SPEECH ENDED")
            self._last_speech_pass = False

        return result

    def _run_silero(self, audio: np.ndarray) -> float:
        """Internal helper to execute ONNX graph."""
        # 1. Convert to float32
        audio = np.asarray(audio, dtype=np.float32)
        
        # 2. Ensure shape is exactly (1, N)
        if audio.ndim == 1:
            audio = np.expand_dims(audio, axis=0)
            
        # 3. Concatenate the overlapping 64-sample context!
        # This is absolutely mandatory for the CNN layers to prevent boundary corruption.
        # Without this overlap, the output produces garbage which permanently saturates the LSTM state.
        audio_with_context = np.concatenate([self._silero_context, audio], axis=1)
            
        # 4. Use contiguous memory
        audio_with_context = np.ascontiguousarray(audio_with_context)
        
        ort_inputs = {
            'input': audio_with_context,
            'state': self._silero_state,
            'sr': self._silero_sr
        }
        ort_outs = self._silero_sess.run(['output', 'stateN'], ort_inputs)
        
        prob = float(ort_outs[0][0][0])
        self._silero_state = ort_outs[1]
        
        # 5. Save the trailing 64 samples of the CURRENT chunk to act as context for the NEXT chunk
        self._silero_context = audio_with_context[:, -64:]
        
        # 6. Occasional diagnostics (every 5th frame) — only when DEBUG_ONNX is on
        self._frame_count += 1
        if DEBUG_ONNX and self._frame_count % 5 == 0:
            log.debug("[ONNX] prob: %.4f | state_mean: %.4f", prob, float(np.mean(self._silero_state)))

        return prob

    # ── Debug export contract (P5-BLOCK-004) ──────────────────────────────────

    def export_debug_state(self) -> dict:
        """
        Export a safe, immutable snapshot of VAD internal state.
        CrashSnapshot MUST consume this interface only — no direct private access.
        """
        return {
            "fsm_state": self._vad_fsm.state.value,
            "silero_available": self._silero_sess is not None,
            "stats": dict(self.stats),
            "frame_count": getattr(self, "_frame_count", 0),
            "last_speech_pass": getattr(self, "_last_speech_pass", False),
        }
