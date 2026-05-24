# ARCHITECTURE_FREEZE_v1 — AVAListener Runtime

> **Freeze Date:** 2026-05-22
> **Version:** 1.0
> **Status:** FROZEN — no ownership changes permitted without versioning this document

---

## 1. Purpose

This document canonically records the **post-Phase S+ architecture** of the
AVAListener runtime. It serves as the contractual reference for:

- All future refactoring decisions
- CI architecture checker rules (`scripts/check_architecture.py`)
- Code review: any edit that violates a boundary listed here requires a new
  freeze version
- Onboarding: the authoritative description of module responsibilities

---

## 2. Module Ownership Map

### 2.1 Tier 1 — Core Subsystems

| Module | Owner | Owns | Must NOT own |
|--------|-------|------|-------------|
| `runtime/asr/streaming.py` | `SherpaStreamer` | Coordinator: wires QueueManager, AudioWorker, SherpaProvider, HybridVAD | Any pipeline logic, audio frames, ONNX sessions, threads |
| `runtime/audio/queue_manager.py` | `QueueManager` | `queue.Queue` instance, enqueue/dequeue API, depth diagnostics | Any ASR or VAD state |
| `runtime/audio/worker.py` | `AudioWorker` | Consumer thread, speech hysteresis, peak/stability tracking, silence timeout, on_hypothesis delivery | ONNX sessions, audio stream handles |
| `runtime/asr/providers/sherpa.py` | `SherpaProvider` | `OnlineRecognizer`, `OnlineStream`, `generation_id`, `reset_count` | Queue, threads, VAD state |
| `runtime/vad/pipeline.py` | `HybridVAD` | WebRTC VAD + Silero cascade, VAD FSM | ONNX session creation (delegated to SileroResources) |
| `runtime/kernel/orchestrator.py` | `WakeEngine` | Detection pipeline, candidate lifecycle (via SessionContext), cooldown, transport | Audio streaming, ASR, VAD logic |
| `runtime/session/context.py` | `SessionContext` | `CandidateSession` dataclass (canonical), session window | Any audio or detection logic |
| `runtime/pipeline/linear.py` | `LinearPipeline` | AudioFrame, HypothesisResult, process() interface | Any live logic (Phase S scaffold — see §6) |

### 2.2 Tier 2 — Resource Factories

| Module | Owner | Creates |
|--------|-------|---------|
| `runtime/resources/audio_resources.py` | `AudioResources` | `sounddevice.InputStream` |
| `runtime/resources/asr_resources.py` | `SherpaResources` | `sherpa_onnx.OnlineRecognizer` |
| `runtime/resources/vad_resources.py` | `SileroResources` | `onnxruntime.InferenceSession` (Silero model) |
| `runtime/resources/pools.py` | `ThreadPoolResources` | Thread pools |

### 2.3 Tier 3 — Detection Stack (stateless)

| Module | Responsibility |
|--------|----------------|
| `detection/matcher.py` | `best_match(window)` — top-level matcher |
| `detection/variants.py` | `get_canonical()`, `get_variants()` |
| `confidence/scorer.py` | `compute_confidence(score, window_len, hit_count)` |
| `decision/cooldown.py` | `CooldownGate` — per-phrase trigger rate limiting |
| `runtime/matcher/registry/` | Profile-driven phrase registry |

---

## 3. Data Flow (Frozen)

```
sounddevice callback
    |
    v  (float32 chunk, BLOCK_SIZE samples)
QueueManager.enqueue(chunk)
    |
    v  (AudioWorker._run() -- consumer thread)
HybridVAD.process_chunk(chunk)  --> bool: speech?
    |
    v
SherpaProvider.accept(SAMPLE_RATE, chunk)
SherpaProvider.decode()
SherpaProvider.result()  --> str: partial hypothesis
    |
    v
on_hypothesis(text, stability, peak, generation_id, correlation_id)
    |
    v  (WakeEngine._on_hypothesis() -- engine thread)
best_match(window)  --> (score, phrase, variant)
compute_confidence(score, window_len, hit_count)  --> float
    |
    v  (if conf >= threshold and cooldown clear)
WakeEngine._fire_wake(phrase, variant, conf)
    |
    v
stdout JSON event  { event: "wake", phrase: "...", ... }
```

---

## 4. Forbidden Import Rules (enforced by check_architecture.py)

| Source Package | Forbidden Import | Rationale |
|---------------|-----------------|-----------|
| `runtime.asr` | `runtime.matcher` | ASR must not know about wake detection |
| `runtime.asr` | `runtime.vad` | ASR must not gate on VAD internally |
| `runtime.vad` | `runtime.matcher` | VAD must not know about wake detection |
| `runtime.asr.providers` | `runtime.kernel.orchestrator` | Providers must not call up to orchestrator |
| `runtime.vad.providers` | `runtime.kernel.orchestrator` | Providers must not call up to orchestrator |

To add a new forbidden rule, update both this document (§4) and
`scripts/check_architecture.py` `FORBIDDEN_IMPORTS`.

