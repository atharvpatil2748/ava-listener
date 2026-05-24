const assert = require('assert');
const { ReleaseManager } = require('../../release_manager');
const path = require('path');

const rm = new ReleaseManager({ baseDir: path.join(__dirname, '..', '..', '..') });

// Verify releaseVersion mapping and platform/arch selection
const manifest = rm.load_release_manifest();
assert.strictEqual(manifest.releaseVersion, '1.0.0');

const url = rm.resolve_download_url('windows', 'x64');
assert.ok(url.includes('v1.0.0'));
assert.ok(url.includes('ava-runtime-windows-x64.zip'));

const linuxUrl = rm.resolve_download_url('linux', 'arm64');
assert.ok(linuxUrl.includes('v1.0.0'));
assert.ok(linuxUrl.includes('ava-runtime-linux-arm64.tar.gz'));

console.log('github_asset_resolution_test passed');
