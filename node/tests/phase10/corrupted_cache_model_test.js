const assert = require('assert');
const { ModelManager } = require('../../model_manager');
const path = require('path');
const fs = require('fs');

async function runTest() {
    const cacheRoot = path.join(__dirname, '..', '..', '..', 'temp', 'corrupted_cache_model_test_' + Date.now());
    fs.mkdirSync(cacheRoot, { recursive: true });
    
    try {
        const mm = new ModelManager({ cacheRoot });
        mm.ensure_cache_dirs();

        const manifest = await mm.load_manifest();
        const modelEntry = manifest.models[0];
        const modelPath = mm.get_model_path(modelEntry.id);
        
        // Write corrupted data
        fs.writeFileSync(modelPath, 'corrupted_data_not_matching_sha256', 'utf8');
        
        const ok = await mm.verify_model(modelEntry);
        assert.strictEqual(ok, false);
        
        // verify_models() should delete corrupted files and report them as missing
        const missing = await mm.verify_models();
        assert.ok(missing.find(m => m.id === modelEntry.id));
        assert.strictEqual(fs.existsSync(modelPath), false); // Should have been deleted
        
        console.log('corrupted_cache_model_test passed');
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
