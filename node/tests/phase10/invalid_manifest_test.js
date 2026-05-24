const assert = require('assert');
const { ReleaseManager, ReleaseManifestError } = require('../../release_manager');
const path = require('path');
const fs = require('fs');

const baseDir = path.join(__dirname, '..', '..', '..');
const rm = new ReleaseManager({ baseDir });
const manifestPath = path.join(baseDir, 'runtime', 'manifests', 'release_manifest.json');
const originalManifest = fs.readFileSync(manifestPath, 'utf8');

function testManifest(modifierFn, expectedErrorFragment) {
    try {
        const mockManifest = JSON.parse(originalManifest);
        modifierFn(mockManifest);
        fs.writeFileSync(manifestPath, JSON.stringify(mockManifest), 'utf8');
        rm.load_release_manifest();
        assert.fail('Expected ReleaseManifestError was not thrown');
    } catch (err) {
        if (err.name !== 'ReleaseManifestError') {
            assert.fail('Expected ReleaseManifestError, got: ' + err.name);
        }
        if (expectedErrorFragment && !err.message.includes(expectedErrorFragment)) {
            assert.fail(`Expected error message to include "${expectedErrorFragment}", but got: ${err.message}`);
        }
    } finally {
        fs.writeFileSync(manifestPath, originalManifest, 'utf8');
    }
}

// 1. Missing fields
testManifest(m => delete m.releaseVersion, 'Missing or invalid releaseVersion');
testManifest(m => delete m.manifestVersion, 'Missing or invalid manifestVersion');
testManifest(m => delete m.artifacts, 'Missing or invalid artifacts array');

// 2. Invalid sha256
testManifest(m => { m.artifacts[0].sha256 = 'short_hash'; }, 'Invalid sha256 checksum');
testManifest(m => { delete m.artifacts[0].sha256; }, 'Invalid sha256 checksum');

// 3. Invalid platform values
testManifest(m => { m.artifacts[0].platform = 'amiga'; }, 'Invalid platform value: amiga');

// 4. Malformed JSON
try {
    fs.writeFileSync(manifestPath, '{ malformed json ', 'utf8');
    rm.load_release_manifest();
    assert.fail('Expected ReleaseManifestError was not thrown');
} catch (err) {
    assert.strictEqual(err.name, 'ReleaseManifestError');
    assert.ok(err.message.includes('Malformed JSON'));
} finally {
    fs.writeFileSync(manifestPath, originalManifest, 'utf8');
}

console.log('invalid_manifest_test passed');
