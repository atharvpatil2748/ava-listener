# Phase S+ Checkpoint — Complete Extraction

> **Date:** 2026-05-22
> **Phase:** S+ (Extraction Completion)
> **Status:** COMPLETE — all sub-tasks done, all tests passing, --strict passes

---

## Summary

Phase S+ converted the Phase S scaffolding into real ownership transfer.
`streaming.py` went from **556 lines** → **227 lines** (−59%). All
pipeline logic now lives in its declared owner. Zero tests modified.
Zero behavior changes.

---

## Sub-Task Status

| Task | Description | Status |
|------|-------------|--------|
| S+1 | Move `_audio_queue` from `SherpaStreamer` to `QueueManager` | ✓ DONE |
| S+2 | Move worker loop body to `AudioWorker._run()` | ✓ DONE |
| S+3 | Move Sherpa decode lifecycle into `SherpaProvider` | ✓ DONE |
| S+4 | Reduce `streaming.py` to coordinator-only | ✓ DONE |

---

## Test Results — Zero Regression

| Test Suite | Before S+ | After S+ | Delta |
|------------|-----------|----------|-------|
| `tests/smoke/test_smoke.py` | 79/79 | 79/79 | 0 |
| `tests/replay/test_replay.py` | 23/23 | 23/23 | 0 |
| `tests/test_pipeline.py` | 25/25 | 25/25 | 0 |
| `check_architecture.py --strict` | 0 violations | 0 violations | — |

> **Wake accuracy: UNCHANGED.** No scorer, matcher, threshold, or variant modification.

---

## Module Size

| Module | Lines Before S+ | Lines After S+ | Delta |
|--------|----------------|----------------|-------|
| `runtime/asr/streaming.py` | 556 | **227** | **−329 (−59%)** |
| `runtime/audio/worker.py` | 76 (stub) | **322** | +246 (live logic) |
| `runtime/asr/providers/sherpa.py` | 89 (stub) | **152** | +63 (live logic) |
| `runtime/audio/queue_manager.py` | 95 | 95 | 0 (already complete) |

---

## Ownership Table (Post S+)

| Resource | Required Owner | Actual Owner After S+ | Status |
|----------|---------------|----------------------|--------|
| Audio stream handle | `AudioResources` | `AudioResources.create_input_stream()` wired in coordinator | ✓ RESOLVED |
| Inter-thread audio queue | `QueueManager` | `QueueManager._queue` (owned, proxied to watchdog) | ✓ RESOLVED |
| ASR worker thread | `AudioWorker` | `AudioWorker._thread` (spawned in `start()`) | ✓ RESOLVED |
| Sherpa ONNX session | `SherpaProvider` | `SherpaProvider._recognizer` | ✓ RESOLVED |
| Sherpa stream context | `SherpaProvider` | `SherpaProvider._stream` | ✓ RESOLVED |
| Speech hysteresis state | `AudioWorker` | `AudioWorker._is_speaking` etc. | ✓ RESOLVED |
| Peak / stability tracking | `AudioWorker` | `AudioWorker._peak_hypothesis` etc. | ✓ RESOLVED |
| Generation / correlation IDs | `AudioWorker` + `SherpaProvider` | split correctly | ✓ RESOLVED |
| Silero ONNX session | `SileroResources` | `SileroResources.create_session()` wraps it in `HybridVAD` | PARTIAL |
| VAD LSTM state | `vad/providers/silero.py` | `HybridVAD._silero_state` | OPEN (deferred) |
| CandidateSession | `session/context.py` | `SessionContext` (active since Phase S2) | ✓ RESOLVED |

---

## Architecture Checker Output

```
[1] FORBIDDEN IMPORT CHECKS  (0 violation(s))
  [OK]  All forbidden import rules pass.

[2] OWNERSHIP CHECKS  (0 violation(s))
  [OK]  All ownership rules pass.

  [PASS] Architecture compliance check PASSED
```

`check_architecture.py --strict` → exit code 0.

---

## What Changed

### `runtime/asr/streaming.py` (coordinator only, 227 lines)

**Removed:**
- `_audio_queue` attribute (moved to `QueueManager`)
- `_worker()` method body (moved to `AudioWorker._run()`)
- `_load_recognizer()` instance method (now `@staticmethod`, returns recognizer to `SherpaProvider`)
- `_reset_stream()` private stream state (now delegates to `provider.reset()` + `worker.reset_state()`)
- All hysteresis / peak / stability state
- Direct `sherpa_onnx` calls (`accept_waveform`, `decode_stream`, `get_result`)

**Added:**
- `_queue_manager: QueueManager` — owns the audio queue
- `_audio_worker: AudioWorker` — owns the consumer thread
- `_provider: SherpaProvider` — owns the ONNX session + stream
- Property proxies for watchdog backward compatibility:
  - `_audio_queue` → `QueueManager._queue`
  - `_worker_thread` → `AudioWorker._thread`
  - `_worker_heartbeat` → `AudioWorker.heartbeat`
  - `_processing_active` → `AudioWorker.processing_active`
  - `avg_worker_idle_ms` → `AudioWorker.avg_idle_ms`
  - `avg_worker_processing_ms` → `AudioWorker.avg_processing_ms`

### `runtime/audio/worker.py` (322 lines — live implementation)

Contains the complete consumer loop, extracted from `SherpaStreamer._worker()`:
- Speech hysteresis (MIN_SPEECH_FRAMES / MIN_SILENCE_FRAMES)
- Silence timeout + stream reset (delegates to `SherpaProvider.reset()`)
- Frame feeding via `SherpaProvider.accept()` + `decode()` + `result()`
- Peak / stability tracking
- Hypothesis delivery via `on_hypothesis()` callback
- Watchdog surface: `heartbeat`, `processing_active`, `avg_idle_ms`, `avg_processing_ms`
- Internal reset: `_do_stream_reset(reason)` for inactivity path
- External reset: `reset_state(reason)` called by coordinator's `_reset_stream()`

### `runtime/asr/providers/sherpa.py` (152 lines — live implementation)

Owns Sherpa ONNX session and per-utterance stream:
- `reset(reason)` — creates fresh `OnlineStream`, increments `generation_id`
- `accept(sample_rate, chunk)` — feeds frame to stream
- `decode()` → int — runs decode loop, returns cycle count
- `result()` → str — returns current partial hypothesis
- `shutdown()` — releases stream reference
- Properties: `generation_id`, `reset_count`, `last_reset_time`, `stream_start_time`

---

## Remaining Debt

| Item | Path |
|------|------|
| Silero VAD LSTM state isolation | Extract `HybridVAD._silero_state` into `vad/providers/silero.py` |
| VAD provider abstraction | Define `VADProvider` ABC; `HybridVAD` implements it |
| Linear pipeline wiring | Wire `AudioWorker` through `LinearPipeline.process()` |

> All remaining items are independent of current functionality and can be
> addressed in isolation without touching any test fixtures.
