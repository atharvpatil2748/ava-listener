const assert = require('assert');
const { ModelManager } = require('../../model_manager');
const path = require('path');
const fs = require('fs');

async function runTest() {
    const cacheRoot = path.join(__dirname, '..', '..', '..', 'temp', 'model_normalization_test_' + Date.now());
    fs.mkdirSync(cacheRoot, { recursive: true });
    
    try {
        const mm = new ModelManager({ cacheRoot });
        mm.ensure_cache_dirs();

        // Create a fake local source file
        const fakeSource = path.join(cacheRoot, 'temp', 'fake-source-epoch-99.onnx');
        fs.writeFileSync(fakeSource, 'dummy_content');
        const hash = require('crypto').createHash('sha256').update('dummy_content').digest('hex');

        const modelEntry = {
            id: 'test_model',
            version: '1',
            size: '13',
            sha256: hash,
            sourceFilename: 'fake-source-epoch-99.onnx',
            targetFilename: 'normalized.onnx',
            downloadUrl: 'file://' + fakeSource
        };

        // Test 1: Original filename -> normalized filename
        const targetPath = await mm.download_model(modelEntry);
        assert.strictEqual(targetPath, path.join(cacheRoot, 'models', 'normalized.onnx'));
        assert.ok(fs.existsSync(targetPath), 'Target file should exist');
        assert.ok(!fs.existsSync(path.join(cacheRoot, 'temp', 'fake-source-epoch-99.onnx.download')), 'Temp file should be removed or renamed');

        // Test 2: Corrupted download
        fs.writeFileSync(fakeSource, 'dummy_content');
        const badEntry = { ...modelEntry, id: 'bad', targetFilename: 'bad.onnx', sha256: 'wronghash' };
        try {
            await mm.download_model(badEntry);
            assert.fail('Should fail on checksum mismatch');
        } catch (err) {
            if (!err.message.includes('Checksum mismatch')) {
                console.error("Unexpected error in Test 2:", err);
            }
            assert.ok(err.message.includes('Checksum mismatch'));
            // cleanup behavior check
            assert.ok(!fs.existsSync(path.join(cacheRoot, 'temp', 'fake-source-epoch-99.onnx.download')), 'Temp file should be removed on failure');
        }

        // Test 3: Duplicate install (should overwrite or succeed)
        // Since download_model blindly overwrites, it should just succeed.
        // Let's rewrite the fake source as it was removed by the badEntry failure.
        fs.writeFileSync(fakeSource, 'dummy_content');
        const targetPath2 = await mm.download_model(modelEntry);
        assert.strictEqual(targetPath2, targetPath);

        // Test 4: Checksum validation before rename
        // ALready verified by Test 2 - the rename didn't happen because it failed.
        assert.ok(!fs.existsSync(path.join(cacheRoot, 'models', 'bad.onnx')), 'Rename should not happen if checksum fails');
        
        console.log('model_normalization_test passed');
    } finally {
        if (fs.existsSync(cacheRoot)) {
            fs.rmSync(cacheRoot, { recursive: true, force: true });
        }
    }
}

runTest().catch(err => {
    console.error(err);
    process.exit(1);
});
