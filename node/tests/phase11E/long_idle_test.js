const fs = require('fs');
const path = require('path');
const { AVAListener } = require('../../../node/listener');
const { isolateTest, cleanupTest } = require('../test_isolation');

async function wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function run() {
    await isolateTest('long_idle');
    try {
        console.log("=== PHASE 11E: LONG DURATION STABILITY ===");
        const fastMode = process.argv.includes('--fast');
    const DURATION_MS = fastMode ? 60 * 1000 : 60 * 60 * 1000; // 1 min or 1 hour
    const POLL_INTERVAL_MS = 30 * 1000;
    
    let listener = new AVAListener({ startPaused: true });
    await listener.start();
    
    console.log(`Starting idle run for ${DURATION_MS / 1000} seconds...`);
    
    const startTime = Date.now();
    const metricsLog = [];
    
    let lastRss = process.memoryUsage().rss;
    let growthTicks = 0;
    
    while (Date.now() - startTime < DURATION_MS) {
        await wait(POLL_INTERVAL_MS);
        
        try {
            const metrics = await listener.getMetrics();
            const nodeMem = process.memoryUsage();
            
            console.log(`[${Math.floor((Date.now() - startTime)/1000)}s] Worker PID: ${metrics.worker_pid}, Heap: ${(nodeMem.heapUsed/1024/1024).toFixed(2)}MB, RSS: ${(nodeMem.rss/1024/1024).toFixed(2)}MB, CPU: ${metrics.cpu_usage_percent}%`);
            
            metricsLog.push({
                timestamp: Date.now(),
                rss_mb: nodeMem.rss / 1024 / 1024,
                heap_mb: nodeMem.heapUsed / 1024 / 1024,
                python_memory_mb: metrics.memory_usage_mb,
                cpu_percent: metrics.cpu_usage_percent,
                worker_pid: metrics.worker_pid
            });
            
            if (nodeMem.rss > lastRss) {
                growthTicks++;
            } else {
                growthTicks = 0;
            }
            lastRss = nodeMem.rss;
            
            if (growthTicks > 10) {
                console.warn("[!] Memory continuously growing for 5 minutes!");
            }
            
        } catch(e) {
            console.error("Failed to get metrics:", e.message);
        }
    }
    
    await listener.stop();
    
    const peakMem = Math.max(...metricsLog.map(m => m.rss_mb));
    const avgMem = metricsLog.reduce((a,b) => a + b.rss_mb, 0) / metricsLog.length;
    const avgCpu = metricsLog.reduce((a,b) => a + b.cpu_percent, 0) / metricsLog.length;
    
    const report = {
        duration_ms: DURATION_MS,
        peak_memory_mb: peakMem,
        average_memory_mb: avgMem,
        memory_growth_mb_per_hour: (metricsLog[metricsLog.length-1].rss_mb - metricsLog[0].rss_mb) * (3600000 / DURATION_MS),
        cpu_idle_percent: avgCpu,
        logs: metricsLog
    };
    
    fs.writeFileSync(path.join(__dirname, '..', '..', '..', 'benchmarks', 'long_run_report.json'), JSON.stringify(report, null, 2));
    console.log("Long run complete. Report saved.");
    } finally {
        await cleanupTest('long_idle');
    }
}

run().then(() => process.exit(0)).catch(e => {
    console.error("Test failed:", e);
    process.exit(1);
});
