const assert = require('assert');
const os = require('os');
const { RuntimeManager, UnsupportedPlatformError } = require('../../runtime_manager');

const originalPlatform = os.platform;
const originalArch = os.arch;

try {
    const rm = new RuntimeManager();
    
    // Test freebsd
    os.platform = () => 'freebsd';
    os.arch = () => 'x64';
    
    assert.throws(() => {
        rm.get_runtime_artifact();
    }, UnsupportedPlatformError);

    // Test unsupported windows arch
    os.platform = () => 'win32';
    os.arch = () => 'ia32';
    
    assert.throws(() => {
        rm.get_runtime_artifact();
    }, UnsupportedPlatformError);

    console.log('unsupported_platform_test passed');
} finally {
    os.platform = originalPlatform;
    os.arch = originalArch;
}
