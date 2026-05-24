const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const baseDir = path.join(__dirname, '..', '..', '..');

function runTest() {
    console.log('[TEST] Validating runtime payload inclusion');
    const tempDir = path.join(baseDir, 'temp', 'runtime_payload_test_' + Date.now());
    if (!fs.existsSync(tempDir)) {
        fs.mkdirSync(tempDir, { recursive: true });
    }

    try {
        // 1. Pack the package
        console.log('Running npm pack...');
        const packOutput = execSync('npm pack', { cwd: baseDir, encoding: 'utf8' });
        const tarballName = packOutput.trim().split('\n').pop().trim();
        const tarballPath = path.join(baseDir, tarballName);

        // 2. Validate tarball contents
        console.log('Validating tarball contents...');
        const tarOutput = execSync(`tar -tf "${tarballPath}"`, { encoding: 'utf8' });
        const files = tarOutput.split('\n').map(f => f.trim());

        const requiredFiles = [
            'package/runtime/main.py',
            'package/runtime/supervisor/', // Check directory or files in it
            'package/runtime/worker/'
        ];

        let hasSupervisor = false;
        let hasWorker = false;
        let hasMain = false;

        for (const file of files) {
            if (file === 'package/runtime/main.py') hasMain = true;
            if (file.startsWith('package/runtime/supervisor/')) hasSupervisor = true;
            if (file.startsWith('package/runtime/worker/')) hasWorker = true;
        }

        if (!hasMain) throw new Error('package/runtime/main.py is missing from tarball');
        if (!hasSupervisor) throw new Error('package/runtime/supervisor/ is missing from tarball');
        if (!hasWorker) throw new Error('package/runtime/worker/ is missing from tarball');

        // 3. Extract and check preservation
        console.log('Validating extracted payload...');
        fs.copyFileSync(tarballPath, path.join(tempDir, tarballName));
        fs.writeFileSync(path.join(tempDir, 'package.json'), JSON.stringify({ name: "test-pkg" }));
        execSync(`npm install ./${tarballName} --no-save`, { cwd: tempDir, stdio: 'ignore' });

        const extractedMain = path.join(tempDir, 'node_modules', 'ava-listener', 'runtime', 'main.py');
        const extractedSupervisor = path.join(tempDir, 'node_modules', 'ava-listener', 'runtime', 'supervisor');
        const extractedWorker = path.join(tempDir, 'node_modules', 'ava-listener', 'runtime', 'worker');

        if (!fs.existsSync(extractedMain)) throw new Error('runtime/main.py missing after install');
        if (!fs.existsSync(extractedSupervisor)) throw new Error('runtime/supervisor missing after install');
        if (!fs.existsSync(extractedWorker)) throw new Error('runtime/worker missing after install');

        console.log('[TEST PASSED] Runtime payload is successfully preserved.');
    } finally {
        // if (fs.existsSync(tempDir)) {
        //     fs.rmSync(tempDir, { recursive: true, force: true });
        // }
    }
}

try {
    runTest();
} catch (e) {
    console.error('[TEST FAILED]', e.message);
    process.exit(1);
}
