# ARVSAL Benchmark Metrics

## 1. System Information
- **CPU**: 13th Gen Intel(R) Core(TM) i7-13700HX
- **RAM**: 15.71 GB
- **OS**: Windows_NT 10.0.26200 x64
- **Python version**: Python 3.12.12
- **Node version**: v20.20.0

## 2. Startup Performance

| Metric | Value |
|--------|-------|
| Cold start | 25483.00 ms |
| Warm start | 21344.00 ms |
| Worker spawn | 1314.32 ms |
| Worker ready | 2711.98 ms |
| Handshake | 5.47 ms |

## 3. Resource Usage (1 Hour Idle)

| Metric | Value |
|--------|-------|
| Idle RAM | 38.40 MB |
| Peak RAM | 39.17 MB |
| Avg RAM | 38.40 MB |
| CPU idle | 0.00 % |

## 4. Recovery Performance (20 crashes, 2 min interval)

| Metric | Value |
|--------|-------|
| Restart latency | 5383.80 ms |
| Recovery success | 100.00 % |
| Recovery failures | 0 |

## 5. Stability (100 Start/Stop Cycles)

| Metric | Value |
|--------|-------|
| Start/Stop success | 100.00 % |
| Websocket disconnects | 0 |
| Memory growth/hour | 1.06 MB/hour |
