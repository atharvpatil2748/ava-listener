# AVA-Listener Model Setup

The AVA-Listener runtime requires external ONNX models to function. These models (~75MB) are excluded from the `npm` package and GitHub repository to maintain a lightweight footprint. **They are not downloaded automatically during `npm install`.**

You must run the setup sequence to acquire the models before starting the listener.

## Setup Workflow (Recommended Future Workflow)

*Note: The `ava-listener setup` command does not exist yet. This is the planned recommended workflow.*

1. Install the package: `npm install ava-listener`
2. Run the setup wizard: `npx ava-listener setup`
3. The wizard will securely download the models.
4. Checksums are verified automatically.
5. Models are placed in the global application data directory.

---

## 1. Automatic Setup (Recommended Future Workflow)

*Note: This command is planned for a future release.*
To automatically fetch, verify, and install the required models, run:

```bash
npx ava-listener setup
```

### Downloaded Files
The setup process will download the following verified files:
*   `encoder.onnx`
*   `decoder.onnx`
*   `joiner.onnx`
*   `tokens.txt`
*   `silero_vad.onnx`

### Expected Install Locations
Depending on your operating system, the models will be placed in the following global directories so they can be shared across multiple projects:

*   **Windows:** `C:\Users\<user>\AppData\Local\AVAListener\models`
*   **Linux:** `~/.ava-listener/models`
*   **macOS:** `~/Library/Application Support/AVAListener/models`

---

## 2. Manual Setup (Offline/Air-gapped Environments)

If you are deploying in an offline environment or prefer to manage binaries yourself, you can download the models manually and place them in the required folder structure.

### Required Folder Structure
Create a `models/` folder in the root of your project directory, or use the global paths listed above.

```text
models/
├── encoder.onnx
├── decoder.onnx
├── joiner.onnx
├── tokens.txt
└── silero_vad.onnx
```

### Download Links & Instructions

#### A. Speech Recognition (Sherpa-ONNX)
**Source:** https://github.com/k2-fsa/sherpa-onnx/releases

You must download a streaming Zipformer or Transducer model archive. Extract the archive and rename the files to match the expected filenames exactly:
*   *Rename* `<model_prefix>-encoder.onnx` ➔ `encoder.onnx`
*   *Rename* `<model_prefix>-decoder.onnx` ➔ `decoder.onnx`
*   *Rename* `<model_prefix>-joiner.onnx` ➔ `joiner.onnx`
*   *Keep as* `tokens.txt`

#### B. Voice Activity Detection (Silero)
**Source:** https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx

*   Download the raw `.onnx` file.
*   *Keep as* `silero_vad.onnx`
