# AVA-Listener

AVA-Listener is a high-performance, programmable speech runtime and offline ASR (Automatic Speech Recognition) engine. Designed to decouple assistant-specific logic from the core speech pipeline, AVA-Listener provides a blazing-fast, isolated local runtime optimized for latency-critical voice applications.

## Quick Start (Fresh Clone)

### 1. Clone the Repository

```bash
git clone https://github.com/atharvpatil2748/ava-listener.git
cd ava-listener
npm install
```

### 2. Setup Models

The speech runtime requires external ONNX models (~75MB) to function. To keep the repository lightweight, they are excluded from Git and npm. You must download them via the setup script before running the engine.

```bash
npm run setup-models
```
*(This script securely fetches, verifies, and installs the required speech and VAD models to your local cache.)*

### 3. Verify Installation

```bash
npm run verify
```
*(Ensures the package layout and required folders are structurally sound before execution.)*

### 4. Test Wake Detection

```bash
npm start
```
**Expected Output:**
```text
[NodeSDK][INFO] READY
Listening for wake word...
```

---

## Architecture & File Structure

```text
AVA-Listener/
├── node/               # Node.js supervisor and IPC handlers
├── runtime/            # Python core engine (ASR, VAD, Matching)
├── models/             # (Ignored) Binary ONNX models
│   └── manifests/      # Validation manifests 
├── profiles/           # Assistant configuration JSONs
├── scripts/            # Setup and utility scripts
└── package.json
```

---

## Manual Model Setup (Fallback)

If you are deploying in an offline/air-gapped environment and cannot use `npm run setup-models`, you can place the required binaries manually.

1. Ensure the directory `models/` exists.
2. Download the required ONNX models from HuggingFace/GitHub.
3. Place them in `models/` with exactly these filenames:
   - `encoder.onnx`
   - `decoder.onnx`
   - `joiner.onnx`
   - `tokens.txt`
   - `silero_vad.onnx`

---

## Troubleshooting

- **`Missing required package entry: models`**
  Run `npm install` again to trigger the bootstrap, or manually run `node node/bootstrap.js --validate-layout` to create the missing directories.
- **Model Checksum/Download Failures**
  Run `npm run setup-models` again. The script is resilient and will resume or overwrite corrupted partial downloads.
- **`ImportError: cannot import name ...`**
  Ensure your `PYTHONPATH` correctly aligns with the runtime path. Running via the standard `npm start` SDK wrapper handles environment pathways automatically.

---

## Features

- **Offline Local Speech Recognition**: Zero-cloud dependencies. Full local execution using Sherpa ONNX.
- **Ultra-Low Latency**: Highly optimized initialization pipelines achieving sub-4-second warm starts.
- **Process Isolation**: Fault-tolerant multiprocess architecture decoupling Node.js application state from Python ML execution.
- **Platform Agnostic**: Built for cross-platform compatibility across Windows, macOS, and Linux.
