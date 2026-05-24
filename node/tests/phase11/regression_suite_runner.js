const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const BENCHMARKS_DIR = path.join(__dirname, '..', '..', '..', 'benchmarks');
const HISTORY_FILE = path.join(BENCHMARKS_DIR, 'history.json');
const RESULTS_FILE = path.join(__dirname, '..', '..', 'benchmark_results.json');
const RESTART_RESULTS_FILE = path.join(__dirname, '..', '..', 'restart_benchmark_results.json');
const DIFF_FILE = path.join(__dirname, '..', '..', 'benchmark_diff.json');
const REPORT_FILE = path.join(__dirname, '..', '..', 'regression_report.json');

const TESTS = [
    '../phase10/workflow_validation_test.js',
    '../phase10/runtime_payload_test.js',
    '../phase10/model_url_validation_test.js',
    './startup_benchmark_test.js',
    './worker_restart_benchmark_test.js',
    './stress_start_stop_test.js'
];

function ensureBenchmarksDir() {
    if (!fs.existsSync(BENCHMARKS_DIR)) {
        fs.mkdirSync(BENCHMARKS_DIR, { recursive: true });
    }
}

function loadHistory() {
    ensureBenchmarksDir();
    if (fs.existsSync(HISTORY_FILE)) {
        return JSON.parse(fs.readFileSync(HISTORY_FILE, 'utf8'));
    }
    return [];
}

function saveHistory(history) {
    fs.writeFileSync(HISTORY_FILE, JSON.stringify(history, null, 2));
}

function runTests() {
    console.log("=== PHASE 11: REGRESSION SUITE RUNNER ===");
    for (const test of TESTS) {
        console.log(`\n=> Running ${test}...`);
        try {
            execSync(`node ${path.join(__dirname, test)}`, { stdio: 'inherit', cwd: path.join(__dirname, '..', '..') });
        } catch (e) {
            console.error(`\n[!] Test ${test} FAILED.`);
            process.exit(1);
        }
    }
    console.log("\n[+] All tests passed successfully!");
}

function computeDiff(baseline, current) {
    const diff = {};
    let hasRegression = false;
    let regressionDetails = [];

    const keys = new Set([...Object.keys(baseline || {}), ...Object.keys(current)]);
    for (const key of keys) {
        const b = baseline ? baseline[key] : null;
        const c = current[key];
        
        if (typeof c !== 'number') continue;
        
        if (b != null && typeof b === 'number') {
            const delta = c - b;
            const pct = (delta / b) * 100;
            diff[key] = { baseline: b, current: c, delta, pct };
            
            // Check for >10% regression (only on latency metrics, CPU/memory is jittery)
            if (pct > 10 && key.endsWith('_ms')) {
                hasRegression = true;
                regressionDetails.push(`${key} degraded by ${pct.toFixed(1)}% (${b.toFixed(1)}ms -> ${c.toFixed(1)}ms)`);
            }
        } else {
            diff[key] = { baseline: null, current: c, delta: null, pct: null };
        }
    }
    
    return { diff, hasRegression, regressionDetails };
}

function collectMetadata() {
    const os = require('os');
    let pythonVersion = 'unknown';
    try {
        pythonVersion = execSync('python --version').toString().trim();
    } catch(e) {}
    
    // Retrieve runtime and model versions from config or package.json
    let runtimeVersion = 'unknown';
    try {
        const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, '..', '..', 'package.json'), 'utf8'));
        runtimeVersion = pkg.version || 'unknown';
    } catch(e) {}

    return {
        os: `${os.type()} ${os.release()} ${os.arch()}`,
        cpu: os.cpus()[0].model,
        ram_gb: (os.totalmem() / (1024 ** 3)).toFixed(2),
        python_version: pythonVersion,
        node_version: process.version,
        runtime_version: runtimeVersion,
        model_versions: 'Sherpa ONNX Phase 10' // Baseline indicator
    };
}

