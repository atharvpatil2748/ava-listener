const assert = require('assert');
const os = require('os');
const { RuntimeManager } = require('../../runtime_manager');

// Mock os.platform and os.arch
const originalPlatform = os.platform;
const originalArch = os.arch;

try {
    const rm = new RuntimeManager();
    
    // Test windows
    os.platform = () => 'win32';
    os.arch = () => 'x64';
    let artifact = rm.get_runtime_artifact();
    assert.strictEqual(artifact.platform, 'windows');
    assert.strictEqual(artifact.arch, 'x64');

    // Test linux arm64
    os.platform = () => 'linux';
    os.arch = () => 'arm64';
    artifact = rm.get_runtime_artifact();
    assert.strictEqual(artifact.platform, 'linux');
    assert.strictEqual(artifact.arch, 'arm64');
    
    console.log('platform_resolution_test passed');
} finally {
    os.platform = originalPlatform;
    os.arch = originalArch;
}
