const fs = require('fs');
const path = require('path');
const os = require('os');
const { AVAListener } = require('../../../node/listener');
const benchmark = require('../../../node/benchmark');
const { isolateTest, cleanupTest } = require('../test_isolation');

async function wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function run() {
    await isolateTest('worker_restart_benchmark');
    try {
        console.log("=== PHASE 11: RESTART BENCHMARK ===");

    // We can use the default cache since we assume it's already downloaded.
    const listener = new AVAListener({
        startPaused: true
    });

    console.log("[1] Initial Startup...");
    await listener.start(null, { debug: false });
    
    // Simulate a worker crash
    console.log("[2] Forcing worker crash via IPC / Process Kill...");
    
    // Forcefully crash the Python worker to trigger the restart logic
    if (listener.lifecycle.processManager.proc) {
        // Send a crash command if supported, else we can't easily crash the worker from node without IPC.
        try {
            console.log("-> Sending crash_worker command to supervisor...");
            const envelope = require('../../../node/protocol/messages').createEnvelope('crash_worker');
            listener.lifecycle.transport.send(envelope);
            
            await new Promise(resolve => {
                const onStatus = (data) => {
                    if (data && data.status === 'ready') {
                        listener.removeListener('status', onStatus);
                        benchmark.mark('restart_end');
                        benchmark.measure('restart_recovery_ms', 'restart_start', 'restart_end');
                        resolve();
                    }
                };
                listener.on('status', onStatus);
                benchmark.mark('restart_start');
            });
        } catch (e) {
            console.log("Failed to kill worker process:", e);
        }
    }
    
    // We already have restart benchmark marks in lifecycle.js
    let recoveryMs = benchmark.getMetric('restart_recovery_ms');
    console.log(`Recovery took: ${recoveryMs}ms`);

    await listener.stop();
    benchmark.export('restart_benchmark_results.json');
    console.log("\nRestart Benchmark complete.");
    } finally {
        await cleanupTest('worker_restart_benchmark');
    }
}

run().catch(err => {
    console.error("Benchmark failed:", err);
    process.exit(1);
});
