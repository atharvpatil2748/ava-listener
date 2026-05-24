const cp = require('child_process');
const os = require('os');
const fs = require('fs');
const path = require('path');
const { PathManager } = require('../path_manager');

const trackedProcesses = new Map();
const origSpawn = cp.spawn;
cp.spawn = function(...args) {
    const child = origSpawn.apply(this, args);
    if (child.pid) {
        let cmdStr = args[0];
        if (args[1] && Array.isArray(args[1])) {
            cmdStr += ' ' + args[1].join(' ');
        }
        trackedProcesses.set(child.pid, { pid: child.pid, cmd: cmdStr });
        child.on('exit', () => trackedProcesses.delete(child.pid));
        child.on('error', () => trackedProcesses.delete(child.pid));
    }
    return child;
};

function getMetrics(activeProcs) {
    let pythonCount = 0;
    let nodeCount = 0;
    const workerPids = [];
    
    for (const proc of activeProcs) {
        const lowerCmd = proc.cmd.toLowerCase();
        if (lowerCmd.includes('python')) {
            pythonCount++;
            workerPids.push(proc.pid);
        }
        if (lowerCmd.includes('node')) {
            nodeCount++;
        }
    }
    
    const nodeMem = process.memoryUsage();
    return {
        active_python_process_count: pythonCount,
        active_node_process_count: nodeCount,
        active_worker_pids: workerPids,
        rss_memory_mb: nodeMem.rss / 1024 / 1024,
        heap_memory_mb: nodeMem.heapUsed / 1024 / 1024,
        system_ram_free_mb: os.freemem() / 1024 / 1024,
        system_ram_total_mb: os.totalmem() / 1024 / 1024
    };
}

