const assert = require('assert');
const path = require('path');
const fs = require('fs');

const manifestPath = path.join(__dirname, '..', '..', '..', 'runtime', 'manifests', 'release_manifest.json');
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));

assert.strictEqual(manifest.manifestVersion, 1);
assert.ok(manifest.releaseVersion);
assert.ok(Array.isArray(manifest.artifacts));

for (const artifact of manifest.artifacts) {
    assert.ok(artifact.assetName);
    assert.ok(artifact.platform);
    assert.ok(artifact.arch);
    assert.strictEqual(typeof artifact.sha256, 'string');
    assert.strictEqual(typeof artifact.size, 'number');
    assert.ok(artifact.url.startsWith('http'));
}

console.log('release_manifest_test passed');
