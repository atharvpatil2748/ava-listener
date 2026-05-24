const { ModelManager } = require('../node/model_manager');

async function main() {
    console.log("Setting up models...");
    
    const fs = require('fs');
    const path = require('path');
    
    const modelsDir = path.join(__dirname, '..', 'models');
    const manifestsDir = path.join(modelsDir, 'manifests');
    const manifestPath = path.join(manifestsDir, 'manifest.json');
    
    if (!fs.existsSync(modelsDir)) {
        fs.mkdirSync(modelsDir);
    }
    if (!fs.existsSync(manifestsDir)) {
        fs.mkdirSync(manifestsDir);
    }
    
    if (!fs.existsSync(manifestPath)) {
        console.log("Generating default manifest.json...");
        const defaultManifest = {
            "manifestVersion": 1,
            "models": [
                {
                    "id": "encoder.onnx",
                    "version": "1",
                    "size": 70108816,
                    "sha256": "5022b2eca5b19d1bc104fcf33e26bc32604b7df553cd2e1f62e31dc7b05e9c87",
                    "sourceFilename": "encoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx",
                    "targetFilename": "encoder.onnx",
                    "downloadUrl": "https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-en-2023-06-26/resolve/main/encoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx"
                },
                {
                    "id": "decoder.onnx",
                    "version": "1",
                    "size": 540688,
                    "sha256": "780c63ee94c7cfa314211172e5d09b406c0da2beab5c40ea2f54cc95670b76a5",
                    "sourceFilename": "decoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx",
                    "targetFilename": "decoder.onnx",
                    "downloadUrl": "https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-en-2023-06-26/resolve/main/decoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx"
                },
                {
                    "id": "joiner.onnx",
                    "version": "1",
                    "size": 259416,
                    "sha256": "abd5e30f3f16fc510605c6029dba33f10e4386bd75c5bdc30cf94076864db10d",
                    "sourceFilename": "joiner-epoch-99-avg-1-chunk-16-left-128.int8.onnx",
                    "targetFilename": "joiner.onnx",
                    "downloadUrl": "https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-en-2023-06-26/resolve/main/joiner-epoch-99-avg-1-chunk-16-left-128.int8.onnx"
                },
                {
                    "id": "tokens.txt",
                    "version": "1",
                    "size": 5048,
                    "sha256": "49e3c2646595fd907228b3c6787069658f67b17377c60aeb8619c4551b2316fb",
                    "sourceFilename": "tokens.txt",
                    "targetFilename": "tokens.txt",
                    "downloadUrl": "https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-en-2023-06-26/resolve/main/tokens.txt"
                },
                {
                    "id": "silero_vad.onnx",
                    "version": "1",
                    "size": 2327524,
                    "sha256": "1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3",
                    "sourceFilename": "silero_vad.onnx",
                    "targetFilename": "silero_vad.onnx",
                    "downloadUrl": "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
                }
            ]
        };
        fs.writeFileSync(manifestPath, JSON.stringify(defaultManifest, null, 2));
    }

    const manager = new ModelManager();
    
    console.log("Validating manifest...");
    await manager.validate_manifest_urls();
    
    console.log("Checking and downloading missing models...");
    let lastId = null;
    const missing = await manager.verifyOrDownload((progress) => {
        if (lastId !== progress.id) {
            if (lastId !== null) console.log(""); // Newline for previous
            lastId = progress.id;
        }
        const percent = ((progress.downloaded / progress.total) * 100).toFixed(1);
        process.stdout.write(`\rDownloading ${progress.id}... ${percent}%`);
    });
    
    if (lastId !== null) console.log(""); // Final newline

    if (missing.length > 0) {
        console.log("Models successfully downloaded and verified.");
    } else {
        console.log("All models are already present and verified.");
    }
}

main().catch(err => {
    console.error("\nSetup failed:", err.message);
    process.exit(1);
});
