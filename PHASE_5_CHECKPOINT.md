# Phase 5 Checkpoint — Observability

> **Status: LOCKED**
> **Date: 2026-05-22**

---

## 1. Frozen APIs

The following public APIs and interfaces are now frozen:
- **`LogContext`**: Process-global context holder (`new_session()`, `set_correlation()`, `set_subsystem()`, `get()`).
- **`StructuredFormatter`**: Dual-mode JSON/text formatter.
- **`LogSink` classes**: `LogSink` (ABC), `ConsoleSink`, `FileSink`, `NullSink`.
- **`RuntimeClock`**: Authoritative time source (`now_ns()`, `now_s()`, `monotonic()`, `uptime_s()`).
- **`LatencyTracker`**: Per-correlation latency tracking (`mark(stage)`, `to_dict()`, `end_to_end_ms`) and `RollingLatency`.
- **`HealthReporter`**: Formats comprehensive health reports using mapped signals and weights (`get_report()`).
- **`CrashSnapshot`**: Captures a safe, immutable snapshot of runtime state consuming only exported contracts (`capture(reason)`).
- **Diagnostics APIs**: `WakeEngine` methods `getHealth()`, `getMetrics()`, `getDiagnostics()`, `getManifest()`.

## 2. Frozen Stage Contracts

The following explicit pipeline stages are formally defined and enforced in `LatencyTracker`:
- `capture_to_queue`: Audio chunk lands in the audio queue.
- `vad`: VAD decision completes.
- `asr`: ASR partial/final hypothesis emitted.
- `matcher`: Matcher scores computed.
- `wake_total`: Wake event fired (end-to-end boundary).

## 3. Regression Matrix

| Check | Result |
|-------|--------|
| Observability Test Suite | **80/80 PASS** |
| Smoke Suite | **79/79 PASS** |
| Replay Suite | **23/23 PASS** |
| Startup Verification | **RESTORED AND VERIFIED [OK]** |
| Clock Enforcement | **PASS** |

## 4. Rollback Procedure

```bash
# Option A: git
git checkout <phase4_checkpoint_tag>

# Option B: manual
# 1. Delete directories: runtime/logging/, runtime/timing/, runtime/health/, runtime/debug/.
# 2. Revert runtime/asr/streaming.py (remove export_debug_state).
# 3. Revert runtime/vad/pipeline.py (remove export_debug_state).
# 4. Revert runtime/kernel/orchestrator.py (remove Phase 5 observability wiring and get* methods).
# 5. Delete tests/runtime/test_observability.py and scripts/check_clock_usage.py.
# 6. Ensure utils/logger.py correctly imports from runtime.telemetry.logging.

# Verify after rollback:
python tests/smoke/test_smoke.py        # 79/79
python tests/replay/test_replay.py      # 23/23
python scripts/verify_startup.py        # RESTORED AND VERIFIED
```

## 5. Known Issues List

- **P5-KNOWN-001 (Carried from P4-KNOWN-001):** Occasional empty strings for `variant` and `canonical` metadata on the second wake event (e.g., when the hypothesis stabilizes mid-phrase). The `variant` lookup misses the populated variant string in the second trigger path. Non-blocking (tracked for future phase).
