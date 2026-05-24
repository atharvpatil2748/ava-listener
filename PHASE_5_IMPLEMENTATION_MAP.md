# PHASE_5_IMPLEMENTATION_MAP.md

> **Status: PENDING LOCK** (all P5-BLOCKs resolved, gate verification passed)
> **Date: 2026-05-22**

---

## Overview

Phase 5 adds observability infrastructure **around** the runtime engine.
The hot path (matcher, VAD, ASR, wake thresholds) is **never touched**.
Pattern: copy → wrap → test → verify → refactor.

---

## New Files — Complete Map

### `runtime/logging/context.py`
| Field | Value |
|-------|-------|
| **Owner** | Context management only |
| **Imports** | `uuid` (stdlib) |
| **Dependencies** | None |
| **Public API** | `LogContext.new_session()`, `set_session()`, `set_correlation()`, `set_subsystem()`, `get()`, `clear()` |
| **Touched existing** | None |

---

### `runtime/logging/formatters.py`
| Field | Value |
|-------|-------|
| **Owner** | Formatter logic only |
| **Imports** | `json`, `logging`, `time` (stdlib); `LogContext` from `context.py` |
| **Dependencies** | `runtime.logging.context` |
| **Public API** | `StructuredFormatter(json_mode=bool)` — dual-mode JSON/text formatter with `schema_version: 1` |
| **Touched existing** | None |

---

### `runtime/logging/sinks.py`
| Field | Value |
|-------|-------|
| **Owner** | Sink abstractions only |
| **Imports** | `logging`, `os`, `sys`, `abc` (stdlib); `StructuredFormatter` from `formatters.py` |
| **Dependencies** | `runtime.logging.formatters` |
| **Public API** | `LogSink` (ABC), `ConsoleSink`, `FileSink(path)`, `NullSink` |
| **Touched existing** | None |

---

### `runtime/logging/logger.py`
| Field | Value |
|-------|-------|
| **Owner** | Logger construction only |
| **Imports** | `logging` (stdlib); `ConsoleSink`, `FileSink` from `sinks.py` |
| **Dependencies** | `runtime.logging.sinks` |
| **Public API** | `configure_runtime_logging(level, file_path, json_console)`, `get_runtime_logger(name)` |
| **Touched existing** | None — does NOT replace `utils/logger.py` (which re-exports from `runtime/telemetry/logging.py`) |

> **CRITICAL**: `utils/logger.py` re-exports from `runtime/telemetry/logging.py`.
> `runtime/logging/logger.py` is a Phase 5 *addition* for future SDK use — not a runtime replacement.

---

### `runtime/timing/clock.py`
| Field | Value |
|-------|-------|
| **Owner** | Authoritative time source |
| **Imports** | `time` (stdlib) |
| **Dependencies** | None |
| **Public API** | `now_ns()`, `now_s()`, `monotonic()`, `uptime_s()`, `RuntimeClock` singleton |
| **Touched existing** | None |

---

### `runtime/timing/latency.py`
| Field | Value |
|-------|-------|
| **Owner** | Pipeline stage latency tracking |
| **Imports** | `time`, `warnings`, `dataclasses` (stdlib) |
| **Dependencies** | None |
| **Public API** | `PIPELINE_STAGES`, `STAGE_INTERVALS`, `LatencyTracker(correlation_id)`, `RollingLatency(label, window)` |
| **Touched existing** | None |

**Canonical stages (enforced):**

| Stage | Description |
|-------|-------------|
| `capture_to_queue` | Audio chunk lands in audio queue |
| `vad` | VAD decision completes |
| `asr` | ASR partial/final hypothesis emitted |
| `matcher` | Matcher scores computed |
| `wake_total` | Wake event fired (end-to-end boundary) |

---

### `runtime/health/signals.py`
| Field | Value |
|-------|-------|
| **Owner** | Health signal definitions and normalization |
| **Imports** | `dataclasses` (stdlib) |
| **Dependencies** | None |
| **Public API** | `HEALTH_SIGNAL_MAP`, `SignalDefinition`, `HealthSignals`, `compute_signals(metrics)` |
| **Touched existing** | None |

**`HEALTH_SIGNAL_MAP` (explicit — no hidden magic):**

| Signal | Metric Key | Normalizer Basis | Description |
|--------|-----------|-----------------|-------------|
| `queue_overruns` | `queue_depth` | ÷ 100 | Audio queue saturation |
| `vad_lag` | `reset_count` | ÷ 20 | ASR resets as lag proxy |
| `memory_pressure` | `memory_usage_mb` | ÷ 2048 | RSS vs 2 GB ceiling |
| `restart_frequency` | `restart_count` | ÷ 5 | Subsystem restart count |
| `transport_latency` | `transport_latency_ms` | ÷ 500 | Round-trip vs 500ms |
| `dropped_wake_candidates` | `telemetry_drop_count` | ÷ 500 | Telemetry drops |