---

## 5. Watchdog Surface Contract

`RuntimeWatchdog` accesses these attributes on `SherpaStreamer`.
These are **compatibility properties** — they must not be removed
or renamed without a freeze version bump:

| Property | Type | Delegates To |
|----------|------|-------------|
| `_audio_queue.qsize()` | `queue.Queue` proxy | `QueueManager._queue` |
| `_worker_thread` | `threading.Thread` | `AudioWorker._thread` |
| `_worker_heartbeat` | `float` | `AudioWorker.heartbeat` |
| `_processing_active` | `bool` | `AudioWorker.processing_active` |
| `avg_worker_idle_ms` | `float` | `AudioWorker.avg_idle_ms` |
| `avg_worker_processing_ms` | `float` | `AudioWorker.avg_processing_ms` |
| `_vad` | `HybridVAD` | direct attribute |
| `_reset_stream(reason)` | method | delegates to `SherpaProvider.reset()` + `AudioWorker.reset_state()` |

---

## 6. Frozen Scaffold Modules (Phase S)

These modules exist as scaffolding. Their **interfaces are frozen**;
their **implementations are stubs pending future extraction**:

| Module | Interface | Implementation |
|--------|-----------|----------------|
| `runtime/pipeline/linear.py` | `AudioFrame`, `HypothesisResult`, `LinearPipeline.process()` | Stub — `process()` returns None |
| `runtime/pipeline/linear.py::_run_vad()` | `(frame) -> bool` | Raises `NotImplementedError` |
| `runtime/pipeline/linear.py::_run_asr()` | `(frame) -> str` | Raises `NotImplementedError` |

These stubs must not be deleted. Their interfaces define the contract for
the next extraction phase.

---

## 7. Remaining Debt (Acknowledged)

| Item | Location | Severity | Target Phase |
|------|----------|----------|-------------|
| Silero VAD LSTM state isolation | `vad/pipeline.py._silero_state` | Medium | Future |
| `HybridVAD` provider abstraction | `vad/pipeline.py` | Medium | Future |
| `LinearPipeline.process()` implementation | `pipeline/linear.py` | Low | Future |
| VAD cascade logic extraction | `vad/pipeline.py` | Low | Future |

These items are **not** violations of the current freeze — they are
documented debt to be addressed in a future phase.

---

## 8. Validation Results (Freeze Baseline)

All validation tasks completed 2026-05-22. Results are the contractual
baseline — any future phase must preserve these numbers exactly.

| Task | Metric | Baseline |
|------|--------|----------|
| F1 Runtime Stress | Worker deaths (60s) | 0 |
| F1 Runtime Stress | Queue overflow events | 0 |
| F2 Memory Stability | Memory trend | STABLE (+0.108 MB/min) |
| F2 Memory Stability | Memory delta over 60s | < 1 MB |
| F3 Wake Regression | Smoke suite | 79/79 PASS |
| F3 Wake Regression | Replay suite | 23/23 PASS |
| F3 Wake Regression | Pipeline suite | 25/25 PASS |
| F3 Wake Regression | Total | 127/127 PASS |
| F4 Lifecycle Stress | Cycles passed | 99/100+ |
| F4 Lifecycle Stress | Orphan threads | 0 |
| F4 Lifecycle Stress | Engine errors | 0 |
| Architecture Checker | Forbidden import violations | 0 |
| Architecture Checker | Ownership violations | 0 |

> **Detailed reports:** `MEMORY_STABILITY_REPORT.md`, `WAKE_REGRESSION_REPORT.md`,
> `LIFECYCLE_STRESS_REPORT.md`

---

## 9. Freeze Rules

Any code change that touches a frozen boundary (§2–§5) MUST:

1. Update this document with a new version number
2. Re-run `python scripts/check_architecture.py --strict` and confirm 0 violations
3. Re-run all three test suites and confirm 127/127 PASS
4. Update `ARCHITECTURE_ALIGNMENT_REPORT.md` with the new ownership table

Changes that do NOT require a version bump:
- Bug fixes inside a module that do not change its public interface
- Log message changes
- Comment/docstring changes
- Performance optimizations with no interface change
- New tests

---

## 10. Key Files Reference

| File | Role |
|------|------|
| `ARCHITECTURE_FREEZE_v1.md` | This document (canonical reference) |
| `ARCHITECTURE_AUDIT_V2.md` | Original audit that identified the drift |
| `ARCHITECTURE_ALIGNMENT_REPORT.md` | Before/after dependency graph |
| `PHASE_S_CHECKPOINT.md` | Phase S completion record |
| `PHASE_S_PLUS_CHECKPOINT.md` | Phase S+ completion record |
| `scripts/check_architecture.py` | Automated boundary checker |
| `MEMORY_STABILITY_REPORT.md` | F2 memory leak validation |
| `WAKE_REGRESSION_REPORT.md` | F3 wake regression validation |
| `LIFECYCLE_STRESS_REPORT.md` | F4 lifecycle stress validation |
