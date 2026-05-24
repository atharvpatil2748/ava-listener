const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

class PackageValidator {
    constructor(baseDir = path.join(__dirname, '..')) {
        this.baseDir = baseDir;
        this.constraintsPath = path.join(this.baseDir, 'runtime', 'manifests', 'package_constraints.json');
        this.requiredTargets = [
            'node/',
            'runtime/',
            'profiles/',
            'models/manifests/',
            'package.json',
            'README.md'
        ];
    }

    validate_required_files() {
        const missing = [];
        for (const target of this.requiredTargets) {
            const isDir = target.endsWith('/');
            const targetPath = path.join(this.baseDir, target.replace(/\/$/, ''));
            if (!fs.existsSync(targetPath)) {
                missing.push(target);
                continue;
            }
            const stat = fs.statSync(targetPath);
            if (isDir && !stat.isDirectory()) {
                missing.push(target + ' (expected directory)');
            }
            if (!isDir && !stat.isFile()) {
                missing.push(target + ' (expected file)');
            }
        }
        if (missing.length > 0) {
            throw new Error(`Missing required package files/directories: ${missing.join(', ')}`);
        }
        return true;
    }

    validate_package_layout() {
        // More comprehensive validation could be added here
        return this.validate_required_files();
    }

    run_npm_pack() {
        const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
        const result = spawnSync(npmCmd, ['pack'], { cwd: this.baseDir, encoding: 'utf8', shell: true });
        if (result.error || result.status !== 0) {
            throw new Error(`npm pack failed: ${result.stderr || result.stdout || result.error}`);
        }
        
        // npm pack outputs the tarball name on the last line
        const output = (result.stdout || '').trim().split('\n');
        const tarballName = output[output.length - 1].trim();
        const tarballPath = path.join(this.baseDir, tarballName);
        
        if (!fs.existsSync(tarballPath)) {
            throw new Error(`npm pack tarball not found at ${tarballPath}`);
        }
        
        return tarballPath;
    }

    validate_package_size(tarballPath) {
        if (!fs.existsSync(this.constraintsPath)) {
            throw new Error(`Constraints manifest not found at ${this.constraintsPath}`);
        }
        const constraints = JSON.parse(fs.readFileSync(this.constraintsPath, 'utf8'));
        const stat = fs.statSync(tarballPath);
        const sizeMB = stat.size / (1024 * 1024);
        
        if (sizeMB > constraints.hardLimitMB) {
            throw new Error(`Package size ${sizeMB.toFixed(2)} MB exceeds hard limit of ${constraints.hardLimitMB} MB`);
        }
        if (sizeMB > constraints.softLimitMB) {
            console.warn(`WARNING: Package size ${sizeMB.toFixed(2)} MB exceeds soft limit of ${constraints.softLimitMB} MB`);
        }
        return sizeMB;
    }

    validate_fresh_install(tarballPath) {
        // Create temp dir, simulate fresh install
        const tempDir = path.join(this.baseDir, 'temp', 'fresh_install_test_' + Date.now());
        fs.mkdirSync(tempDir, { recursive: true });
        const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
        try {
            // we initialize a dummy package
            spawnSync(npmCmd, ['init', '-y'], { cwd: tempDir, shell: true });
            // we npm install the tarball
            const res = spawnSync(npmCmd, ['install', tarballPath], { cwd: tempDir, encoding: 'utf8', shell: true });
            if (res.error || res.status !== 0) {
                throw new Error('Fresh install failed: ' + (res.stderr || res.stdout));
            }
            
            // Run startup path with empty cache
            const cacheDir = path.join(tempDir, 'empty_cache');
            fs.mkdirSync(cacheDir, { recursive: true });
            
            const env = Object.assign({}, process.env, {
                LOCALAPPDATA: cacheDir // Simulate empty cache on Windows
            });
            
            // We use the package's bootstrap script to verify layout/startup
            const startupRes = spawnSync('node', ['node_modules/ava-listener/node/bootstrap.js', '--validate-layout'], { 
                cwd: tempDir, 
                encoding: 'utf8',
                env: env 
            });
            
            if (startupRes.error || startupRes.status !== 0) {
                throw new Error('Startup path failed: ' + (startupRes.stderr || startupRes.stdout));
            }
            
            return true;
        } finally {
            if (fs.existsSync(tempDir)) {
                fs.rmSync(tempDir, { recursive: true, force: true });
            }
        }
    }

    validate_local_install(tarballPath) {
        // Validate it can be installed locally, essentially overlaps with fresh install conceptually,
        // but could test link or exact layout behavior.
        const tempDir = path.join(this.baseDir, 'temp', 'local_install_test_' + Date.now());
        fs.mkdirSync(tempDir, { recursive: true });
        const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
        try {
            spawnSync(npmCmd, ['init', '-y'], { cwd: tempDir, shell: true });
            const res = spawnSync(npmCmd, ['install', tarballPath], { cwd: tempDir, encoding: 'utf8', shell: true });
            if (res.error || res.status !== 0) {
                throw new Error('Local install failed: ' + (res.stderr || res.stdout || res.error));
            }
            
            // Verify node_modules contains the package
            const pkgNameMatch = tarballPath.match(/(.*?)-\d+\.\d+\.\d+.*\.tgz/);
            // Just assume it created a node_modules dir
            if (!fs.existsSync(path.join(tempDir, 'node_modules'))) {
                throw new Error('node_modules not created during local install');
            }
            return true;
        } finally {
            if (fs.existsSync(tempDir)) {
                fs.rmSync(tempDir, { recursive: true, force: true });
            }
        }
    }
}

module.exports = { PackageValidator };
