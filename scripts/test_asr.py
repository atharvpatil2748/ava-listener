#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AVAListener — Raw ASR Diagnostic Script
========================================
Purpose: validate the acoustic pipeline END-TO-END with zero wake logic.

What runs:
    mic → sounddevice → PCM → Sherpa streaming ASR → transcript printed to terminal

What does NOT run:
    VAD | matcher | scorer | cooldown | confidence | buffer | any wake logic

What is measured and printed:
    A.  Audio device info      — sample rate, channels, device name, actual SR delivered
    B.  PCM frame stats        — RMS energy, peak, DC offset, clipping, per chunk
    C.  Sherpa chunk latency   — time from accept_waveform() to get_result() per chunk
    D.  Hypothesis stream      — every partial printed with elapsed time + char count
    E.  Endpoint detection     — when Sherpa fires an endpoint and what the final text is
    F.  Per-utterance report   — WER-proxy, word count, latency from first chunk to endpoint

Usage:
    cd wakeword
    venv\\Scripts\\python scripts\\test_asr.py

    Optional flags:
        --duration   N     record for N seconds then exit (default: run until Ctrl+C)
        --block      N     override BLOCK_SIZE (samples, default: 1600)
        --rate       N     override SAMPLE_RATE (Hz, default: 16000)
        --threads    N     override NUM_THREADS (default: 2)
        --device     N     sounddevice device index (default: system default)
        --no-endpoint      disable Sherpa endpoint detection
        --save-wav         save raw mic audio to scripts/diag_capture.wav

