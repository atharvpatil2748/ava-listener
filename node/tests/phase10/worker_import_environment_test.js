const fs = require('fs');
const path = require('path');
const cp = require('child_process');
const os = require('os');

async function run() {
    const rootDir = path.resolve(__dirname, '../../..');
    
    console.log("1. Running npm pack...");
    cp.execSync('npm pack', { cwd: rootDir, stdio: 'pipe' });
    
    const tarball = fs.readdirSync(rootDir).find(f => f.endsWith('.tgz'));
    if (!tarball) throw new Error("Tarball not found");
    const tarballPath = path.join(rootDir, tarball);
    
    console.log("2. Creating isolated install...");
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ava-worker-test-'));
    
    // Write package.json so npm install works without modifying global tree
    fs.writeFileSync(path.join(tempDir, 'package.json'), JSON.stringify({
        name: "test-consumer",
        version: "1.0.0"
    }));
    
    cp.execSync(`npm install ${tarballPath}`, { cwd: tempDir, stdio: 'pipe' });
    
    console.log("3. Verifying package payload...");
    const pkgRoot = path.join(tempDir, 'node_modules', 'ava-listener');
    const required = ['asr', 'runtime/vad', 'core', 'utils', 'runtime', 'runtime/kernel'];
    for (const req of required) {
        if (!fs.existsSync(path.join(pkgRoot, req))) {
            throw new Error(`${req} missing from payload`);
        }
    }
    
    console.log("4. Spawning worker process natively...");
    try {
        const pythonExec = 'python';
        // Test module execution environment just like supervisor does
        const output = cp.execSync(`${pythonExec} -m runtime.worker.worker_process --help`, { 
            cwd: pkgRoot, 
            encoding: 'utf8',
            stdio: 'pipe'
        });
        
        console.log("Execution successful! Worker environment is healthy.");
        console.log("Test Passed.");
    } catch (err) {
        console.error("Execution failed!");
        console.error(err.stderr || err.message || err);
        process.exit(1);
    }
}

run().catch(err => {
    console.error(err);
    process.exit(1);
});