---

### `runtime/health/scorer.py`
| Field | Value |
|-------|-------|
| **Owner** | Health score computation |
| **Imports** | `typing` (stdlib) |
| **Dependencies** | `runtime.health.signals` |
| **Public API** | `SIGNAL_WEIGHTS`, `compute_health_score(signals)`, `score_from_metrics(metrics)` |
| **Touched existing** | None |

**`SIGNAL_WEIGHTS` (explicit, sum = 1.0):**

| Signal | Weight | Rationale |
|--------|--------|-----------|
| `queue_overruns` | 0.20 | Audio overruns degrade ASR quality |
| `vad_lag` | 0.15 | Resets indicate pipeline lag |
| `memory_pressure` | 0.20 | OOM is high-impact |
| `restart_frequency` | 0.25 | Frequent restarts = unstable |
| `transport_latency` | 0.10 | Degrades UX, not correctness |
| `dropped_wake_candidates` | 0.10 | Any drop = bug |

---

### `runtime/health/reporter.py`
| Field | Value |
|-------|-------|
| **Owner** | Health report formatting |
| **Imports** | `copy` (stdlib) |
| **Dependencies** | `runtime.health.signals`, `runtime.health.scorer` |
| **Public API** | `HealthReporter(metrics_collector, subsystem_fsms).get_report()` |
| **Touched existing** | None |

---

### `runtime/debug/crash_snapshot.py`
| Field | Value |
|-------|-------|
| **Owner** | Crash state capture |
| **Imports** | `json`, `os`, `time`, `psutil` (optional) |
| **Dependencies** | `runtime.timing.clock`, `runtime.logging.context` |
| **Public API** | `CrashSnapshot(engine, output_dir).capture(reason)` |
| **Touched existing** | None — consumes only exported contracts |

**P5-BLOCK-004 contract requirements:**

| Data | Source |
|------|--------|
| ASR/Audio/VAD state | `streamer.export_debug_state()` |
| Subsystem FSM states | `.state.value` (public enum) |
| Metrics | `engine.metrics_collector.get_all_metrics()` |
| Watchdog metrics | `engine._watchdog.watchdog_metrics` |

---

### `scripts/check_clock_usage.py`
| Field | Value |
|-------|-------|
| **Owner** | Pre-phase gate enforcement |
| **Imports** | `os`, `sys` (stdlib) |
| **Dependencies** | None |
| **Public API** | CLI: `python scripts/check_clock_usage.py` → exit 0 (PASS) or exit 1 (FAIL with violations) |
| **Touched existing** | None |

---

## Touched Existing Files

| File | Change | Reason |
|------|--------|--------|
| `runtime/asr/streaming.py` | Added `export_debug_state()` method | P5-BLOCK-004: CrashSnapshot contract |
| `runtime/vad/pipeline.py` | Added `export_debug_state()` method | P5-BLOCK-004: CrashSnapshot contract |
| `runtime/kernel/orchestrator.py` | Added Phase 5 imports + `MetricsCollector`, `HealthReporter`, `CrashSnapshot`, `LogContext` wiring + `getHealth()`, `getMetrics()`, `getDiagnostics()`, `getManifest()` | Phase 5 diagnostics API |
| `utils/logger.py` | Restored to re-export from `runtime/telemetry/logging.py` | Regression fix — wrong import path |

---

## Test Coverage

| Test | File | Result |
|------|------|--------|
| P5-BLOCK-001: module ownership | `test_observability.py` | 9/9 PASS |
| P5-BLOCK-003: explicit stages | `test_observability.py` | 9/9 PASS |
| P5-BLOCK-005: signal map | `test_observability.py` | 33/33 PASS |
| RuntimeClock | `test_observability.py` | 4/4 PASS |
| LatencyTracker / RollingLatency | `test_observability.py` | 7/7 PASS |
| LogContext + Formatter | `test_observability.py` | 10/10 PASS |
| Health Scorer | `test_observability.py` | 4/4 PASS |
| MetricsCollector | `test_observability.py` | 9/9 PASS |
| **Total observability** | | **80/80 PASS** |
| Smoke suite | `test_smoke.py` | **79/79 PASS** |
| Replay suite | `test_replay.py` | **23/23 PASS** |
| Startup | `verify_startup.py` | **RESTORED AND VERIFIED [OK]** |
| Clock enforcement | `check_clock_usage.py` | **PASS** |

---

## Hard Constraints Verified

- ✅ Matcher scoring: untouched
- ✅ Wake thresholds: untouched
- ✅ VAD decision logic: untouched
- ✅ ASR decoding: untouched
- ✅ PhraseRegistry behavior: untouched
- ✅ `utils/logger.py` correctly routes to `runtime/telemetry/logging.py`
- ✅ No `time.time()` / `time.monotonic()` / `datetime.now()` in runtime/ (outside exempted files)
