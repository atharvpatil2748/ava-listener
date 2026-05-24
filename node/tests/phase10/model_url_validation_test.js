const assert = require('assert');
const { ModelManager } = require('../../model_manager');

async function runTest() {
    const mm = new ModelManager();
    
    const validUrl = 'https://github.com/microsoft/onnxruntime/releases/download/v1.16.3/onnxruntime-win-x64-1.16.3.zip';
    const missingUrl = 'https://github.com/microsoft/onnxruntime/releases/download/v1.16.3/this-file-does-not-exist.zip';
    
    // Test 1: Valid asset URL
    mm.load_manifest = async () => ({
        models: [{ id: 'test1', downloadUrl: validUrl }]
    });
    const ok = await mm.validate_manifest_urls();
    assert.strictEqual(ok, true);

    mm._manifestValidated = false;
    mm.load_manifest = async () => ({
        models: [{ id: 'test2', downloadUrl: missingUrl }]
    });
    try {
        await mm.validate_manifest_urls();
        assert.fail('Should have thrown on 404');
    } catch (err) {
        assert.ok(err.message.includes('404 Not Found'));
    }



    console.log('model_url_validation_test passed');
}

runTest().catch(err => {
    console.error(err);
    process.exit(1);
});
