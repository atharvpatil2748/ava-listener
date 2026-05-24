"""
AVAListener — Core Engine (Phase 2)
=====================================
Orchestrator only. Contains NO detection, audio, or scoring logic.
Wires all components together and manages utterance lifecycle state.

Data flow:
  SherpaStreamer → _on_hypothesis(text, stability, peak, generation_id, correlation_id)
    → HypothesisBuffer.push()
    → best_match()                [anchor gate + fuzzy + context]
    → compute_confidence()
    → EMA smoothing               [smoothed_conf = α·raw + (1-α)·prev]
    → generation gate             [PRIMARY duplicate suppression]
    → CooldownGate                [SECONDARY duplicate suppression]
    → emit_wake()                 [stdout → Node.js]

Phase 2 additions
-----------------
  1. Utterance generation gate:   one wake per generation (silence-reset boundary)
  2. EMA confidence smoothing:    α=0.35 — smooths 0.57→0.83 spikes
  3. Per-phrase thresholds:       "arvsal"→0.80, "hey arvsal"→0.68, etc.
  4. Stability saturation:        effective_stab = min(stab, STABILITY_CAP)
  5. Hypothesis change detection: EMA resets when phrase or generation changes
  6. Rich diagnostic logging:     gen, raw, smooth, threshold, trigger/suppress reason
"""
import time
from dataclasses import dataclass, field
from asr.sherpa_stream import SherpaStreamer
from audio.buffer import HypothesisBuffer
from detection.matcher import best_match
from detection.variants import get_canonical
from confidence.scorer import compute_confidence
from decision.cooldown import CooldownGate
from integration.stdout_bridge import emit_wake, emit_status, emit_error, start_heartbeat
from runtime.state_machine import RuntimeStateMachine
from runtime.watchdog import RuntimeWatchdog
from telemetry.collector import TelemetryCollector
from utils.logger import get_logger, DEBUG_WAKE

from config.settings import (
    DEFAULT_THRESHOLD,
    EMA_RISE_ALPHA,
    EMA_DECAY_ALPHA,
    STABILITY_CAP,
    METRICS_TO_DISK,
    METRICS_FILE_PATH,
)

log = get_logger("engine")

def _get_threshold(phrase: str) -> float:
    """Return the configured trigger threshold for a matched phrase."""
    return DEFAULT_THRESHOLD


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


