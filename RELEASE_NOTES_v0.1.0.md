# AVA-Listener v0.1.0 Release Notes

Welcome to the **v0.1.0** Release Candidate of AVA-Listener.

This initial release introduces a strictly isolated, ultra-low latency, and fully offline ASR engine built on Sherpa ONNX. It effectively decouples heavy machine-learning workloads from standard Node.js applications while guaranteeing strong resource determinism and fault tolerance.

## Major Features
- **Zero-Cloud Offline Processing**: Performs all Wake Word and Speech Recognition entirely locally.
- **Node.js SDK**: Ships with a robust control plane allowing simple start/stop lifecycles, caching overrides, and diagnostic telemetry extraction.
- **Deterministic Resource Management**: Rigorously tested against cyclic memory leaks. Processes are strictly accounted for and forcefully cleaned up when parent applications terminate.
- **Self-Healing Supervisor Pipeline**: Built-in Python runtime verification and model downloader that transparently provisions missing dependencies on the first cold start.

## Architecture Overview
The runtime follows a multi-tier multiprocessing model:
1. **Host App / SDK Layer**: The Node.js package providing the public `AVAListener` interface.
2. **Supervisor Layer**: Python-based orchestration that manages WebSocket IPC, schema validations, and process locks.
3. **Audio Worker Layer**: Python-based inference engine strictly bound to the Sherpa ONNX library and the system microphone.

## Benchmark Summary
The Phase 11 stabilization effort produced the following official baseline metrics:
- **Startup Success**: 100% (10/10 automated lifecycle verifications)
- **Worker Failures**: 0
- **Websocket Disconnects**: 0
- **Warm Start**: 3770 ms
- **Cold Start**: 19138 ms
- **Worker Spawn**: 567.3 ms
- **Worker Ready**: 2652.3 ms

## Optimization Results
During Phase 11, systemic startup bottlenecks were identified and removed, producing a combined startup improvement of **5762.8 ms**:
- **Process Scan**: 2981.75 ms → 0.014 ms *(Replaced synchronous OS polling with native ChildProcess event bookkeeping)*
- **Model Verification**: 2792.29 ms → 11.234 ms *(Implemented metadata-keyed manifest hashing to skip redundant sequential SHA checksum recalculations on disk)*

## Known Limitations
- Input stream defaults purely to the system-assigned default microphone device. An explicit input selection API will be available in future releases.
- Inference is currently tightly bound to the standard `Sherpa ONNX` backend profiles.

## Roadmap Preview
- **Phase 12**: Repository Hardening and Initial Release (Current).
- **Phase 13**: Pluggable Backend API & Dynamic Configuration Registry to support programmable thresholds, custom waking models, and hot-swappable AI assistants.
- **Phase 14**: External audio streaming and End-to-End Multimodal extensions.
