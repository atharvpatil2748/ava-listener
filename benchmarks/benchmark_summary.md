# AVAListener Performance Benchmark

**Date**: 2026-05-23T18:23:43.173Z
**Status**: ❌ Regression Detected

## System Metadata
- **OS**: Windows_NT 10.0.26200 x64
- **CPU**: 13th Gen Intel(R) Core(TM) i7-13700HX
- **RAM**: 15.71 GB
- **Node**: v20.20.0
- **Python**: Python 3.12.12

## Key Metrics
| Metric | Value (ms) |
|--------|------------|
| Cold Start | 25483.00 |
| Warm Start | 21344.00 |
| Worker Restart | 4247.69 |
| Model Verification | 2792.29 |
| Idle Memory | 29.55 MB |

## Diff
```json
{
  "runtime_verification_ms": {
    "baseline": 786.9592,
    "current": 3773.1535,
    "delta": 2986.1943,
    "pct": 379.45986272223513
  },
  "model_verification_ms": {
    "baseline": 2979.2151,
    "current": 2792.2936,
    "delta": -186.92149999999992,
    "pct": -6.274186110294619
  },
  "worker_spawn_ms": {
    "baseline": 1149.0455,
    "current": 1314.3153,
    "delta": 165.26980000000003,
    "pct": 14.383225033299382
  },
  "ws_connection_ms": {
    "baseline": 5.0454,
    "current": 5.8955,
    "delta": 0.8501000000000003,
    "pct": 16.849010980298893
  },
  "handshake_ms": {
    "baseline": 5.4076,
    "current": 5.4741,
    "delta": 0.06649999999999956,
    "pct": 1.2297507212071817
  },
  "worker_ready_ms": {
    "baseline": 2729.0803,
    "current": 2711.9841,
    "delta": -17.096199999999953,
    "pct": -0.6264454732240731
  },
  "startup_time_ms": {
    "baseline": 7660.4906,
    "current": 10611.0687,
    "delta": 2950.5780999999997,
    "pct": 38.51682945737183
  },
  "restart_recovery_ms": {
    "baseline": 4155.1643,
    "current": 4247.6902,
    "delta": 92.52589999999964,
    "pct": 2.226768746545104
  },
  "cold_start_ms": {
    "baseline": null,
    "current": 25483,
    "delta": null,
    "pct": null
  },
  "idle_memory_mb_cold": {
    "baseline": null,
    "current": 29.65234375,
    "delta": null,
    "pct": null
  },
  "idle_cpu_percent_cold": {
    "baseline": null,
    "current": 0,
    "delta": null,
    "pct": null
  },
  "warm_start_ms": {
    "baseline": null,
    "current": 21344,
    "delta": null,
    "pct": null
  },
  "idle_memory_mb_warm": {
    "baseline": null,
    "current": 29.546875,
    "delta": null,
    "pct": null
  },
  "idle_cpu_percent_warm": {
    "baseline": null,
    "current": 0,
    "delta": null,
    "pct": null
  }
}
```
