const { AVAListener } = require('../../node/index');
const path = require('path');

async function testDebugOverlay() {
    console.log("Testing debug: false...");
    const listenerNormal = new AVAListener({
        profile: path.join(__dirname, '../../profiles/arvsal.json'),
        debug: false
    });
    
    await listenerNormal.start();
    const normalConfig = await listenerNormal.getEffectiveConfig();
    
    if (normalConfig.values['transcription.enableDebug'] === true) {
        throw new Error("Normal config has enableDebug=true");
    }
    await listenerNormal.stop();
    console.log("Normal config OK.");
    
    console.log("Testing debug: true...");
    const listenerDebug = new AVAListener({
        profile: path.join(__dirname, '../../profiles/arvsal.json'),
        debug: true
    });
    
    await listenerDebug.start();
    const debugConfig = await listenerDebug.getEffectiveConfig();
    
    if (debugConfig.values['transcription.enableDebug'] !== true) {
        throw new Error("Debug config missing enableDebug=true");
    }
    if (debugConfig.values['diagnostics.enableInternalTrace'] !== true) {
        throw new Error("Debug config missing enableInternalTrace=true");
    }
    // Verify arvsal values unchanged
    if (debugConfig.values['vad.sileroThreshold'] === undefined) {
         throw new Error("Profile inheritance broken, missing vad.sileroThreshold");
    }
    await listenerDebug.stop();
    console.log("Debug config OK.");
    console.log("All tests passed!");
}

testDebugOverlay().catch(err => {
    console.error(err);
    process.exit(1);
});
