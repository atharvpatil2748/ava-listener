# Phase 4 Checkpoint — Runtime Hardening & Recovery

> **Status: LOCKED**
> **Date: 2026-05-22**
> **Baseline: Smoke 79/79 | Replay 23/23 | Lifecycle 51/51 | Recovery 20/20 | Startup VERIFIED**

---

## 1. Frozen Components

### Runtime: Recovery Subsystem

| Component | File | Contract |
|-----------|------|----------|
| `RecoveryPolicy` | `runtime/hardening/recovery_policy.py` | Exponential backoff — `delay = min(initial * 2^retries, max_ms)` |
| `FaultClassifier` | `runtime/hardening/fault_classifier.py` | Maps exceptions/strings → `TRANSIENT / RECOVERABLE / CRITICAL` |
| `RestartManager` | `runtime/hardening/restart_manager.py` | Per-subsystem restart tracking with cooldown, pluggable handlers |
| `RecoveryCoordinator` | `runtime/hardening/recovery_coordinator.py` | Top-level dispatcher: `recover / restart / escalate / shutdown` |

**Hard constraints (never modify):**
- Recovery logic MUST NOT touch matcher scoring, phrase registry, wake thresholds, or ASR decoding
- All recovery actions MUST emit structured telemetry events
- Watchdog backoff gate MUST prevent restart death loops

### Runtime: ASR Worker FSM Lifecycle (Fixed)

**Correct startup sequence:**
```
OFFLINE → INITIALIZING → READY → worker.start() → ACTIVE
```

**Critical ordering rule:**
> `self._asr_fsm.transition(READY)` MUST be called BEFORE `worker.start()`.
> The OS scheduler may begin thread execution on the very next tick — READY must already be set.

**Worker defensive guard:**
```python
if self._asr_fsm.state == SubsystemState.READY:
    self._asr_fsm.transition(SubsystemState.ACTIVE)
elif self._asr_fsm.state == SubsystemState.ACTIVE:
    pass  # re-entrant path
else:
    raise RuntimeError(f"ASR worker invalid state: {self._asr_fsm.state.value}")
```

### Runtime: Watchdog Integration

`RuntimeWatchdog` now integrates `RecoveryPolicy` to prevent restart death loops:
- Backoff delays: 100ms → 200ms → 400ms → 800ms → max 8000ms
- Escalation after 4 retries at max backoff
- `reset_recovery_state()` callable externally after manual restart

### Node SDK: Frozen API Surface

| Component | Contract |
|-----------|----------|
| Lifecycle methods | `start()`, `stop()`, `pause()`, `resume()` — state-gated |
| State machine | `UNINITIALIZED → STARTING → READY → RUNNING → RECOVERING → STOPPED → FAILED` |
| Process manager | Supervisor spawns Worker; crash isolated to Worker |
| Profile loading | `--profile <path>` — generic, no assistant coupling |
| Runtime connection flow | Handshake → configure → start → detect |

### Runtime: PhraseRegistry & Profile System

| Component | Contract |
|-----------|----------|
| `PhraseRegistry` | Thread-safe, generic — no assistant names in engine layer |
| Profile loading | `_load_profile_into_registry(path)` — reads external JSON |
| ASR wake pipeline | Unchanged — fuzzy match → EMA score → threshold gate → cooldown |

---

## 2. Runtime Validation

### `profiles/arvsal.json`

| Check | Result |
|-------|--------|
| Wake detection | ✅ `WAKE \| phrase='arvsal'` |
| Profile loading | ✅ 6 phrases registered |
| ASR worker startup | ✅ `state=READY → ACTIVE` (no exception) |
| Generation reset | ✅ `ASR stream reset → generation N reason=wake` |
| No worker death | ✅ |
| No watchdog restart loop | ✅ |
| No queue overflow | ✅ |
| Lifecycle state transitions | ✅ All legal sequences |

### `profiles/jarvis.json`

| Check | Result |
|-------|--------|
| Wake detection | ✅ `WAKE \| phrase='jarvis'` |
| Profile switching | ✅ Loads cleanly, no restart |
| Runtime remains generic | ✅ No assistant coupling |
| No engine changes required | ✅ |

### Generic Engine Verification

AVAListener runtime confirmed as a fully generic engine:
- Arvsal profile → detects "arvsal", "arsal", "hey arvsal", etc.
- Jarvis profile → detects "jarvis", "jarvas", etc.
- Engine code references zero assistant names.

---

## 3. Known Issues

### P4-KNOWN-001

**Observed:**
```
WAKE | phrase='jarvis' variant='' canonical=''
```
On second wake event: `raw=0.83 smooth=0.76`

**Root cause:** Variant lookup misses when hypothesis stabilizes mid-phrase — matched phrase ID but variant string not populated in second trigger path.

**Status:** Non-blocking
**Priority:** Medium
**Action:** Do NOT fix during Phase 4 checkpoint. Track for Phase 5 or Phase 6.

---

## 4. Test Results

| Suite | Result |
|-------|--------|
| `tests/runtime/test_subsystem_lifecycle.py` | **51/51 PASS** |
| `tests/runtime/test_recovery.py` | **20/20 PASS** |
| `tests/runtime/test_transition_invariants.py` | **6/6 PASS** |
| `tests/runtime/test_telemetry_queue.py` | **PASS** |
| `tests/smoke/test_smoke.py` | **79/79 PASS** |
| `tests/replay/test_replay.py` | **23/23 PASS** |
| `scripts/verify_startup.py` | **RESTORED AND VERIFIED [OK]** |
| `scripts/check_baseline_integrity.py` | **Baseline integrity verified** |

---

## 5. Rollback Procedure

```bash
# Option A: git
git checkout <phase4_checkpoint_tag>

# Option B: manual
# 1. Remove runtime/hardening/ directory
# 2. Restore runtime/supervisor/watchdog.py to Phase 3 version (no RecoveryPolicy)
# 3. Revert streaming.py — restore worker.start() BEFORE READY transition
#    (reverts fix, brings back race — do not do this)

# Verify after rollback:
python tests/smoke/test_smoke.py        # 79/79
python tests/replay/test_replay.py      # 23/23
python scripts/verify_startup.py        # RESTORED AND VERIFIED
```

---

## 6. Critical Invariants for Future Phases

- ASR FSM READY must be set BEFORE `worker.start()` — this is a **hard ordering constraint**
- Watchdog recovery policy must not be bypassed
- Recovery coordinator must emit telemetry for every action
- `RecoveryPolicy.reset()` must be called after successful recovery
- Phase 5 MUST NOT modify: matcher scoring, wake thresholds, VAD decisions, ASR decoding, PhraseRegistry behavior
