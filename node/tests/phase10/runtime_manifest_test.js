const assert = require('assert');
const path = require('path');
const fs = require('fs');

const manifestPath = path.join(__dirname, '..', '..', '..', 'runtime', 'manifests', 'platform_manifest.json');
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));

assert.strictEqual(manifest.manifestVersion, 1);
assert.ok(Array.isArray(manifest.artifacts));

for (const artifact of manifest.artifacts) {
    assert.ok(artifact.platform);
    assert.ok(artifact.arch);
    assert.ok(artifact.assetName);
    assert.strictEqual(typeof artifact.sha256, 'string');
    assert.strictEqual(typeof artifact.size, 'number');
    assert.strictEqual(typeof artifact.pythonVersion, 'string');
    assert.ok(Array.isArray(artifact.dependencies));
}

console.log('runtime_manifest_test passed');
