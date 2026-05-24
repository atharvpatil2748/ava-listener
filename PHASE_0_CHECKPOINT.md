# AVAListener — Phase 0 Rollback Checkpoint
## Baseline Preservation Artifact
**Created:** 2026-05-22  
**Phase:** 0 — Baseline Preservation  
**Status:** ✅ Frozen  

---

## Purpose

This document is the **Phase 0 rollback reference**. It records the exact state of the
engine at the moment Phase 0 was locked. If any future phase destabilizes the runtime,
revert to this state to restore a known-good baseline.

---

## Frozen Files (do not modify without plan approval)

The following files constitute the Phase 0 baseline. Their content is frozen.
Any modification to these files during later phases must be explicitly gated.

### Engine Core

| File | Description |
|------|-------------|
| `core/engine.py` | WakeEngine — orchestrator, EMA, generation gate, cooldown |
| `main.py` | Entry point, stdin command reader |
| `detection/matcher.py` | `best_match()`, `anchor_present()` — matcher logic |
| `detection/variants.py` | Variant index, canonical mapping |
| `confidence/scorer.py` | `compute_confidence()` — confidence computation |
| `decision/cooldown.py` | CooldownGate — 2s post-trigger lockout |
| `audio/buffer.py` | HypothesisBuffer — weighted sliding window |
| `audio/vad.py` | Hybrid VAD (WebRTC + Silero) |
| `asr/sherpa_stream.py` | Sherpa-ONNX streaming ASR wrapper |
| `integration/stdout_bridge.py` | JSON event emitter to Node.js |
| `runtime/state_machine.py` | RuntimeStateMachine |
| `runtime/watchdog.py` | RuntimeWatchdog |
| `telemetry/collector.py` | TelemetryCollector |

### Configuration (frozen schema, not values)

| File | Description |
|------|-------------|
| `config/settings.py` | All tunable parameters + WAKEWORDS |
| `config/schema.py` | Config schema definitions |
| `config/validation.py` | Config validation |

### Models (content frozen, SHA256 in manifest)

| Model | SHA256 (first 16 chars) |
|-------|------------------------|
| `models/encoder.onnx` | `5022b2eca5b19d1b…` |
| `models/decoder.onnx` | `780c63ee94c7cfa3…` |
| `models/joiner.onnx` | `abd5e30f3f16fc51…` |
| `models/tokens.txt` | `49e3c264659…` |
| `models/silero_vad.onnx` | `1a153a22f450…` |

Full hashes in `models_manifest.json`.

---

## Dependency Snapshot

```
Python:             3.10.10
cffi:               2.0.0
coloredlogs:        15.0.1
flatbuffers:        25.12.19
humanfriendly:      10.0
jellyfish:          1.2.1
mpmath:             1.3.0
numpy:              2.2.6
onnxruntime:        1.23.2
packaging:          26.2
protobuf:           7.34.1
pycparser:          3.0
pyreadline3:        3.5.4
RapidFuzz:          3.14.5
sherpa-onnx:        1.13.2
sherpa-onnx-core:   1.13.2
sounddevice:        0.5.5
sympy:              1.14.0
webrtcvad-wheels:   2.0.14
```

Full lockfile: `requirements.lock.txt`

---

## Startup Signals (required at every phase gate)

All five must appear within 15 seconds of `python main.py`:

| Signal | Source | Substring |
|--------|--------|-----------|
| Sherpa model loaded | stderr | `Model loaded` |
| Mic opened | stderr | `Mic open` |
| Engine started | stderr | `AVAListener engine started` |
| status=ready | stdout | `"ready"` |
| Heartbeat | stdout | `"heartbeat"` |

Verified by: `python scripts/verify_startup.py`

---

## Known Architecture State (Phase 0)

### What works
- Microphone capture → audio queue → hybrid VAD → Sherpa ASR → hypothesis stream
- Matcher: anchor gate (Jaro-Winkler + variant lookup) + fuzzy scorer (RapidFuzz)
- EMA confidence smoothing (asymmetric rise/decay α)
- Generation gate (one wake per utterance boundary)
- Cooldown gate (2s post-trigger lockout)
- Multi-wakeword support (WAKEWORDS list in settings.py)
- stdout JSON event emission for Node.js IPC
- stdin command protocol (pause/resume/suppress)
- Heartbeat emission every 5s
- Per-phrase threshold lookup
- Candidate session lifecycle tracking
- Telemetry collection to disk (optional)
- Runtime state machine + watchdog

### Known technical debt (tracked for future phases)
- Mixed concerns: audio, ASR, matching, control, diagnostics all in one process
- No formal supervisor layer — crashes are unrecovered
- Transport via stdout/stdin: fragile, no schema versioning
- WAKEWORDS hardcoded in `config/settings.py` — violates generic engine identity rule (Phase 0.5 fixes this)
- No formal lifecycle FSM at kernel level
- No structured logging with correlation IDs
- No WebSocket transport

### Rollback procedure

If any phase destabilizes the engine:

1. **Stop** all development on the failing phase.
2. **Revert** all modified files to their Phase 0 state using git or file backup.
3. **Run** smoke tests: `python tests/smoke/test_smoke.py`
4. **Run** replay tests: `python tests/replay/test_replay.py`
5. **Run** startup check: `python scripts/verify_startup.py`
6. **Run** pipeline test: `python tests/test_pipeline.py`
7. Document the regression and root cause before resuming.

> A rollback is **always preferred** over debugging a broken engine against a live microphone.
> The Phase 0 baseline is the safety net. Trust it.

---

## Regression Firewall

All four test targets must pass at 100% before any phase gate:

```
python tests/smoke/test_smoke.py          → all checks pass
python tests/replay/test_replay.py        → all fixtures pass
python tests/test_pipeline.py             → all 3 sections pass
python scripts/verify_startup.py          → RESTORED AND VERIFIED
```

---

*Phase 0 checkpoint locked. Do not modify this document except to add future phase records below.*

---

## Phase Completion Log

| Phase | Completed | Exit Criteria Met | Notes |
|-------|-----------|-------------------|-------|
| Phase 0 | 2026-05-22 | ✅ Yes | Baseline frozen. Smoke + replay + pipeline + startup all passing. |
