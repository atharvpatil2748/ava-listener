const { AVAListener } = require('../../../node/listener');
const { isolateTest, cleanupTest, recordCycleMetrics } = require('../test_isolation');

async function run() {
    await isolateTest('stress_start_stop');
    try {
        console.log("=== PHASE 11: STRESS START/STOP ===");
    
    // We do 10 loops for sanity, scale up manually if 100 is needed
    const CYCLES = 10;
    
    let listener = new AVAListener({
        startPaused: true
    });

    for (let i = 1; i <= CYCLES; i++) {
        console.log(`\n--- Cycle ${i}/${CYCLES} ---`);
        const t0 = Date.now();
        await listener.start(null, { debug: false });
        console.log(`Started in ${Date.now() - t0}ms`);
        
        await listener.stop();
        console.log(`Stopped.`);
        await recordCycleMetrics(i, listener);
    }

    console.log("\nStress Start/Stop Benchmark complete.");
    } finally {
        await cleanupTest('stress_start_stop');
    }
}

run().catch(err => {
    console.error("Stress Test failed:", err);
    process.exit(1);
});
