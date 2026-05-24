# Phase 3 Checkpoint — Telemetry & Observability

> **Status: LOCKED**
> **Date: 2026-05-22**
> **Baseline: Smoke 79/79 | Replay 23/23 | Startup VERIFIED**

---

## 1. Phase Summary

Phase 3 formalized the AVAListener telemetry and observability infrastructure. Every item below was implemented, validated, and stress-tested before lock.

| Item | Status |
|------|--------|
| Transition invariant validation (`VALID_SUBSYSTEM_TRANSITIONS`) | ✅ DONE |
| Structured event schema with `schema_version` | ✅ DONE |
| Correlation ID ownership moved to utterance/speech-start | ✅ DONE |
| Bounded telemetry queue (`maxsize=1000`, oldest-drop policy) | ✅ DONE |
| Drop tracking (`dropped_count` exposed in metrics) | ✅ DONE |
| Replay capture memory-only via `deque(maxlen=N)` | ✅ DONE |
| Manual flush/shutdown only — no runtime writes | ✅ DONE |
| Health score normalization (bounded min/max penalties) | ✅ DONE |
| Diagnostics snapshot safety (`deepcopy`) | ✅ DONE |
| `psutil` made optional — runtime never fails without it | ✅ DONE |
| Telemetry dispatcher background worker (non-blocking) | ✅ DONE |
| Telemetry stress test (10,000 events, non-blocking) | ✅ DONE |

---

## 2. Runtime Contracts — Frozen

The following APIs are **frozen**. Future phases must not break their signatures.

### `TelemetryEvent` (schema_version: 1)

```json
{
  "schema_version": 1,
  "event_id": "<uuid>",
  "correlation_id": "<utterance-session-uuid>",
  "subsystem": "<VAD|ASR|Matcher|Transport|...>",
  "event_type": "<string>",
  "timestamp_ns": "<int>",
  "payload": {}
}
```

### `engine.get_runtime_snapshot()` → `dict`

```json
{
  "uptime_seconds": 0.0,
  "current_state": "<RuntimeState>",
  "subsystem_states": { "ASR": "ACTIVE", "VAD": "ACTIVE", ... },
  "metrics": { ... },
  "active_profile": "<path>",
  "queue_status": 0
}
```
- Returns `deepcopy` — callers must not assume live reference.

### `ReplayCapture`

| Method | Signature | Contract |
|--------|-----------|----------|
| `start_capture(correlation_id)` | `str → None` | Begin in-memory accumulation |
| `record_hypothesis(correlation_id, text, stability)` | `str, str, int → None` | Append to deque (bounded) |
| `record_matcher_output(correlation_id, phrase, confidence)` | `str, str, float → None` | Append to deque |
| `flush(correlation_id)` | `str → str` | Write JSON to disk, return path |
| `shutdown()` | `→ None` | Flush all active sessions |

### `MetricsCollector` Public Methods

| Method | Returns | Contract |
|--------|---------|----------|
| `record_wake(latency_ms)` | `None` | Increment wake_count, append latency |
| `record_false_trigger()` | `None` | Increment false_trigger_count |
| `record_reset()` | `None` | Increment reset_count |
| `record_restart()` | `None` | Increment restart_count |
| `record_audio_drop()` | `None` | Increment audio_drop_count |
| `set_queue_depth(depth)` | `None` | Update current queue_depth |
| `avg_latency_ms` | `float` | Rolling average latency |
| `get_system_metrics()` | `dict` | CPU/memory (None if no psutil) |
| `get_all_metrics()` | `dict` | Full metrics snapshot including telemetry_drop_count |

---

## 3. Test Results

| Suite | Result |
|-------|--------|
| `tests/runtime/test_transition_invariants.py` | **6/6 PASS** |
| `tests/runtime/test_telemetry_queue.py` | **PASS** — 10,000 events in 0.240s, 1,780 drops tracked, queue bounded at 999 |
| `tests/smoke/test_smoke.py` | **79/79 PASS** |
| `tests/replay/test_replay.py` | **23/23 PASS** |
| `scripts/verify_startup.py` | **RESTORED AND VERIFIED [OK]** |
| `scripts/check_identity.py` | **zero violations** |
| `scripts/check_baseline_integrity.py` | **Baseline integrity verified** |

---

## 4. Rollback Procedure

### Option A — Git rollback
```bash
git checkout <phase3_checkpoint_tag>
```

### Option B — Manual rollback sequence

1. Restore `runtime/kernel/lifecycle.py` to Phase 2 version (remove `VALID_SUBSYSTEM_TRANSITIONS`, remove `shutdown()` / `recover()` helpers)
2. Remove `runtime/telemetry/schema.py`, `events.py`, `metrics.py`, `diagnostics.py`, `replay_capture.py`, `health.py`
3. Remove `tests/runtime/test_transition_invariants.py`, `tests/runtime/test_telemetry_queue.py`
4. Revert `runtime/asr/streaming.py` correlation_id changes
5. Revert `runtime/kernel/orchestrator.py` correlation_id propagation

### Verify after rollback:
```bash
python tests/smoke/test_smoke.py       # must be 79/79
python tests/replay/test_replay.py     # must be 23/23
python scripts/verify_startup.py       # must be RESTORED AND VERIFIED
```

---

## 5. Critical Invariants for Future Phases

- Telemetry MUST NOT be synchronous in hot paths (audio callback, VAD, ASR hot loop, matcher)
- `correlation_id` is owned by **utterance lifecycle** (speech-start), NOT by reset events
- `schema_version` must be incremented if `TelemetryEvent` fields change
- `ReplayCapture` must never write to disk automatically during runtime
- `get_runtime_snapshot()` must always return a deep copy
- `psutil` remains optional — always guard with `HAS_PSUTIL`
