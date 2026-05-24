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
    await isolateTest('startup_benchmark');
    try {
        console.log("=== PHASE 11: STARTUP BENCHMARK ===");

    // 1. COLD STARTUP (empty cache)
    const coldCacheDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ava-bench-cold-'));
    console.log(`\n[1] Cold Startup (Cache: ${coldCacheDir})`);
    
    let listener = new AVAListener({
        cacheRoot: coldCacheDir,
        startPaused: true
    });

    let t0 = Date.now();
    await listener.start(null, { debug: false });
    let coldStartMs = Date.now() - t0;
    
    console.log(`Cold start took: ${coldStartMs}ms`);
    benchmark.setMetric('cold_start_ms', coldStartMs);

    await wait(500); // Give worker time to settle

    // Get metrics from Python runtime
    let metrics = await listener.getMetrics();
    benchmark.setMetric('idle_memory_mb_cold', metrics.memory_usage_mb);
    benchmark.setMetric('idle_cpu_percent_cold', metrics.cpu_usage_percent);

    await listener.stop();

    // 2. WARM STARTUP (same cache)
    console.log(`\n[2] Warm Startup (Cache: ${coldCacheDir})`);
    
    listener = new AVAListener({
        cacheRoot: coldCacheDir,
        startPaused: true
    });

    t0 = Date.now();
    await listener.start(null, { debug: false });
    let warmStartMs = Date.now() - t0;

    console.log(`Warm start took: ${warmStartMs}ms`);
    benchmark.setMetric('warm_start_ms', warmStartMs);

    await wait(500);

    metrics = await listener.getMetrics();
    benchmark.setMetric('idle_memory_mb_warm', metrics.memory_usage_mb);
    benchmark.setMetric('idle_cpu_percent_warm', metrics.cpu_usage_percent);

    await listener.stop();
    
    // Cleanup
    try {
        fs.rmSync(coldCacheDir, { recursive: true, force: true });
    } catch (e) {}

    benchmark.export('startup_benchmark_results.json');
    console.log("\nBenchmark complete. Results saved to startup_benchmark_results.json.");
    } finally {
        await cleanupTest('startup_benchmark');
    }
}

run().catch(err => {
    console.error("Benchmark failed:", err);
    process.exit(1);
});
