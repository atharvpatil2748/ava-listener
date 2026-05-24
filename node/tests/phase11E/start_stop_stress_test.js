const fs = require('fs');
const path = require('path');
const { AVAListener } = require('../../../node/listener');
const { isolateTest, cleanupTest, recordCycleMetrics } = require('../test_isolation');

async function run() {
    await isolateTest('start_stop_stress');
    try {
        console.log("=== PHASE 11E: START/STOP STRESS ===");
        const fastMode = process.argv.includes('--fast');
    const CYCLES = fastMode ? 5 : 100;
    
    let listener = new AVAListener({ startPaused: true });
    
    let successes = 0;
    let failures = 0;
    
    for (let i = 1; i <= CYCLES; i++) {
        console.log(`\n--- Cycle ${i}/${CYCLES} ---`);
        try {
            await listener.start(null, { debug: false });
            await listener.stop();
            successes++;
        } catch (e) {
            console.error("Failed cycle:", e.message);
            failures++;
        }
        await recordCycleMetrics(i, listener);
    }
    
    const report = {
        cycles: CYCLES,
        start_stop_success_rate: (successes / CYCLES) * 100,
        failures: failures
    };
    
    fs.writeFileSync(path.join(__dirname, '..', '..', '..', 'benchmarks', 'start_stop_report.json'), JSON.stringify(report, null, 2));
    console.log("\nStart/Stop Stress Benchmark complete. Report saved.");
    } finally {
        await cleanupTest('start_stop_stress');
    }
}

run().then(() => process.exit(0)).catch(err => {
    console.error("Stress Test failed:", err);
    process.exit(1);
});
