# AVA-Listener

AVA-Listener is a high-performance, programmable speech runtime and offline ASR (Automatic Speech Recognition) engine. Designed to decouple assistant-specific logic from the core speech pipeline, AVA-Listener provides a blazing-fast, isolated local runtime optimized for latency-critical voice applications.

## Features

- **Offline Local Speech Recognition**: Zero-cloud dependencies. Full local execution using Sherpa ONNX.
- **Ultra-Low Latency**: Highly optimized initialization pipelines achieving sub-4-second warm starts.
- **Process Isolation**: Fault-tolerant multiprocess architecture decoupling Node.js application state from Python ML execution.
- **Platform Agnostic**: Built for cross-platform compatibility across Windows, macOS, and Linux.
- **Resource Determinism**: Strictly guarded memory growth preventing leaks during multi-hour continuous audio sessions.

## Architecture

```mermaid
graph TD
    Client[Client Application] <-->|WebSocket IPC| SDK[Node.js SDK / Supervisor]
    SDK <-->|WebSocket + stdio| Worker[Python Audio Worker]
    Worker -->|Inference| Sherpa[Sherpa ONNX Runtime]
    Worker <--|Audio Data| Mic[System Microphone]
```

## Installation

```bash
npm install ava-listener
```

Ensure Python >= 3.10 is installed and available in your system `PATH`.

## Quick Start

```javascript
const { AVAListener } = require('ava-listener');

async function run() {
    const listener = new AVAListener({ debug: false });
    
    // Start the runtime (downloads required models automatically on first run)
    await listener.start();
    console.log("AVA-Listener is actively listening!");
    
    // Stop gracefully
    await listener.stop();
}

run();
```

## API Overview

### Initialization
```javascript
const listener = new AVAListener({
  cacheRoot: './custom_cache', // Optional: Override model storage directory
  startPaused: false           // Optional: Start without immediately opening the microphone
});
```

### Retrieving Metrics
```javascript
const metrics = await listener.getMetrics();
console.log(`Memory Used: ${metrics.memory_usage_mb} MB`);
console.log(`Active Workers: ${metrics.active_python_process_count}`);
```

## Benchmarks & Performance

*(Metrics collected during Phase 11 official production baseline).*

### Startup Metrics
| Metric | Latency |
|--------|---------|
| **Warm Start** | 3770 ms |
| **Cold Start (Initial Download)** | 19138 ms |
| **Worker Spawn** | 567.3 ms |
| **Worker Ready** | 2652.3 ms |

### Stability & Resource Usage
- **Startup Success Rate**: 100% (10/10 deterministic stress cycles)
- **Worker Failures**: 0
- **WebSocket Disconnects**: 0
- **Idle Memory Footprint**: ~30 MB (Flat across sequential restarts with 0MB leak rate)

### Optimization Evidence
During Phase 11, critical path bottlenecks were identified and aggressively optimized. Total startup latency reduction: **5762.8 ms**.

| Subcomponent | Before | After | Improvement Strategy |
|--------------|--------|-------|----------------------|
| **Process Scan (OS Exec)** | 2981.75 ms | 0.014 ms | Eliminated via native child-process bookkeeping |
| **Model Validation (SHA256)**| 2792.29 ms | 11.234 ms | Replaced with keyed manifest/mtime/size disk caching |

## Limitations

- Currently relies on the system default microphone. Device selection API is planned.
- Tightly coupled to the Sherpa ONNX backend. Pluggable backends planned.

## Future Plans

See `ROADMAP.md` for upcoming milestones, including dynamic configuration registries and plugin API interfaces.