function processResults() {
    const startupFile = path.join(__dirname, '..', '..', 'startup_benchmark_results.json');
    const restartFile = path.join(__dirname, '..', '..', 'restart_benchmark_results.json');
    const stressFile = path.join(__dirname, '..', '..', 'stress_benchmark_results.json');

    const results = {};
    if (fs.existsSync(startupFile)) Object.assign(results, JSON.parse(fs.readFileSync(startupFile, 'utf8')));
    if (fs.existsSync(restartFile)) Object.assign(results, JSON.parse(fs.readFileSync(restartFile, 'utf8')));
    if (fs.existsSync(stressFile)) Object.assign(results, JSON.parse(fs.readFileSync(stressFile, 'utf8')));

    if (Object.keys(results).length === 0) {
        console.error("No benchmark results found!");
        process.exit(1);
    }
    
    const timestamp = new Date().toISOString();
    const metadata = collectMetadata();
    
    const history = loadHistory();
    let baseline = null;
    
    // Find the latest successful baseline run
    for (let i = history.length - 1; i >= 0; i--) {
        if (!history[i].failedRegression) {
            baseline = history[i].phase11_baseline || history[i].metrics; // fallback for older format
            break;
        }
    }
    
    console.log("\n=== PERFORMANCE DIFF ===");
    const { diff, hasRegression, regressionDetails } = computeDiff(baseline, results);
    
    for (const [key, stat] of Object.entries(diff)) {
        if (stat.pct != null) {
            const sign = stat.pct > 0 ? '+' : '';
            console.log(`${key}: ${stat.current.toFixed(2)} (${sign}${stat.pct.toFixed(2)}%)`);
        } else {
            console.log(`${key}: ${stat.current.toFixed(2)} (new)`);
        }
    }
    
    fs.writeFileSync(DIFF_FILE, JSON.stringify(diff, null, 2));
    
    const report = {
        timestamp: timestamp,
        passed: !hasRegression,
        details: regressionDetails
    };
    fs.writeFileSync(REPORT_FILE, JSON.stringify(report, null, 2));
    
    const snapshot = {
        phase11_baseline: {
            timestamp: timestamp,
            warm_start_ms: results.warm_start_ms,
            cold_start_ms: results.cold_start_ms,
            worker_restart_ms: results.restart_recovery_ms,
            idle_memory_mb: results.idle_memory_mb_warm || results.idle_memory_mb_cold,
            ...results // Include all metrics
        },
        metadata: metadata,
        failedRegression: hasRegression,
        regressionDetails
    };
    
    history.push(snapshot);
    saveHistory(history);
    
    // Export summaries
    const tableData = {
        timestamp,
        metadata,
        metrics: results
    };
    const tablePath = path.join(BENCHMARKS_DIR, 'benchmark_table.json');
    fs.writeFileSync(tablePath, JSON.stringify(tableData, null, 2));
    
    const mdPath = path.join(BENCHMARKS_DIR, 'benchmark_summary.md');
    const mdContent = `# AVAListener Performance Benchmark

**Date**: ${timestamp}
**Status**: ${hasRegression ? '❌ Regression Detected' : '✅ Passing'}

## System Metadata
- **OS**: ${metadata.os}
- **CPU**: ${metadata.cpu}
- **RAM**: ${metadata.ram_gb} GB
- **Node**: ${metadata.node_version}
- **Python**: ${metadata.python_version}

## Key Metrics
| Metric | Value (ms) |
|--------|------------|
| Cold Start | ${results.cold_start_ms?.toFixed(2) || 'N/A'} |
| Warm Start | ${results.warm_start_ms?.toFixed(2) || 'N/A'} |
| Worker Restart | ${results.restart_recovery_ms?.toFixed(2) || 'N/A'} |
| Model Verification | ${results.model_verification_ms?.toFixed(2) || 'N/A'} |
| Idle Memory | ${snapshot.phase11_baseline.idle_memory_mb?.toFixed(2) || 'N/A'} MB |

## Diff
\`\`\`json
${JSON.stringify(diff, null, 2)}
\`\`\`
`;
    fs.writeFileSync(mdPath, mdContent);
    
    if (hasRegression) {
        console.error("\n[!] PERFORMANCE REGRESSION DETECTED (>10% degradation):");
        regressionDetails.forEach(d => console.error("  - " + d));
        process.exit(1);
    } else {
        console.log("\n[+] No performance regressions detected.");
    }
}

// Check if we want to run tests or just process existing results
if (process.argv.includes('--process-only')) {
    processResults();
} else {
    runTests();
    processResults();
}
