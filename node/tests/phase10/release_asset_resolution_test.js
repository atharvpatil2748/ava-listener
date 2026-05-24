const assert = require('assert');
const { ReleaseManager } = require('../../release_manager');
const path = require('path');

const rm = new ReleaseManager({ baseDir: path.join(__dirname, '..', '..', '..') });

// Test resolution of supported platforms
const windowsAsset = rm.get_release_asset('windows', 'x64');
assert.strictEqual(windowsAsset.assetName, 'ava-runtime-windows-x64.zip');

const macosAsset = rm.get_release_asset('macos', 'arm64');
assert.strictEqual(macosAsset.assetName, 'ava-runtime-macos-arm64.tar.gz');

const url = rm.resolve_download_url('linux', 'x64');
assert.ok(url.includes('linux-x64.tar.gz'));

// Test resolution of unsupported platforms
assert.throws(() => {
    rm.get_release_asset('freebsd', 'x64');
}, /No release asset found/);

console.log('release_asset_resolution_test passed');
