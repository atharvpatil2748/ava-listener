const assert = require('assert');
const path = require('path');
const fs = require('fs');
const { spawnSync } = require('child_process');

function runTest() {
    const baseDir = path.join(__dirname, '..', '..', '..');
    const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
    
    // 1. Run npm pack
    const packRes = spawnSync(npmCmd, ['pack'], { cwd: baseDir, encoding: 'utf8', shell: true });
    if (packRes.status !== 0 || packRes.error) {
        throw new Error('npm pack failed: ' + (packRes.stderr || packRes.stdout || packRes.error));
    }
    
    const output = (packRes.stdout || '').trim().split('\n');
    const tarballName = output[output.length - 1].trim();
    const tarballPath = path.join(baseDir, tarballName);
    
    // 2. Install tarball into temp folder
    const tempDir = path.join(baseDir, 'temp', 'external_import_test_' + Date.now());
    fs.mkdirSync(tempDir, { recursive: true });
    
    try {
        spawnSync(npmCmd, ['init', '-y'], { cwd: tempDir, shell: true });
        const installRes = spawnSync(npmCmd, ['install', tarballPath], { cwd: tempDir, encoding: 'utf8', shell: true });
        
        if (installRes.status !== 0 || installRes.error) {
            throw new Error('npm install failed: ' + (installRes.stderr || installRes.stdout || installRes.error));
        }

        // 3. Require "ava-listener" inside the temp folder context
        // Since we are running in the current process, requiring a dynamic path directly is cleaner
        const packagePath = path.join(tempDir, 'node_modules', 'ava-listener');
        const { AVAListener } = require(packagePath);
        
        // 4. Assert constructor exists
        assert.ok(AVAListener, 'AVAListener should be exported');
        assert.strictEqual(typeof AVAListener, 'function', 'AVAListener should be a constructor function');
        
        const listener = new AVAListener({ profileName: 'test_profile', suppressInit: true });
        assert.ok(listener, 'Should be able to instantiate AVAListener');

        console.log('external_import_test passed');
    } finally {
        // Cleanup
        if (fs.existsSync(tarballPath)) {
            fs.unlinkSync(tarballPath);
        }
        if (fs.existsSync(tempDir)) {
            try {
                fs.rmSync(tempDir, { recursive: true, force: true });
            } catch (e) {
                console.warn('Failed to cleanup temp dir:', e.message);
            }
        }
    }
}

runTest();
