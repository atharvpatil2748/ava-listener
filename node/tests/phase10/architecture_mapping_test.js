const assert = require('assert');
const os = require('os');
const { RuntimeManager } = require('../../runtime_manager');

const originalPlatform = os.platform;
const originalArch = os.arch;

try {
    const rm = new RuntimeManager();
    
    // windows x64
    os.platform = () => 'win32';
    os.arch = () => 'x64';
    let artifact = rm.get_runtime_artifact();
    assert.strictEqual(artifact.assetName, 'ava-runtime-windows-x64.zip');

    // macos arm64
    os.platform = () => 'darwin';
    os.arch = () => 'arm64';
    artifact = rm.get_runtime_artifact();
    assert.strictEqual(artifact.assetName, 'ava-runtime-macos-arm64.tar.gz');

    // macos x64
    os.platform = () => 'darwin';
    os.arch = () => 'x64';
    artifact = rm.get_runtime_artifact();
    assert.strictEqual(artifact.assetName, 'ava-runtime-macos-x64.tar.gz');

    // linux x64
    os.platform = () => 'linux';
    os.arch = () => 'x64';
    artifact = rm.get_runtime_artifact();
    assert.strictEqual(artifact.assetName, 'ava-runtime-linux-x64.tar.gz');
    
    // linux arm64
    os.platform = () => 'linux';
    os.arch = () => 'arm64';
    artifact = rm.get_runtime_artifact();
    assert.strictEqual(artifact.assetName, 'ava-runtime-linux-arm64.tar.gz');

    console.log('architecture_mapping_test passed');
} finally {
    os.platform = originalPlatform;
    os.arch = originalArch;
}
