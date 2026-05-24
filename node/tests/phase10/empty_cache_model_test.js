const assert = require('assert');
const { ModelManager } = require('../../model_manager');
const path = require('path');
const fs = require('fs');

async function runTest() {
    const cacheRoot = path.join(__dirname, '..', '..', '..', 'temp', 'empty_cache_model_test_' + Date.now());
    fs.mkdirSync(cacheRoot, { recursive: true });
    
    try {
        const mm = new ModelManager({ cacheRoot });
        
        // ensure_cache_dirs shouldn't fail
        mm.ensure_cache_dirs();
        assert.ok(fs.existsSync(path.join(cacheRoot, 'models')));
        assert.ok(fs.existsSync(path.join(cacheRoot, 'metadata')));

        // Load manifest
        const manifest = await mm.load_manifest();
        assert.ok(manifest.models.length > 0);
        
        // Verify models against an empty cache (should all be missing)
        const missing = await mm.verify_models();
        assert.strictEqual(missing.length, manifest.models.length);
        
        console.log('empty_cache_model_test passed');
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
