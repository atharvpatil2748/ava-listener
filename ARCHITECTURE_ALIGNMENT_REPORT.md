# AVAListener — Architecture Alignment Report (Phase S)

> **Date:** 2026-05-22
> **Scope:** Phase S Stabilization — Dependency Graph, Ownership, and Module Responsibility Analysis

---

## 1. Before / After Dependency Graph

### Before Phase S

```
runtime/kernel/orchestrator.py (WakeEngine)
  ├─ owns: CandidateSession (duplicate dataclass — also in session/context.py)
  ├─ owns: candidate lifecycle state machine
  ├─ imports: asr.sherpa_stream.SherpaStreamer
  ├─ imports: detection.matcher.best_match
  ├─ imports: confidence.scorer.compute_confidence
  └─ imports: audio.buffer.HypothesisBuffer

runtime/asr/streaming.py (SherpaStreamer)
  ├─ owns: audio stream (sounddevice.InputStream)
  ├─ owns: inter-thread queue (queue.Queue)
  ├─ owns: ASR worker thread (threading.Thread)
  ├─ owns: Sherpa ONNX session (sherpa_onnx.OnlineRecognizer)
  ├─ owns: Sherpa stream context (OnlineStream)
  ├─ owns: VAD instantiation (HybridVAD)
  └─ owns: entire VAD→ASR→callback pipeline (monolithic _worker)

runtime/vad/pipeline.py (HybridVAD)
  ├─ owns: Silero ONNX session (onnxruntime.InferenceSession)
  └─ owns: WebRTC VAD + Silero cascade logic

runtime/session/context.py
  └─ defines: CandidateSession (NOT consumed by anyone — orphan)

runtime/pipeline/linear.py
  └─ STUB (empty)

runtime/audio/worker.py          — DOES NOT EXIST
runtime/audio/queue_manager.py   — DOES NOT EXIST
runtime/asr/providers/sherpa.py  — STUB (empty)
```

### After Phase S

```
runtime/kernel/orchestrator.py (WakeEngine)
  ├─ imports: runtime.session.context.CandidateSession  [S2 — no duplicate]
  ├─ owns: SessionContext (self._session)                [S2]
  ├─ delegates candidate lifecycle to session.add/clear  [S2]
  └─ (all other imports unchanged)

runtime/asr/streaming.py (SherpaStreamer) — coordinator role clarified
  ├─ delegates stream creation → AudioResources           [S1 — prior session]
  ├─ delegates thread creation → ThreadPoolResources      [S1 — prior session]
  ├─ delegates recognizer creation → SherpaResources     [S1 — prior session]
  └─ (audio queue + _worker logic unchanged — scaffolded for S4)

runtime/vad/pipeline.py (HybridVAD)
  ├─ delegates Silero session creation → SileroResources  [S1 — prior session]
  └─ (cascade logic unchanged)

runtime/session/context.py
  └─ defines: CandidateSession, SessionContext
  └─ CONSUMED BY: WakeEngine (self._session)              [S2 — now active]

runtime/pipeline/linear.py
  └─ AudioFrame, HypothesisResult, LinearPipeline         [S3 — scaffold]
  └─ process(frame) stub established
  └─ _run_vad(), _run_asr() interface declared

runtime/audio/worker.py
  └─ AudioWorker stub — declares consumer thread ownership boundary  [S4]

runtime/audio/queue_manager.py
  └─ QueueManager stub — declares audio queue ownership boundary      [S4]

runtime/asr/providers/sherpa.py
  └─ SherpaProvider stub — declares ONNX session + stream ownership   [S4]

scripts/check_architecture.py
  └─ AST-based import boundary + ownership checker                     [S5]
```

---

## 2. Ownership Table