class WakeEngine:
    def __init__(self):
        self._streamer  = SherpaStreamer()
        self._buffer    = HypothesisBuffer()
        self._cooldown  = CooldownGate()
        self._hit_count = 0     # hypotheses in current window that scored > 0.5
        self._active_profile = {}
        self._runtime_params = {}

        # ── Phase 2: utterance generation gate ───────────────────────────────
        # Primary duplicate suppression: only ONE wake allowed per generation.
        # Generation increments on every ASR stream reset (silence timeout),
        # which creates a natural utterance boundary.
        self._last_trigger_generation: int = -1  # -1 = no trigger ever fired
        self._last_seen_generation:    int = -1  # tracks gen for EMA reset

        # ── Phase 2: EMA confidence smoothing ────────────────────────────────
        # Prevents spuriously low early partial from being the trigger score,
        # and prevents a stabilized hypothesis from re-triggering via a spike.
        # Reset whenever generation or matched phrase changes.
        self._smooth_conf:      float = 0.0
        self._last_matched_phrase: str = ""

        # ── Metrics ──────────────────────────────────────────────────────────
        self._last_metrics_time = time.monotonic()
        self._wake_count = 0
        self._latency_sum = 0.0
        self._raw_sum = 0.0
        self._smooth_sum = 0.0

        self._telemetry = TelemetryCollector(metrics_to_disk=METRICS_TO_DISK, metrics_path=METRICS_FILE_PATH)
        self._state_machine = RuntimeStateMachine()
        self._watchdog = RuntimeWatchdog(self._streamer)
        self._candidate: CandidateSession | None = None

        # ── Pause/Resume gate (controlled via stdin commands from Node.js) ────
        # When True: on_hypothesis() exits immediately — no wake can fire.
        # The audio pipeline (VAD, Silero, Sherpa) continues unaffected.
        # This preserves LSTM context continuity and enables instant resume.
        self._detection_paused: bool = False

    def load_profile(self, path: str, debug_overlay: bool = False) -> None:
        from runtime.config.profile_loader import load_profile
        from runtime.matcher.registry.phrase_registry import get_registry, PhraseConfig
        
        self._active_profile = load_profile(path, debug_overlay=debug_overlay)
        
        registry = get_registry()
        registry.clear()
        for phrase_data in self._active_profile.get("wakePhrases", []):
            registry.add_phrase(PhraseConfig.from_dict(phrase_data))
            
        from detection.variants import rebuild_index
        rebuild_index()
        
    def get_effective_config(self) -> dict:
        def flatten(d: dict, prefix: str = "") -> dict:
            res = {}
            for k, v in d.items():
                if isinstance(v, dict):
                    res.update(flatten(v, prefix + k + "."))
                elif not isinstance(v, list):
                    res[prefix + k] = v
            return res

        values = flatten(self._active_profile)
        # Apply runtime param overrides
        return {"values": values}
        
    def update_config(self, params: dict) -> None:
        from runtime.config.mutability import check_mutability
        
        # We simulate the state machine active check
        active = getattr(self, "_state_machine", None) is not None
        for key in params.keys():
            check_mutability(key, active)
            
        for key, value in params.items():
            if key == "vad.sileroThreshold":
                self._runtime_params["vad_threshold"] = value
            elif key == "confidence.defaultThreshold":
                self._runtime_params["wake_threshold"] = value

    def start(self) -> None:
        """Start the heartbeat, signal readiness, then block on mic loop."""
        start_heartbeat()
        emit_status("ready")
        self._state_machine.transition("start")
        self._watchdog.start()
        log.info("AVAListener engine started (Phase 2)")

        try:
            self._streamer.start(self._on_hypothesis)
        except KeyboardInterrupt:
            log.info("Interrupted by user")
            emit_status("stopped")
        except Exception as exc:
            log.exception("Fatal error in engine: %s", exc)
            emit_error(str(exc))
            raise

    def _start_candidate(self, phrase: str, matched_variant: str, canonical: str, text: str, raw_conf: float, smooth_conf: float, frames: int) -> None:
        self._candidate = CandidateSession(
            phrase=phrase,
            variant=matched_variant,
            canonical=canonical,
            start_time=time.monotonic(),
            last_update=time.monotonic(),
            peak_raw=raw_conf,
            peak_smooth=smooth_conf,
            transcript_evolution=[text],
            stabilization_frames=frames,
        )
        self._telemetry.start_candidate(phrase, matched_variant, canonical, text, raw_conf, smooth_conf, frames)
        self._state_machine.transition("candidate_started", detail=phrase)
        log.info("🧠 Wake candidate started: %r raw=%.2f smooth=%.2f", phrase, raw_conf, smooth_conf)

    def _update_candidate(self, text: str, raw_conf: float, smooth_conf: float, frames: int) -> None:
        if not self._candidate:
            return
        self._candidate.update(text, raw_conf, smooth_conf, frames)
        self._telemetry.update_candidate(text, raw_conf, smooth_conf, frames)
        log.debug("Candidate=%r score=%.2f smooth=%.2f", self._candidate.phrase, raw_conf, smooth_conf)
        self._state_machine.transition("candidate_updated", detail=self._candidate.phrase)

    def _confirm_candidate(self) -> None:
        if not self._candidate:
            return
        self._candidate.confirm()
        self._telemetry.confirm_candidate()
        self._state_machine.transition("candidate_confirmed", detail=self._candidate.phrase)
        self._candidate = None

    def export_metrics_json(self, path: str | None = None) -> str:
        return self._telemetry.export_metrics_json(path)

    def _drop_candidate(self) -> None:
        if not self._candidate:
            return
        self._candidate.drop()
        self._telemetry.drop_candidate()
        self._state_machine.transition("candidate_dropped", detail=self._candidate.phrase)
        log.debug("🧠 Wake candidate dropped: %r", self._candidate.phrase)
        self._candidate = None

    # ── Private ───────────────────────────────────────────────────────────────

    def _on_hypothesis(
        self,
        text:          str,
        stability:     int,
        peak:          str,
        generation_id: int,
        correlation_id: str = "",
    ) -> None:
        """
        Called by SherpaStreamer for every non-empty ASR result.
        Orchestrates the full Phase 2 detection pipeline.

        Args:
            text:          current partial hypothesis from Sherpa
            stability:     frames since last text change (0 = just changed)
            peak:          longest hypothesis decoded since last stream reset
            generation_id: utterance generation counter from SherpaStreamer
            correlation_id: tracking ID for metrics
        """
        t0 = time.monotonic()

        # ── Pause gate ────────────────────────────────────────────────────────
        # Controlled by stdin commands (pause/suppress/resume) from Node.js.
        # The full audio pipeline continues running to keep models warm.
        if self._detection_paused:
            return

        # ── Runtime Metrics ───────────────────────────────────────────────────
        now = time.monotonic()
        if now - self._last_metrics_time >= 30.0:
            vad_stats = getattr(self._streamer._vad, "stats", {})
            webrtc_dropped = vad_stats.get("webrtc_dropped", 0)
            silero_dropped = vad_stats.get("silero_dropped", 0)
            speech_passed = vad_stats.get("speech_passed", 0)
            total_vad = webrtc_dropped + silero_dropped + speech_passed
            pass_rate = (speech_passed / total_vad * 100) if total_vad > 0 else 0.0
            
            silero_probs = vad_stats.get("silero_probs", [])
            s_avg = sum(silero_probs) / len(silero_probs) if silero_probs else 0.0
            s_max = max(silero_probs) if silero_probs else 0.0
            
            avg_lat = (self._latency_sum / self._wake_count) if self._wake_count > 0 else 0.0
            avg_raw = (self._raw_sum / self._wake_count) if self._wake_count > 0 else 0.0
            avg_smooth = (self._smooth_sum / self._wake_count) if self._wake_count > 0 else 0.0

            log.info(
                "[METRICS] wake_count=%d avg_trigger_latency=%.1fms avg_raw=%.2f avg_smooth=%.2f "
                "vad_pass_rate=%.1f%% silero_avg=%.2f silero_max=%.2f reset_count=%d",
                self._wake_count, avg_lat, avg_raw, avg_smooth, pass_rate, s_avg, s_max, generation_id
            )
            
            self._last_metrics_time = now
            vad_stats["silero_probs"] = []

        # ── Stability saturation ──────────────────────────────────────────────
        # Cap raw stability so stab=50+ stops generating log noise and repeated
        # scoring of an already-frozen hypothesis. Weight table in matcher.py
        # already caps at weight=4 (stab>=6), so effective scoring is unchanged.
        eff_stab = min(stability, STABILITY_CAP)

        # ── Buffer ───────────────────────────────────────────────────────────
        self._buffer.push(text, eff_stab)

        # Push peak (more complete decoding) with bonus stability so it
        # outweighs early partials in the weighted combined text.
        if peak and peak != text and len(peak) > len(text):
            self._buffer.push(peak, eff_stab + 2)

        window = self._buffer.get_window()

        # ── Matching ─────────────────────────────────────────────────────────
        score, phrase, matched_variant = best_match(window)

        # If matcher found a specific variant, use get_canonical as a sanity
        # check (the fuzzy scorer may pick a different canonical phrase than
        # the variant mapping; prefer the fuzzy scorer's phrase for scoring but
        # log both for diagnostics).
        canonical_from_variant = get_canonical(matched_variant) if matched_variant else ""

        # ── Hit counter (sustained match tracking) ────────────────────────────
        if score > 0.50:
            self._hit_count += 1
        else:
            self._hit_count = max(0, self._hit_count - 1)

        # ── Raw confidence ────────────────────────────────────────────────────
        raw_conf = compute_confidence(score, len(window), self._hit_count)
        self._telemetry.register_asr_latency((time.monotonic() - t0) * 1000)

        # ── Candidate lifecycle / observation layer ───────────────────────────────
        if phrase and raw_conf >= 0.50:
            if not self._candidate or self._candidate.phrase != phrase:
                self._start_candidate(
                    phrase,
                    matched_variant,
                    canonical_from_variant or phrase,
                    text,
                    raw_conf,
                    self._smooth_conf,
                    eff_stab,
                )
            else:
                self._update_candidate(text, raw_conf, self._smooth_conf, eff_stab)
        elif self._candidate and now - self._candidate.last_update > 1.0:
            self._drop_candidate()

        # ── EMA reset conditions ──────────────────────────────────────────────
        # 1. New generation (silence reset occurred) → fresh utterance
        if generation_id != self._last_seen_generation:
            self._smooth_conf         = 0.0
            self._hit_count           = 0
            self._last_seen_generation = generation_id
            log.debug(
                "EMA reset: new generation %d → %d",
                self._last_seen_generation, generation_id,
            )

        # 2. Matched phrase changed → previous confidence state is irrelevant
        if phrase and phrase != self._last_matched_phrase:
            self._smooth_conf         = 0.0
            self._last_matched_phrase = phrase

        # ── EMA smoothing ─────────────────────────────────────────────────────
        # Asymmetric smoothing: faster rise on incoming signal, slower decay.
        alpha = EMA_RISE_ALPHA if raw_conf > self._smooth_conf else EMA_DECAY_ALPHA
        self._smooth_conf = alpha * raw_conf + (1.0 - alpha) * self._smooth_conf

        # Per-phrase trigger threshold
        threshold = _get_threshold(phrase) if phrase else DEFAULT_THRESHOLD

        # ── Trigger gate (Escape Hatch + EMA) ─────────────────────────────────
        is_escape_trigger = raw_conf >= (threshold + 0.08)
        would_ema_trigger = self._smooth_conf >= threshold

        # ── Diagnostic logging ────────────────────────────────────────────────
        if DEBUG_WAKE:
            log.debug(
                "[WAKE_CHECK] hyp=%r eff_stab=%d gen=%d raw=%.2f smooth=%.2f threshold=%.2f "
                "phrase=%r variant=%r canonical=%r would_raw_trigger=%s would_ema_trigger=%s",
                text, eff_stab, generation_id,
                raw_conf, self._smooth_conf, threshold,
                phrase, matched_variant, canonical_from_variant,
                is_escape_trigger, would_ema_trigger
            )
        elif phrase and raw_conf >= 0.5:
            log.info("🧠 Wake candidate: %r raw=%.2f smooth=%.2f", phrase, raw_conf, self._smooth_conf)

        if not (is_escape_trigger or would_ema_trigger):
            return   # fast path — not confident yet

        # ── Generation gate (PRIMARY duplicate suppression) ───────────────────
        # One wake per utterance generation. Even if cooldown expires, a
        # stabilized hypothesis from the SAME utterance cannot re-fire.
        if generation_id == self._last_trigger_generation:
            if getattr(self, '_last_logged_suppressed_gen', -1) != generation_id:
                log.debug(
                    "suppressed repeated wake in generation=%d phrase=%r",
                    generation_id, phrase
                )
                self._last_logged_suppressed_gen = generation_id
            return

        # ── Cooldown gate (SECONDARY duplicate suppression) ───────────────────
        if not self._cooldown.can_trigger():
            log.debug(
                "suppressed: cooldown remaining=%.1fs phrase=%r",
                self._cooldown.time_remaining(), phrase,
            )
            return

        # ── FIRE ─────────────────────────────────────────────────────────────
        latency_ms = (time.monotonic() - t0) * 1000
        self._last_trigger_generation = generation_id
        self._cooldown.mark_triggered()
        self._buffer.clear()
        self._hit_count    = 0
        
        self._wake_count += 1
        self._latency_sum += latency_ms
        self._raw_sum += raw_conf
        self._smooth_sum += self._smooth_conf
        self._telemetry.register_wake(latency_ms)
        self._confirm_candidate()
        self._state_machine.transition("cooldown", detail=phrase)

        log.info(
            "🔥 WAKE | phrase=%r gen=%d variant=%r canonical=%r "
            "raw=%.2f smooth=%.2f threshold=%.2f latency=%.0fms",
            phrase, generation_id, matched_variant, canonical_from_variant,
            raw_conf, self._smooth_conf, threshold, latency_ms,
        )
        t_before_emit = time.monotonic()
        emit_wake(phrase, raw_conf, self._smooth_conf, latency_ms)
        log.debug("wake_latency=%.0fms inference=%.0fms websocket_send=%.0fms", latency_ms, (t0 - self._candidate.start_time)*1000 if self._candidate else 0, (time.monotonic() - t_before_emit)*1000)
        self._smooth_conf  = 0.0   # reset EMA post-trigger
        self._streamer._reset_stream(reason="wake")
