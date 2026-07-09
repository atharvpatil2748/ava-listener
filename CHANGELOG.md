# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] - 2026-07-09
### Added
- Runtime profile switching without restarting the listener or audio stream.
- Bidirectional worker IPC for receiving `CONFIGURE` routing instructions asynchronously.
- Atomic phrase registry replacements, ensuring inference thread safety during live configuration updates.

## [0.1.0] - 2026-05-24
### Added
- Phase 11 official production baseline.
- `AVAListener` Node.js SDK interface.
- Python Audio Worker using Sherpa ONNX backend.
- Multiplexed WebSocket IPC for fast control and telemetry.
- Built-in diagnostic metrics (`getMetrics`) for tracking memory usage and handles.
- Fully isolated testing environment for benchmarks.
- Automated model download and verification engine.

### Optimized
- Eliminated synchronous OS process tree scanning (`wmic`/`ps`), reducing cycle scan latency by ~2981ms.
- Implemented keyed `manifestHash_size_mtimeMs` disk caching for model validation, reducing warm-start SHA checksum hashing latency by ~2781ms.
- Hardened shutdown sequences to gracefully terminate orphaned workers without leaking resources.