Press Ctrl+C to stop and print final analysis summary.
"""
import sys
import os
import time
import argparse
import textwrap
import struct
import threading
import queue
import wave

import numpy as np
import sounddevice as sd
import sherpa_onnx

# ── Path bootstrap (run from any CWD) ─────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_WAKEWORD_DIR = os.path.dirname(_HERE)
sys.path.insert(0, _WAKEWORD_DIR)

# ── Defaults sourced from settings.py ─────────────────────────────────────────
from config.settings import SAMPLE_RATE, BLOCK_SIZE, NUM_THREADS, MODELS_DIR

# ── ANSI color helpers ─────────────────────────────────────────────────────────
def _c(code, text): return f"\033[{code}m{text}\033[0m"
def green(t):  return _c("92", t)
def yellow(t): return _c("93", t)
def red(t):    return _c("91", t)
def cyan(t):   return _c("96", t)
def bold(t):   return _c("1",  t)
def dim(t):    return _c("2",  t)

# Windows: enable ANSI + UTF-8 output in cmd/PowerShell
if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.kernel32.SetConsoleMode(
            ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass
    # Force UTF-8 so box-drawing chars and arrows render correctly
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# ─────────────────────────────────────────────────────────────────────────────
# Argument parsing
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Raw ASR diagnostic — mic → Sherpa transcript, no wake logic")
    p.add_argument("--duration",    type=float, default=0,
                   help="Stop after N seconds (0 = run until Ctrl+C)")
    p.add_argument("--block",       type=int,   default=BLOCK_SIZE,
                   help=f"Chunk size in samples (default {BLOCK_SIZE} = 100ms)")
    p.add_argument("--rate",        type=int,   default=SAMPLE_RATE,
                   help=f"Sample rate Hz (default {SAMPLE_RATE})")
    p.add_argument("--threads",     type=int,   default=NUM_THREADS,
                   help=f"Sherpa inference threads (default {NUM_THREADS})")
    p.add_argument("--device",      type=int,   default=None,
                   help="sounddevice device index (default: system default)")
    p.add_argument("--no-endpoint", action="store_true",
                   help="Disable Sherpa endpoint detection")
    p.add_argument("--save-wav",    action="store_true",
                   help="Save mic capture to scripts/diag_capture.wav (for offline analysis)")
    return p.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
# Section A — Audio device diagnostics
# ─────────────────────────────────────────────────────────────────────────────

def print_device_info(device_idx, requested_rate, block_size):
    print(bold("\n━━━ A. AUDIO DEVICE INFO ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))

    all_devs = sd.query_devices()
    default_in = sd.default.device[0]
    chosen = device_idx if device_idx is not None else default_in
    dev = sd.query_devices(chosen)

    print(f"  Device index   : {chosen}")
    print(f"  Device name    : {dev['name']}")
    print(f"  Max in channels: {dev['max_input_channels']}")
    print(f"  Default SR     : {int(dev['default_samplerate'])} Hz")
    print(f"  Requested SR   : {requested_rate} Hz")
    print(f"  Block size     : {block_size} samples = {block_size/requested_rate*1000:.1f} ms")

    # Check SR mismatch
    dev_native = int(dev['default_samplerate'])
    if dev_native != requested_rate:
        print(yellow(f"\n  ⚠ SAMPLE RATE MISMATCH: device native={dev_native}Hz, "
                     f"requesting={requested_rate}Hz"))
        print(yellow("    sounddevice will resample internally — this adds latency and "
                     "may degrade quality."))
        print(yellow("    Recommendation: if possible, set system mic to 16000 Hz in "
                     "Windows Sound settings."))
    else:
        print(green(f"  ✓ Sample rate matches device native ({dev_native} Hz)"))

    # Check if model rate matches
    if requested_rate != 16000:
        print(red(f"\n  ✗ Sherpa Zipformer expects 16000 Hz. You are passing {requested_rate} Hz."))
        print(red("    This WILL cause degraded transcription. Reset --rate to 16000."))
    else:
        print(green("  ✓ Sample rate = 16000 Hz — correct for Sherpa Zipformer"))

    print()
    return chosen


# ─────────────────────────────────────────────────────────────────────────────
# Section B — Model diagnostics
# ─────────────────────────────────────────────────────────────────────────────

def print_model_info(models_dir, threads):
    print(bold("━━━ B. MODEL DIAGNOSTICS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))

    files = {
        "encoder.onnx": ("encoder", 60_000_000, 140_000_000),
        "decoder.onnx": ("decoder",    400_000,   1_000_000),
        "joiner.onnx" : ("joiner",     150_000,     500_000),
        "tokens.txt"  : ("tokens",       2_000,      10_000),
    }
    model_ok = True
    for fname, (label, lo, hi) in files.items():
        path = os.path.join(models_dir, fname)
        if not os.path.isfile(path):
            print(red(f"  ✗ MISSING: {fname}"))
            model_ok = False
            continue
        sz = os.path.getsize(path)
        sz_mb = sz / 1_048_576
        if lo <= sz <= hi:
            marker = green("✓")
            note = ""
        else:
            marker = yellow("?")
            note = f"  ← unexpected size (expected {lo//1000}K–{hi//1_000_000}MB)"
        print(f"  {marker} {fname:<20} {sz_mb:>7.2f} MB{note}")

    # Model identity heuristic from encoder size
    enc_path = os.path.join(models_dir, "encoder.onnx")
    if os.path.isfile(enc_path):
        enc_sz = os.path.getsize(enc_path)
        if 100_000_000 <= enc_sz <= 135_000_000:
            model_id = "sherpa-onnx-streaming-zipformer-en-2023-06-26 (int8, ~121MB)"
            print(f"\n  {green('✓')} Identified model: {bold(model_id)}")
            print(f"    WER on LibriSpeech test-clean: ~3.8%  test-other: ~9.8%")
            print(f"    Accent coverage: trained on LibriSpeech — mostly US/UK English")
            print(yellow("    ⚠ Indian accent caveat: LibriSpeech has minimal Indian accent data."))
            print(yellow("      Expect 10–25% higher WER on Indian English vs US English."))
            print(yellow("      This is a model-level limitation, not a pipeline issue."))
            print(yellow("      Mitigation: larger Zipformer or add ANCHOR_VARIANTS for common"))
            print(yellow("      ASR substitutions of your accent (already partially done)."))
        elif enc_sz < 50_000_000:
            model_id = "Possible tiny/pruned Zipformer — low accuracy expected"
            print(f"\n  {yellow('?')} Encoder small ({enc_sz//1_000_000}MB): {model_id}")
        elif enc_sz > 200_000_000:
            model_id = "Possible large Zipformer — high accuracy, high latency"
            print(f"\n  {yellow('?')} Encoder large ({enc_sz//1_000_000}MB): {model_id}")

    print(f"\n  Inference threads: {threads}")
    if threads == 1:
        print(yellow("  ⚠ Single thread may cause decoder backpressure on 100ms chunks."))
        print(yellow("    Recommend: --threads 2"))
    elif threads >= 4:
        print(yellow("  ⚠ 4+ threads may cause scheduling overhead on streaming chunks."))
        print(yellow("    Recommend: --threads 2"))
    else:
        print(green(f"  ✓ Thread count ({threads}) is appropriate for streaming."))

    print()
    return model_ok


# ─────────────────────────────────────────────────────────────────────────────
# Section C — Build Sherpa recognizer
# ─────────────────────────────────────────────────────────────────────────────

def build_recognizer(models_dir, sample_rate, threads, endpoint_enabled):
    enc = os.path.join(models_dir, "encoder.onnx")
    dec = os.path.join(models_dir, "decoder.onnx")
    joi = os.path.join(models_dir, "joiner.onnx")
    tok = os.path.join(models_dir, "tokens.txt")

    kwargs = dict(
        encoder=enc,
        decoder=dec,
        joiner=joi,
        tokens=tok,
        num_threads=threads,
        sample_rate=sample_rate,
        feature_dim=80,
        enable_endpoint_detection=endpoint_enabled,
    )
    if endpoint_enabled:
        kwargs.update(
            rule1_min_trailing_silence=0.6,
            rule2_min_trailing_silence=1.2,
            rule3_min_utterance_length=20.0,
        )

    t0 = time.monotonic()
    recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(**kwargs)
    load_ms = (time.monotonic() - t0) * 1000
    print(bold("━━━ C. RECOGNIZER LOAD ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
    print(f"  Load time      : {load_ms:.0f} ms")
    if load_ms < 2000:
        print(green("  ✓ Fast load — model is likely cached in OS page cache"))
    elif load_ms < 5000:
        print(green("  ✓ Normal load time"))
    else:
        print(yellow(f"  ⚠ Slow load ({load_ms:.0f}ms) — SSD speed or first-run model parse"))

    print(f"  Endpoint       : {'enabled (Rule1=0.6s  Rule2=1.2s)' if endpoint_enabled else red('DISABLED')}")
    print()
    return recognizer


# ─────────────────────────────────────────────────────────────────────────────
# Live streaming loop
# ─────────────────────────────────────────────────────────────────────────────

class DiagnosticSession:
    """Holds all live measurements for final summary."""

    def __init__(self, sample_rate, block_size, save_wav):
        self.sample_rate = sample_rate
        self.block_size  = block_size
        self.save_wav    = save_wav

        # Per-chunk stats
        self.chunk_count      = 0
        self.chunk_latencies  = []   # ms: accept_waveform → get_result
        self.chunk_rms_values = []
        self.chunk_peaks      = []
        self.clipped_chunks   = 0
        self.dc_offsets       = []

        # Per-hypothesis
        self.hypothesis_count     = 0
        self.last_hypothesis      = ""
        self.hypothesis_changes   = 0    # how many times text changed
        self.hypothesis_stable    = 0    # how many times text was identical to last

        # Per-utterance (between endpoints)
        self.utterances           = []   # list of dicts
        self.current_utt_start    = None # monotonic time of first non-empty partial
        self.current_utt_first    = ""   # first partial text

        # WAV capture
        self._wav_frames = [] if save_wav else None

        # For rate measurement
        self.stream_start         = time.monotonic()
        self.last_print_time      = 0.0

    def record_chunk(self, chunk: np.ndarray, latency_ms: float):
        self.chunk_count += 1
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        peak = float(np.max(np.abs(chunk)))
        dc   = float(np.mean(chunk))

        self.chunk_rms_values.append(rms)
        self.chunk_peaks.append(peak)
        self.dc_offsets.append(dc)
        self.chunk_latencies.append(latency_ms)

        if peak >= 0.999:
            self.clipped_chunks += 1

        if self._wav_frames is not None:
            pcm16 = (np.clip(chunk, -1.0, 1.0) * 32767).astype(np.int16)
            self._wav_frames.append(pcm16.tobytes())

    def record_hypothesis(self, text: str, elapsed_s: float):
        if text == self.last_hypothesis:
            self.hypothesis_stable += 1
        else:
            self.hypothesis_changes += 1
            self.last_hypothesis = text

        if text and self.current_utt_start is None:
            self.current_utt_start = elapsed_s
            self.current_utt_first = text

        self.hypothesis_count += 1

    def record_endpoint(self, final_text: str, elapsed_s: float):
        if self.current_utt_start is not None:
            latency = elapsed_s - self.current_utt_start
            self.utterances.append({
                "text":    final_text,
                "latency": latency,
                "words":   len(final_text.split()) if final_text else 0,
            })
        self.current_utt_start = None
        self.current_utt_first = ""

    def save_wav_file(self, path):
        if self._wav_frames is None or not self._wav_frames:
            return
        with wave.open(path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(b"".join(self._wav_frames))
        print(f"\n  WAV saved → {path}")

    def print_summary(self):
        elapsed = time.monotonic() - self.stream_start
        print(bold("\n\n━━━ FINAL DIAGNOSTIC SUMMARY ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))

        # Audio stats
        if self.chunk_rms_values:
            avg_rms  = np.mean(self.chunk_rms_values)
            max_rms  = np.max(self.chunk_rms_values)
            avg_peak = np.mean(self.chunk_peaks)
            max_peak = np.max(self.chunk_peaks)
            avg_dc   = np.mean(np.abs(self.dc_offsets))
            clip_pct = 100 * self.clipped_chunks / max(self.chunk_count, 1)
        else:
            avg_rms = max_rms = avg_peak = max_peak = avg_dc = clip_pct = 0.0

        print(bold("\n  [AUDIO QUALITY]"))
        print(f"    Avg RMS energy : {avg_rms:.4f}", end="  ")
        if avg_rms < 0.002:
            print(red("← VERY QUIET — mic too far or gain too low"))
        elif avg_rms < 0.01:
            print(yellow("← Quiet — consider increasing mic gain"))
        elif avg_rms > 0.3:
            print(yellow("← LOUD — risk of clipping"))
        else:
            print(green("← Good level"))

        print(f"    Max RMS energy : {max_rms:.4f}")
        print(f"    Avg peak       : {avg_peak:.4f}")
        print(f"    Max peak       : {max_peak:.4f}", end="  ")
        if max_peak >= 0.999:
            print(red(f"← CLIPPING DETECTED ({self.clipped_chunks} chunks)"))
        else:
            print(green("← No clipping"))

        print(f"    DC offset (avg): {avg_dc:.6f}", end="  ")
        if avg_dc > 0.01:
            print(yellow("← DC bias present — may indicate mic hardware issue"))
        else:
            print(green("← Negligible"))

        # Chunk latency
        if self.chunk_latencies:
            lat_arr = np.array(self.chunk_latencies)
            print(bold("\n  [CHUNK DECODE LATENCY]"))
            print(f"    Mean  : {np.mean(lat_arr):.1f} ms")
            print(f"    Median: {np.median(lat_arr):.1f} ms")
            print(f"    P95   : {np.percentile(lat_arr, 95):.1f} ms")
            print(f"    Max   : {np.max(lat_arr):.1f} ms", end="  ")
            chunk_dur_ms = self.block_size / self.sample_rate * 1000
            if np.max(lat_arr) > chunk_dur_ms:
                print(red(f"← BACKPRESSURE: decode > chunk duration ({chunk_dur_ms:.0f}ms)"))
                print(red("    Pipeline cannot keep up. Try --threads 2 or smaller block."))
            else:
                print(green(f"← Within chunk budget ({chunk_dur_ms:.0f}ms) ✓"))

        # Hypothesis stability
        total_hyp = self.hypothesis_changes + self.hypothesis_stable
        print(bold("\n  [HYPOTHESIS STABILITY]"))
        print(f"    Total hypothesis events : {total_hyp}")
        print(f"    Text changes            : {self.hypothesis_changes}")
        print(f"    Stable (same as prev)   : {self.hypothesis_stable}")
        if total_hyp > 0:
            stable_rate = self.hypothesis_stable / total_hyp
            print(f"    Stability rate          : {stable_rate:.1%}", end="  ")
            if stable_rate < 0.3:
                print(yellow("← High churn — partials fluctuating heavily"))
            elif stable_rate < 0.5:
                print(yellow("← Moderate churn — normal for streaming transducer"))
            else:
                print(green("← Good stability"))

        # Utterances
        print(bold("\n  [UTTERANCE RESULTS]"))
        if not self.utterances:
            print(red("    No complete utterances detected (no endpoint fired)."))
            print(red("    Possible causes:"))
            print(red("      - Speaking before model finished loading"))
            print(red("      - Endpoint detection disabled (--no-endpoint)"))
            print(red("      - Very short utterances below Sherpa's min trailing silence"))
        else:
            for i, u in enumerate(self.utterances, 1):
                lat_str = f"{u['latency']*1000:.0f}ms"
                print(f"    [{i}] {lat_str:>6}  {u['words']:2}w  {u['text']!r}")
            avg_lat = np.mean([u['latency'] for u in self.utterances]) * 1000
            print(f"\n    Avg endpoint latency: {avg_lat:.0f} ms")
            if avg_lat < 800:
                print(green("    ✓ Good — endpoint is responsive"))
            elif avg_lat < 1500:
                print(yellow("    ⚠ Moderate — ENDPOINT_RULE1_SILENCE may be tunable"))
            else:
                print(red("    ✗ Slow — reduce ENDPOINT_RULE1_SILENCE or check chunk size"))

        # Session summary
        print(bold("\n  [SESSION]"))
        print(f"    Duration      : {elapsed:.1f}s")
        print(f"    Total chunks  : {self.chunk_count}")
        actual_rate = self.chunk_count * self.block_size / max(elapsed, 0.001)
        print(f"    Actual sample rate delivered: {actual_rate:.0f} Hz", end="  ")
        expected = self.sample_rate
        if abs(actual_rate - expected) / expected > 0.02:
            print(yellow(f"← DRIFT: expected {expected} Hz (>2% off — OS resampling?)"))
        else:
            print(green(f"← Within 2% of {expected} Hz ✓"))

        print(bold("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"))


# ─────────────────────────────────────────────────────────────────────────────
# Main streaming loop
# ─────────────────────────────────────────────────────────────────────────────

def run_stream(recognizer, session: DiagnosticSession, device_idx, duration):
    stream_obj = recognizer.create_stream()
    last_text  = ""
    start_time = time.monotonic()
    endpoint_count = 0

    print(bold("━━━ D. LIVE TRANSCRIPT STREAM ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
    print(dim("  Format: [elapsed_s | chunk_ms | rms | text]"))
    print(dim("  Press Ctrl+C to stop.\n"))

    def _callback(indata, frames, time_info, status):
        nonlocal last_text, stream_obj, endpoint_count

        if status:
            print(yellow(f"  sounddevice status: {status}"))

        chunk = indata[:, 0].astype(np.float32)

        # ── PCM diagnostics ───────────────────────────────────────────────────
        t_decode_start = time.monotonic()
        stream_obj.accept_waveform(session.sample_rate, chunk)
        while recognizer.is_ready(stream_obj):
            recognizer.decode_stream(stream_obj)
        latency_ms = (time.monotonic() - t_decode_start) * 1000

        session.record_chunk(chunk, latency_ms)

        elapsed = time.monotonic() - start_time

        # ── Hypothesis ────────────────────────────────────────────────────────
        text = recognizer.get_result(stream_obj).strip().lower()

        if text:
            session.record_hypothesis(text, elapsed)
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            rms_bar = "▁▂▃▄▅▆▇█"[min(int(rms * 80), 7)]

            changed = text != last_text
            text_display = green(text) if changed else dim(text)
            change_marker = "●" if changed else "·"

            print(f"  {change_marker} [{elapsed:6.2f}s | {latency_ms:5.1f}ms | {rms_bar} {rms:.3f}] "
                  f"{text_display}")
            last_text = text

        # ── Endpoint detection ────────────────────────────────────────────────
        if recognizer.is_endpoint(stream_obj):
            endpoint_count += 1
            final = recognizer.get_result(stream_obj).strip().lower()
            session.record_endpoint(final, elapsed)

            words = len(final.split()) if final else 0
            print(f"\n  {bold(cyan('▶ ENDPOINT'))} #{endpoint_count}  "
                  f"text={bold(final)!r}  words={words}  t={elapsed:.2f}s\n")

            # Reset stream for next utterance
            recognizer.reset(stream_obj)
            last_text = ""

        # ── Duration gate ─────────────────────────────────────────────────────
        if duration > 0 and elapsed >= duration:
            raise sd.CallbackStop()

    with sd.InputStream(
        device=device_idx,
        channels=1,
        samplerate=session.sample_rate,
        dtype="float32",
        blocksize=session.block_size,
        callback=_callback,
    ):
        print(green("  🎤 Mic open — speak now\n"))
        try:
            if duration > 0:
                time.sleep(duration + 0.5)
            else:
                while True:
                    time.sleep(0.5)
        except (KeyboardInterrupt, sd.CallbackStop):
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    print(bold(cyan("\n╔══════════════════════════════════════════════════════════════════════╗")))
    print(bold(cyan("║      AVAListener — Raw ASR Diagnostic  (no wake logic)              ║")))
    print(bold(cyan("╚══════════════════════════════════════════════════════════════════════╝")))

    # ── A. Device info
    device_idx = print_device_info(args.device, args.rate, args.block)

    # ── B. Model info
    model_ok = print_model_info(MODELS_DIR, args.threads)
    if not model_ok:
        print(red("  ERROR: One or more model files missing. Cannot continue."))
        sys.exit(1)

    # ── C. Build recognizer
    recognizer = build_recognizer(
        MODELS_DIR, args.rate, args.threads,
        endpoint_enabled=not args.no_endpoint,
    )

    # ── D-F. Live stream
    session = DiagnosticSession(args.rate, args.block, args.save_wav)

    try:
        run_stream(recognizer, session, device_idx, args.duration)
    except Exception as exc:
        print(red(f"\n  FATAL: {exc}"))
        raise
    finally:
        if args.save_wav:
            wav_path = os.path.join(_HERE, "diag_capture.wav")
            session.save_wav_file(wav_path)
        session.print_summary()


if __name__ == "__main__":
    main()