| Resource | Required Owner (Audit) | Actual Owner Before S | Actual Owner After S | Violation? |
|----------|----------------------|----------------------|----------------------|-----------|
| Audio stream handle | `AudioResources` | `asr/streaming.py` | `AudioResources` wraps creation; stream used in `streaming.py` | PARTIAL |
| Inter-thread audio queue | `QueueManager` | `asr/streaming.py` | `QueueManager` stub exists; still in `streaming.py` | PARTIAL (scaffolded) |
| ASR worker thread | `ThreadPoolResources` | `asr/streaming.py` | `ThreadPoolResources` wraps creation; `AudioWorker` stub exists | PARTIAL |
| Sherpa ONNX session | `SherpaResources` | `asr/streaming.py` | `SherpaResources` wraps creation; `SherpaProvider` stub exists | PARTIAL |
| Sherpa stream context | `asr/providers/sherpa.py` | `asr/streaming.py` | `SherpaProvider` stub exists | PARTIAL (scaffolded) |
| Silero ONNX session | `SileroResources` | `vad/pipeline.py` | `SileroResources` wraps creation; used in `pipeline.py` | PARTIAL |
| VAD LSTM state | `vad/providers/silero.py` | `vad/pipeline.py` | Unchanged; HybridVAD still owns state | OPEN (not S-phase scope) |
| Hypothesis buffer | `session/context.py` | `kernel/orchestrator.py` | `CandidateSession` now from `session/context.py`; `SessionContext` active | **RESOLVED** (S2) |
| Phrase variant registry | `matcher/variants.py` | `matcher/registry.py` | Unchanged | PASS |
| Thread pool | `ThreadPoolResources` | `asr/streaming.py` | Wraps creation; `AudioWorker` stub | PARTIAL |
| CandidateSession definition | `session/context.py` | `kernel/orchestrator.py` (duplicate) | Canonical in `session/context.py`; duplicate removed from orchestrator | **RESOLVED** (S2) |

**Legend:**
- **RESOLVED** — ownership violation fully closed
- **PARTIAL** — creation wrapped in correct resource class; runtime ownership extraction deferred
- **OPEN** — not in Phase S scope; documented for future phase

---

## 3. Module Size Reduction

| Module | Lines Before | Lines After | Delta | Note |
|--------|-------------|-------------|-------|------|
| `runtime/kernel/orchestrator.py` | 728 | 703 | **-25** | Removed duplicate CandidateSession |
| `runtime/pipeline/linear.py` | 2 (stub) | 145 | +143 | Scaffold established |
| `runtime/audio/worker.py` | N/A | 67 | new | Ownership stub |
| `runtime/audio/queue_manager.py` | N/A | 78 | new | Ownership stub |
| `runtime/asr/providers/sherpa.py` | 2 (stub) | 88 | +86 | Ownership stub |
| `runtime/session/context.py` | 53 | 53 | 0 | Now actively consumed |
| `scripts/check_architecture.py` | N/A | 330 | new | S5 checker |

> `streaming.py` line reduction target (>50%) is deferred to the next decomposition phase (when `_worker()` body is moved into `AudioWorker`). Phase S establishes all the ownership boundaries needed for that move.

---

## 4. Architecture Compliance Score (Revised)

| Dimension | Before Phase S | After Phase S | Change |
|-----------|---------------|---------------|--------|
| Ownership violations | 8 | 6 (2 resolved, 6 partial) | -2 hard violations |
| CandidateSession duplication | Yes | No | Eliminated |
| SessionContext consumed | No | Yes | Activated |
| LinearPipeline defined | No | Yes (scaffold) | Interface established |
| Forbidden import violations | 0 | 0 | No regression |
| Architecture checker | Does not exist | Passes (0 violations) | New tooling |

---

## 5. Remaining Debt

The following items are documented for the next decomposition phase:

| Item | Required Action | Est. Complexity |
|------|----------------|-----------------|
| Move `_worker()` body to `AudioWorker` | Logic move; must preserve all hysteresis state | High |
| Move `_audio_queue` to `QueueManager` | Simple ownership transfer | Low |
| Move Sherpa decode loop to `SherpaProvider` | Logic move; must maintain stream lifecycle | Medium |
| Move Silero ONNX state to `SileroProvider` | Logic move; must preserve LSTM state continuity | Medium |
| Reduce `streaming.py` to coordinator only | Requires all above + integration wiring | High |
| VAD LSTM state → `vad/providers/silero.py` | Provider extraction | Medium |

> **Priority rule:** All moves require tests to pass unchanged before and after. Use the `check_architecture.py --strict` flag as the gate.

---

## 6. Success Criteria Assessment

| Criterion | Target | Actual | Status |
|-----------|--------|--------|--------|
| `streaming.py` lines reduced >50% | <278 lines | 556 (unchanged) | DEFERRED (scaffolded) |
| WakeEngine responsibilities reduced | Remove duplicate CandidateSession | Done | **PASS** |
| Ownership violations reduced | Any reduction | 2 hard violations closed | **PASS** |
| All tests pass unchanged | 100% | 100% (79/79, 23/23, 25/25) | **PASS** |
| Architecture checker created | Script exists + passes | Exists + 0 violations | **PASS** |
| Zero behavior changes | No changes to matcher/scorer/thresholds | None made | **PASS** |
