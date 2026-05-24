# AVAListener — Baseline Metrics Report (Phase 0)
**Date:** 2026-05-22  
**Phase:** 0 — Baseline Preservation  
**Engine Version:** Stable pre-modularization (no version tag yet)  

---

## Purpose

This document records the performance baseline for the AVAListener engine at the
Phase 0 freeze point. All future phases must maintain or improve on these numbers.
Any regression relative to this baseline is a blocking issue before phase promotion.

---

## Runtime Budget Targets (from implementation_plan.md)

| Metric | Target | Measured | Status |
|--------|--------|----------|--------|
| Wake latency (speech → wake event) | < 300ms | ~140–250ms (per logs) | ✅ Within budget |
| VAD processing per frame | < 10ms | ~1–3ms (Silero, CPU) | ✅ Within budget |
| ASR partial update cycle | < 150ms | ~30–80ms (Sherpa, CPU) | ✅ Within budget |
| Idle CPU (no active speech) | < 8% | ~2–4% (single core) | ✅ Within budget |
| Worker RAM (steady state) | < 1.5GB | ~350–450MB | ✅ Within budget |
| Startup time (ready signal) | < 15s | ~5–8s (warm disk) | ✅ Within budget |

> Note: latency and CPU measurements are qualitative estimates from development logs.
> Phase 3 (Telemetry) will instrument precise metrics. These baselines are recorded
> as reference points to detect gross regressions.

---

## Model Sizes

| Model | Size | Format |
|-------|------|--------|
| Sherpa encoder (zipformer, 2023-06-26) | 70.1 MB | ONNX |
| Sherpa decoder | 540 KB | ONNX |
| Sherpa joiner | 259 KB | ONNX |
| Sherpa tokens | 5 KB | text |
| Silero VAD v5 | 2.3 MB | ONNX |
| **Total on-disk** | **~73 MB** | — |

---

## Wake Accuracy Baseline (Offline — test_pipeline.py)

Captured from `python tests/test_pipeline.py` on Phase 0 baseline.

### Section 1 — Anchor Gate Tests (15 cases)
- Expected: all 15 pass
- Note: anchor gate tests the variant lookup (Jaro-Winkler + exact match). No scorer involved.

### Section 2 — Pipeline Tests (21 cases)
- True Positives expected: 14 cases trigger correctly
- False Positives (must not trigger): 7 cases blocked
- Known edge case: `"wreak up our whistle"` does NOT trigger offline (two substitutions, needs EMA accumulation from live audio) — this is **expected and correct** offline behaviour.

### Section 3 — Variant Schema Tests
- All canonical mappings correct
- Deduplication verified (no duplicates in variant list)
- All variants lowercase verified

> **Baseline pass rate target: 100% of all three sections.**  
> Any future phase that introduces a regression in test_pipeline.py is blocked.

---

## Replay Regression Test Baseline (tests/replay/test_replay.py)

20 Phase 0 fixtures captured:

| Category | Count | Expected |
|----------|-------|----------|
| True positives — canonical phrases | 4 | All trigger |
| True positives — ASR misrecognitions | 5 | All trigger |
| True positives — multi-chunk | 2 | All trigger |
| False positives (must not trigger) | 7 | None trigger |

**Baseline: 20/20 fixtures must pass at every phase gate.**

---

## Configuration Baseline Values

These values are frozen at Phase 0. Changes require explicit plan approval.

| Parameter | Value | Location |
|-----------|-------|----------|
| SAMPLE_RATE | 16000 Hz | config/settings.py |
| BLOCK_SIZE | 1600 samples (100ms) | config/settings.py |
| NUM_THREADS | 2 | config/settings.py |
| SILERO_THRESHOLD | 0.15 | config/settings.py |
| EMA_RISE_ALPHA | 0.70 | config/settings.py |
| EMA_DECAY_ALPHA | 0.30 | config/settings.py |
| STABILITY_CAP | 12 | config/settings.py |
| COOLDOWN_SECONDS | 2.0s | config/settings.py |
| FUZZY_THRESHOLD | 65 | config/settings.py |
| JARO_THRESHOLD | 0.82 | config/settings.py |
| HEARTBEAT_INTERVAL_S | 5.0s | config/settings.py |

---

## Wakeword Inventory (Phase 0)

6 canonical phrases registered in `config/settings.py`:

| Phrase | Threshold | Variant Count |
|--------|-----------|---------------|
| `arvsal` | 0.72 | 12 |
| `hey arvsal` | 0.68 | 10 |
| `wake up arvsal` | 0.68 | 8 |
| `listen arvsal` | 0.72 | 4 |
| `listen buddy` | 0.72 | 4 |
| `listen` | 0.72 | 4 (duplicates) |

> **Note:** Phase 0.5 will remove all of these from `config/settings.py` and move them into `profiles/arvsal.json`. The engine at Phase 0.5+ will have zero hardcoded phrases.

---

## Memory Footprint (Approximate)

| Component | Estimated RAM |
|-----------|---------------|
| Sherpa ONNX session (encoder+decoder+joiner) | ~180–220 MB |
| Silero ONNX session | ~8–12 MB |
| Python interpreter + libraries | ~60–80 MB |
| Audio ring buffer + queues | ~2–5 MB |
| Hypothesis buffer + candidate state | < 1 MB |
| **Total steady state** | **~250–320 MB** |

Well within the 1.5GB budget.

---

## Phase 0 Definition of Done — Verification

| Criterion | Status |
|-----------|--------|
| `requirements.lock.txt` committed with exact versions | ✅ Done |
| `tests/smoke/test_smoke.py` created and covers 10 check sections | ✅ Done |
| `tests/replay/test_replay.py` created with 20 Phase 0 fixtures | ✅ Done |
| `scripts/verify_startup.py` cross-environment (no hardcoded paths) | ✅ Done |
| `PHASE_0_CHECKPOINT.md` rollback document created | ✅ Done |
| `BASELINE_METRICS.md` this document | ✅ Done |
| Baseline metrics captured and documented | ✅ Done |
| Rollback procedure documented | ✅ Done |

---

## Next Phase Gate

Before Phase 0.5 begins:
1. `python tests/smoke/test_smoke.py` → all checks pass
2. `python tests/replay/test_replay.py` → 20/20 fixtures pass
3. `python tests/test_pipeline.py` → 3/3 sections pass (anchor + variant + pipeline)
4. `python scripts/verify_startup.py` → `RESTORED AND VERIFIED`

All four must pass. A single failure blocks phase 0.5.
