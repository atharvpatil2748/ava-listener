const fs = require('fs');
const path = require('path');
const { AVAListener } = require('../../../node/listener');
const { isolateTest, cleanupTest, recordCycleMetrics } = require('../test_isolation');

async function wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function run() {
    await isolateTest('recovery_stress');
    try {
        console.log("=== PHASE 11E: RECOVERY STRESS ===");
        const fastMode = process.argv.includes('--fast');
    const CYCLES = fastMode ? 2 : 20;
    const WAIT_BETWEEN_CRASHES = fastMode ? 5000 : 120000; // 5s or 2 mins
    
    let listener = new AVAListener({ startPaused: true });
    await listener.start();
    
    console.log(`Starting ${CYCLES} crash cycles...`);
    
    let successes = 0;
    let failures = 0;
    let recoveryTimes = [];
    
    for (let i = 1; i <= CYCLES; i++) {
        await wait(WAIT_BETWEEN_CRASHES);
        console.log(`\n--- Cycle ${i}/${CYCLES} ---`);
        
        let recoverPromise = new Promise(resolve => {
            const handler = (msg) => {
                if ((msg.type === 'status' || msg.event === 'status') && msg.payload && (msg.payload.state === 'READY' || msg.payload.state === 'ACTIVE' || msg.payload.status === 'READY' || msg.payload.status === 'ready')) {
                    listener.lifecycle.transport.removeListener('message', handler);
                    resolve(true);
                }
            };
            listener.lifecycle.transport.on('message', handler);
        });
        
        const t0 = Date.now();
        console.log("Crashing worker...");
        listener.lifecycle.transport.send({ type: 'crash_worker', schemaVersion: 1, timestamp: Date.now(), correlationId: `crash-${i}`, payload: {} });
        
        const success = await recoverPromise;
        const latency = Date.now() - t0;
        
        if (success) {
            successes++;
            recoveryTimes.push(latency);
            console.log(`Recovered in ${latency}ms`);
        } else {
            failures++;
            console.error(`Recovery failed!`);
        }
        await recordCycleMetrics(i, listener);
    }
    
    await listener.stop();
    
    const avgLatency = recoveryTimes.length > 0 ? recoveryTimes.reduce((a,b)=>a+b, 0) / recoveryTimes.length : 0;
    
    const report = {
        cycles: CYCLES,
        restart_success_rate: (successes / CYCLES) * 100,
        recovery_failures: failures,
        average_recovery_latency_ms: avgLatency,
        latencies: recoveryTimes
    };
    
    fs.writeFileSync(path.join(__dirname, '..', '..', '..', 'benchmarks', 'recovery_report.json'), JSON.stringify(report, null, 2));
    console.log("Recovery stress complete. Report saved.");
    } finally {
        await cleanupTest('recovery_stress');
    }
}

run().then(() => process.exit(0)).catch(e => {
    console.error("Test failed:", e);
    process.exit(1);
});
