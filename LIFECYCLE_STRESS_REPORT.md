# Lifecycle Stress Report -- AVAListener (F4)

> **Date:** 2026-05-22 20:55:04
> **Cycles:** 100  |  **Total time:** 547.0s  |  **Verdict:** PASS

---

## 1. Summary

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Total cycles | 100 | 100 | -- |
| Passed | 100 | 100 | OK |
| Baseline initialization events | 1 | 1 | OK |
| Orphan threads | 0 | 0 | OK |
| Engine errors | 0 | 0 | OK |
| Net thread growth (total) | +2 | -- | note |
| Daemon threads remaining | 2 | -- | exit-safe |
| Avg cycle time | 5.414s | -- | -- |
| Min / Max cycle | 5.328s / 5.601s | -- | -- |

> **Thread note:** Daemon threads (watchdog, heartbeat emitter) accumulate across cycles
> and are killed on process exit. Non-daemon orphan threads must be 0.

## 2. Cycle Detail (first 10, last 10, failures)

| Cycle | Time | Orphan | Thr+/- | Queue Residue | Result |
|-------|------|--------|--------|---------------|--------|
| 1 | 5.328s | no | +2 | 0 | BASELINE_INITIALIZATION |
| 2 | 5.417s | no | +0 | 0 | PASS |
| 3 | 5.410s | no | +0 | 0 | PASS |
| 4 | 5.541s | no | +0 | 0 | PASS |
| 5 | 5.527s | no | +0 | 0 | PASS |
| 6 | 5.392s | no | +0 | 0 | PASS |
| 7 | 5.541s | no | +0 | 0 | PASS |
| 8 | 5.601s | no | +0 | 0 | PASS |
| 9 | 5.467s | no | +0 | 0 | PASS |
| 10 | 5.458s | no | +0 | 0 | PASS |
| 91 | 5.404s | no | +0 | 0 | PASS |
| 92 | 5.420s | no | +0 | 0 | PASS |
| 93 | 5.419s | no | +0 | 0 | PASS |
| 94 | 5.433s | no | +0 | 0 | PASS |
| 95 | 5.400s | no | +0 | 0 | PASS |
| 96 | 5.420s | no | +0 | 0 | PASS |
| 97 | 5.390s | no | +0 | 0 | PASS |
| 98 | 5.426s | no | +0 | 0 | PASS |
| 99 | 5.398s | no | +0 | 0 | PASS |
| 100 | 5.512s | no | +0 | 0 | PASS |
_(only first 10 + last 10 + failures shown)_

## 3. Findings

All lifecycle stress criteria passed:

- Orphan threads: 0 (none -- all workers joined cleanly)
- Engine errors: 0 (none)
- Net thread growth over 100 cycles: +2 (acceptable)
- Average cycle time: 5.414s (including model-skipped start overhead)

## 4. Thread Safety Notes

Each cycle exercises:
  1. SherpaStreamer.__init__ (builds QueueManager, AudioWorker, SherpaProvider)
  2. SherpaStreamer.start (fake audio path -- transitions FSMs, starts worker thread)
  3. 5x frame injection via QueueManager
  4. WakeEngine.stop -> SherpaStreamer.stop -> AudioWorker.stop -> thread.join(5s)
  5. Object destruction and GC collection

The test validates that the stop/join/GC cycle fully reclaims thread resources
without residual queue entries or zombie threads.
