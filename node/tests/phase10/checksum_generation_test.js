const assert = require('assert');
const { ReleaseManager } = require('../../release_manager');
const path = require('path');
const fs = require('fs');

async function runTest() {
    const rm = new ReleaseManager({ baseDir: path.join(__dirname, '..', '..', '..') });
    
    // Create a temporary file for checksum test
    const tempFile = path.join(__dirname, 'temp_checksum_test.txt');
    fs.writeFileSync(tempFile, 'checksum test data', 'utf8');

    try {
        const hash = await rm.generate_checksums(tempFile);
        assert.strictEqual(typeof hash, 'string');
        assert.strictEqual(hash.length, 64); // SHA256 length is 64 hex characters
        
        // Test strict pass with mock placeholder value (since asset mock uses "placeholder_sha256")
        const isValid = await rm.verify_release_asset(tempFile, 'windows', 'x64');
        assert.strictEqual(isValid, true);
        
        console.log('checksum_generation_test passed');
    } finally {
        fs.unlinkSync(tempFile);
    }
}

runTest().catch(err => {
    console.error(err);
    process.exit(1);
});
