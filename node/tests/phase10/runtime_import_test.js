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
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ava-test-'));
    
    // Write package.json so npm install works without modifying global tree
    fs.writeFileSync(path.join(tempDir, 'package.json'), JSON.stringify({
        name: "test-consumer",
        version: "1.0.0"
    }));
    
    cp.execSync(`npm install ${tarballPath}`, { cwd: tempDir, stdio: 'pipe' });
    
    console.log("3. Verifying package payload...");
    const pkgRoot = path.join(tempDir, 'node_modules', 'ava-listener');
    if (!fs.existsSync(path.join(pkgRoot, 'runtime', 'main.py'))) {
        throw new Error("runtime/main.py missing from payload");
    }
    if (!fs.existsSync(path.join(pkgRoot, 'utils', 'logger.py'))) {
        throw new Error("utils/logger.py missing from payload");
    }
    
    console.log("4. Executing require('ava-listener')...");
    try {
        const sdk = require(pkgRoot);
        if (!sdk || !sdk.AVAListener) {
            throw new Error("AVAListener export missing");
        }
        
        const listener = new sdk.AVAListener();
        if (!listener) {
            throw new Error("Failed to instantiate AVAListener");
        }
        
        console.log("Execution successful!");
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