function enumerateAvaProcesses(forceScan = false) {
    if (!forceScan) {
        return Array.from(trackedProcesses.values());
    }

    const activeProcs = [];
    try {
        let lines = [];
        if (os.platform() === 'win32') {
            const out = cp.execSync('wmic process get processid,commandline /format:csv', {encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore']});
            lines = out.split('\n').slice(1);
        } else {
            const out = cp.execSync('ps -eo pid,command', {encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore']});
            lines = out.split('\n').slice(1);
        }

        for (const line of lines) {
            if (!line.trim()) continue;
            let pid, cmd;
            if (os.platform() === 'win32') {
                const parts = line.split(',');
                if (parts.length >= 3) {
                    const pidStr = parts[parts.length - 1].trim();
                    cmd = parts.slice(1, -1).join(',').trim();
                    pid = parseInt(pidStr, 10);
                }
            } else {
                const parts = line.trim().split(/\s+/);
                if (parts.length >= 2) {
                    pid = parseInt(parts[0], 10);
                    cmd = parts.slice(1).join(' ');
                }
            }

            if (pid && !isNaN(pid)) {
                if (pid === process.pid || pid === process.ppid) continue;
                
                const lowerCmd = cmd.toLowerCase();
                const isPythonAva = lowerCmd.includes('python') && (lowerCmd.includes('runtime.main') || lowerCmd.includes('worker_process') || lowerCmd.includes('ava-listener'));
                const isNodeAva = lowerCmd.includes('node') && lowerCmd.includes('ava-listener') && (lowerCmd.includes('test') || lowerCmd.includes('benchmark'));
                const isRunner = lowerCmd.includes('run_phase');

                if ((isPythonAva || isNodeAva) && !isRunner && !lowerCmd.includes('code.exe') && !lowerCmd.includes('vscode')) {
                    activeProcs.push({pid, cmd});
                }
            }
        }
    } catch (e) {
        console.error("Failed to enumerate processes:", e.message);
    }
    return activeProcs;
}

function killProcess(pid) {
    try {
        if (os.platform() === 'win32') {
            cp.execSync(`taskkill /F /T /PID ${pid}`, { stdio: 'ignore' });
        } else {
            process.kill(pid, 'SIGKILL');
        }
    } catch(e) {}
}

function removeStaleLocks() {
    try {
        const cacheDir = path.join(PathManager.get_package_root(), '.ava_cache');
        if (fs.existsSync(cacheDir)) {
            const files = fs.readdirSync(cacheDir);
            for (const f of files) {
                if (f.endsWith('.lock')) {
                    fs.unlinkSync(path.join(cacheDir, f));
                }
            }
        }
    } catch(e) {}
}

async function isolateTest(testName) {
    console.log(`\n[Isolation] Preparing environment for ${testName}...`);
    
    const tScanStart = performance.now();
    const procs = enumerateAvaProcesses(true);
    const process_scan_ms = performance.now() - tScanStart;
    
    const metrics = getMetrics(procs);
    
    const outDir = path.join(PathManager.get_package_root(), 'benchmarks');
    if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, {recursive: true});
    fs.writeFileSync(path.join(outDir, 'pre_test_memory.json'), JSON.stringify(metrics, null, 2));
    
    const tCleanupStart = performance.now();
    for (const proc of procs) {
        console.log(`[Isolation] Terminating stale process ${proc.pid} (${proc.cmd.substring(0, 80)})`);
        killProcess(proc.pid);
    }
    const cleanup_ms = performance.now() - tCleanupStart;
    
    const tLockStart = performance.now();
    removeStaleLocks();
    const lock_cleanup_ms = performance.now() - tLockStart;
    
    trackedProcesses.clear();
    
    try {
        const breakdownPath = path.join(outDir, 'startup_breakdown.json');
        let breakdown = {};
        if (fs.existsSync(breakdownPath)) {
            breakdown = JSON.parse(fs.readFileSync(breakdownPath, 'utf8'));
        }
        breakdown.process_scan_ms = process_scan_ms;
        breakdown.cleanup_ms = cleanup_ms;
        breakdown.lock_cleanup_ms = lock_cleanup_ms;
        fs.writeFileSync(breakdownPath, JSON.stringify(breakdown, null, 2));
    } catch(e) {
        console.error("Failed to write breakdown:", e.message);
    }
}

async function cleanupTest(testName) {
    console.log(`\n[Isolation] Cleaning up environment for ${testName}...`);
    for (const [pid, proc] of trackedProcesses.entries()) {
        killProcess(pid);
    }
    trackedProcesses.clear();
    
    const procs = enumerateAvaProcesses(true);
    for (const proc of procs) {
        killProcess(proc.pid);
    }
    
    const postProcs = enumerateAvaProcesses(true);
    const metrics = getMetrics(postProcs);
    
    const outDir = path.join(PathManager.get_package_root(), 'benchmarks');
    if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, {recursive: true});
    
    fs.writeFileSync(path.join(outDir, 'post_test_memory.json'), JSON.stringify(metrics, null, 2));
    
    const cleanupReport = {
        test_name: testName,
        processes_terminated: trackedProcesses.size + procs.length,
        pre_test_metrics_file: 'pre_test_memory.json',
        post_test_metrics_file: 'post_test_memory.json'
    };
    fs.writeFileSync(path.join(outDir, 'process_cleanup_report.json'), JSON.stringify(cleanupReport, null, 2));
    console.log(`[Isolation] Cleanup complete.\n`);
}

async function recordCycleMetrics(cycleNum, listener) {
    const t0 = performance.now();
    const procs = enumerateAvaProcesses();
    const cycle_scan_ms = performance.now() - t0;
    
    const metrics = getMetrics(procs);
    const nodeMem = process.memoryUsage();
    
    let workerPid = null;
    if (listener && listener.lifecycle && listener.lifecycle.processManager && listener.lifecycle.processManager.proc) {
        workerPid = listener.lifecycle.processManager.proc.pid;
    }
    if (!workerPid && metrics.active_worker_pids.length > 0) {
        workerPid = metrics.active_worker_pids[0];
    }
    
    const handles = process._getActiveHandles ? process._getActiveHandles().length : 0;
    
    // Estimate websocket handles if possible, or just look for WS objects
    let wsCount = 0;
    if (process._getActiveHandles) {
        const activeHandles = process._getActiveHandles();
        wsCount = activeHandles.filter(h => h && h.constructor && h.constructor.name === 'Socket' && h._httpMessage).length;
    }

    const cycleData = {
        cycle: cycleNum,
        rss_mb: nodeMem.rss / 1024 / 1024,
        heap_mb: nodeMem.heapUsed / 1024 / 1024,
        handles: handles,
        active_websockets: wsCount,
        workers: metrics.active_python_process_count,
        pid: workerPid,
        system_ram_mb: (os.totalmem() - os.freemem()) / 1024 / 1024,
        scan_ms: cycle_scan_ms
    };

    const outDir = path.join(PathManager.get_package_root(), 'benchmarks');
    if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, {recursive: true});
    
    const timelinePath = path.join(outDir, 'resource_timeline.json');
    let timeline = [];
    if (fs.existsSync(timelinePath)) {
        try {
            const data = fs.readFileSync(timelinePath, 'utf8');
            if (data.trim()) timeline = JSON.parse(data);
        } catch(e) {}
    }
    
    // If it's cycle 1, we might want to start fresh.
    if (cycleNum === 1) timeline = [];
    
    timeline.push(cycleData);
    fs.writeFileSync(timelinePath, JSON.stringify(timeline, null, 2));
}

module.exports = { isolateTest, cleanupTest, recordCycleMetrics };
