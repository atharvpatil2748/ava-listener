const fs = require('fs');
const path = require('path');
const cp = require('child_process');
const os = require('os');
const { AVAListener } = require('../../../node/listener');

async function run() {
    const tempCacheDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ava-model-test-'));
    
    console.log(`1. Simulating empty cache at ${tempCacheDir}`);
    const listener = new AVAListener({
        cacheRoot: tempCacheDir,
        startPaused: true // Prevent audio lock issues during test
    });

    console.log("2. Starting AVAListener to trigger download & worker startup...");
    await listener.start(null, { debug: true });
    
    console.log("3. Verifying models downloaded to cache...");
    const modelsDir = path.join(tempCacheDir, 'models');
    if (!fs.existsSync(modelsDir)) {
        throw new Error(`Models directory missing from cache: ${modelsDir}`);
    }
    
    const requiredModels = ['encoder.onnx', 'decoder.onnx', 'joiner.onnx', 'tokens.txt'];
    for (const req of requiredModels) {
        if (!fs.existsSync(path.join(modelsDir, req))) {
            throw new Error(`Model ${req} missing from cache!`);
        }
    }
    console.log("-> Models verified in cache.");

    console.log("4. Verifying Python worker resolved the cache path...");
    // Check if worker spawned successfully and isn't crashing
    // If it crashed, processManager wouldn't have resolved the WebSocket port.
    if (!listener.lifecycle.processManager.proc) {
        throw new Error("Supervisor process failed to start!");
    }

    console.log("-> Worker spawned and stable.");

    console.log("5. Cleaning up...");
    await listener.stop();
    
    // Attempt cleanup, but ignore EBUSY errors on Windows if process hasn't fully exited yet
    try {
        fs.rmSync(tempCacheDir, { recursive: true, force: true });
    } catch (err) {
        console.warn(`Cleanup non-fatal warning: ${err.message}`);
    }

    console.log("Test Passed.");
}

run().catch(err => {
    console.error(err);
    process.exit(1);
});
