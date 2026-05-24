# Memory Stability Report -- AVAListener Runtime Stress (F2)

> **Date:** 2026-05-22  |  **Start:** 20:31:12  |  **End:** 20:32:12
> **Duration:** 60s  |  **Audio:** Synthetic (no microphone)  |  **Verdict:** PASS

---

## 1. Summary

| Metric | Value | Status |
|--------|-------|--------|
| Worker deaths | 0 | OK |
| Queue overflow events | 0 | OK |
| Memory trend | STABLE (+0.108 MB/min) | OK |
| Total frames injected | 598 | -- |
| Samples collected | 5 | -- |

## 2. Memory Trend

| Slope (MB/min) | R2 | Min MB | Max MB | Delta MB | Verdict |
|---|---|---|---|---|---|
| +0.108 | 0.835 | 0.76 | 0.84 | 0.08 | **STABLE** |

## 3. Per-Sample Metrics

| # | Time | Elapsed | Memory MB | Queue | Threads | Health | Worker | Gen | Resets |
|---|------|---------|-----------|-------|---------|--------|--------|-----|--------|
| 1 | 20:31:22 | 10s | 0.76 | 0 | 6 | 0.979 | Y | 1 | 1 |
| 2 | 20:31:32 | 20s | 0.81 | 0 | 6 | 0.979 | Y | 2 | 2 |
| 3 | 20:31:42 | 30s | 0.82 | 0 | 6 | 0.979 | Y | 3 | 3 |
| 4 | 20:31:52 | 40s | 0.83 | 0 | 6 | 0.979 | Y | 3 | 3 |
| 5 | 20:32:02 | 50s | 0.84 | 0 | 6 | 0.979 | Y | 4 | 4 |

## 4. State Timeline

| # | ASR | Audio | VAD | Engine State |
|---|-----|-------|-----|-------------|
| 1 | ACTIVE | ACTIVE | ACTIVE | LISTENING |
| 2 | ACTIVE | ACTIVE | ACTIVE | LISTENING |
| 3 | ACTIVE | ACTIVE | ACTIVE | LISTENING |
| 4 | ACTIVE | ACTIVE | ACTIVE | LISTENING |
| 5 | ACTIVE | ACTIVE | ACTIVE | LISTENING |

## 5. Findings

All criteria passed.
