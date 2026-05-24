const os = require('os');
const path = require('path');
const fs = require('fs');
const { spawnSync } = require('child_process');

const { PathManager } = require('./path_manager');
const RUNTIME_SOURCES_FILE = path.join(PathManager.get_package_root(), 'node', 'runtime_sources.json');
const MINIMUM_PYTHON_VERSION = [3, 10];

class UnsupportedPlatformError extends Error {
    constructor(platform, arch) {
        super(`Unsupported platform or architecture: ${platform}-${arch}`);
        this.name = 'UnsupportedPlatformError';
        this.platform = platform;
        this.arch = arch;
    }
}

class RuntimeManager {
    constructor(config = {}) {
        this.config = config;
        this.cacheRoot = this.get_cache_dir();
        this.runtimeRoot = path.join(this.cacheRoot, 'runtime');
        this.metadataRoot = path.join(this.cacheRoot, 'metadata');
        this.baseDir = config.baseDir || PathManager.get_package_root();
    }

    get_cache_dir() {
        const platform = os.platform();
        if (platform === 'win32') {
            return path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local'), 'AVAListener');
        }

        if (platform === 'darwin') {
            return path.join(os.homedir(), 'Library', 'Application Support', 'AVAListener');
        }

        return path.join(os.homedir(), '.local', 'share', 'avalistener');
    }

    get_runtime_path() {
        return this.runtimeRoot;
    }

    ensure_cache_structure() {
        for (const segment of ['runtime', 'models', 'manifests', 'logs', 'temp', 'metadata']) {
            const dir = path.join(this.cacheRoot, segment);
            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
            }
        }
    }

    verify_runtime() {
        this.ensure_cache_structure();
        const pythonExec = this.get_cached_python();
        if (!pythonExec) {
            return false;
        }
        const valid = this.verify_python_exec(pythonExec);
        if (!valid) {
            return false;
        }
        this.save_runtime_state({
            runtimeVersion: this.getRuntimeVersion() || 'unknown',
            minimumSDKVersion: this.config.minimumSDKVersion || '0.1.0',
            maximumSDKVersion: this.config.maximumSDKVersion || '0.1.999',
            installedAt: new Date().toISOString(),
            health: 'ready',
        });
        return true;
    }

    install_runtime(sourceConfig = {}) {
        this.ensure_cache_structure();
        const sources = this.loadRuntimeSources(sourceConfig);
        const candidates = ['github', 'mirror', 'local'];
        for (const sourceName of candidates) {
            const sourceUrl = sources[sourceName];
            if (!sourceUrl) continue;
            try {
                if (this.install_from_source(sourceUrl)) {
                    this.save_runtime_state({
                        runtimeVersion: this.getRuntimeVersion() || '1.0.0',
                        minimumSDKVersion: this.config.minimumSDKVersion || '0.1.0',
                        maximumSDKVersion: this.config.maximumSDKVersion || '0.1.999',
                        installedAt: new Date().toISOString(),
                        health: 'ready',
                    });
                    return true;
                }
            } catch (err) {
                continue;
            }
        }
        return false;
    }

    repair_runtime() {
        try {
            if (fs.existsSync(this.runtimeRoot)) {
                fs.rmSync(this.runtimeRoot, { recursive: true, force: true });
            }
            if (fs.existsSync(this.get_runtime_state_path())) {
                fs.unlinkSync(this.get_runtime_state_path());
            }
            return true;
        } catch (err) {
            return false;
        }
    }

    get_python_exec() {
        this.ensure_cache_structure();
        const cached = this.get_cached_python();
        if (cached && this.verify_python_exec(cached)) {
            return cached;
        }

        const venv = this.get_venv_python();
        if (venv && this.verify_python_exec(venv)) {
            return venv;
        }

        const system = this.get_system_python();
        if (system && this.verify_python_exec(system)) {
            return system;
        }

        return null;
    }

    get_bootstrap_lock_path() {
        return path.join(this.cacheRoot, 'bootstrap.lock');
    }

    get_bootstrap_state_path() {
        return path.join(this.metadataRoot, 'bootstrap_state.json');
    }

    get_runtime_state_path() {
        return path.join(this.metadataRoot, 'runtime_state.json');
    }

    load_bootstrap_state() {
        const statePath = this.get_bootstrap_state_path();
        if (!fs.existsSync(statePath)) {
            return null;
        }
        return JSON.parse(fs.readFileSync(statePath, 'utf8'));
    }

    save_bootstrap_state(state) {
        fs.writeFileSync(this.get_bootstrap_state_path(), JSON.stringify(state, null, 2), 'utf8');
    }

    save_runtime_state(state) {
        fs.writeFileSync(this.get_runtime_state_path(), JSON.stringify(state, null, 2), 'utf8');
    }

    can_resume_bootstrap(state) {
        if (!state || state.status !== 'failed') return true;
        const safeSteps = ['acquire_lock', 'read_bootstrap_state', 'verify_runtime'];
        return safeSteps.includes(state.lastCompletedStep);
    }

    rollback_bootstrap_state(state) {
        this.repair_runtime();
        this.save_bootstrap_state({
            phase: 'rollback',
            status: 'completed',
            lastCompletedStep: 'rollback',
            timestamp: new Date().toISOString(),
        });
    }

    loadRuntimeSources(sourceConfig) {
        const configPath = sourceConfig.sourcesFile || RUNTIME_SOURCES_FILE;
        if (!fs.existsSync(configPath)) {
            return {};
        }
        const content = fs.readFileSync(configPath, 'utf8');
        const parsed = JSON.parse(content);
        
        let platformKey = os.platform();
        if (platformKey === 'win32') platformKey = 'windows';
        else if (platformKey === 'darwin') platformKey = 'macos';
        
        const arch = os.arch();
        this.verify_platform_support(platformKey, arch);
        this.verify_architecture(platformKey, arch);
        
        const fullKey = `${platformKey}-${arch}`;
        
        if (parsed.runtime && parsed.runtime[fullKey]) {
            return parsed.runtime[fullKey];
        }
        return parsed.runtime || {};
    }

    install_from_source(sourceUrl) {
        let sourcePath = this.resolve_source_path(sourceUrl);
        let isTemp = false;

        if (!sourcePath && (sourceUrl.startsWith('http://') || sourceUrl.startsWith('https://'))) {
            // Download to temp file
            const { execSync } = require('child_process');
            this.ensure_cache_structure();
            sourcePath = path.join(this.cacheRoot, 'temp', 'runtime_download.zip');
            try {
                if (os.platform() === 'win32') {
                    execSync(`powershell -NoProfile -Command "Invoke-WebRequest -Uri '${sourceUrl}' -OutFile '${sourcePath}'"`, { stdio: 'inherit' });
                } else {
                    execSync(`curl -L -o "${sourcePath}" "${sourceUrl}"`, { stdio: 'inherit' });
                }
                isTemp = true;
            } catch (err) {
                return false;
            }
        }

        if (!sourcePath) {
            throw new Error(`Unsupported runtime source: ${sourceUrl}`);
        }

        try {
            if (fs.existsSync(sourcePath) && fs.lstatSync(sourcePath).isDirectory()) {
                fs.cpSync(sourcePath, this.runtimeRoot, { recursive: true });
                return true;
            }
            if (fs.existsSync(sourcePath) && fs.lstatSync(sourcePath).isFile()) {
                const ext = path.extname(sourcePath).toLowerCase();
                const { spawnSync } = require('child_process');
                
                if (ext === '.zip') {
                    if (os.platform() === 'win32') {
                        const res = spawnSync('powershell', ['-NoProfile', '-Command', `Expand-Archive -Path "${sourcePath}" -DestinationPath "${this.runtimeRoot}" -Force`], { stdio: 'inherit' });
                        if (res.error || res.status !== 0) throw new Error('Failed to extract zip on Windows');
                    } else {
                        const res = spawnSync('unzip', ['-o', sourcePath, '-d', this.runtimeRoot], { stdio: 'inherit' });
                        if (res.error || res.status !== 0) throw new Error('Failed to extract zip');
                    }
                    return true;
                }
                if (ext === '.tar' || ext === '.gz' || ext === '.bz2') {
                    const res = spawnSync('tar', ['-xf', sourcePath, '-C', this.runtimeRoot], { stdio: 'inherit' });
                    if (res.error || res.status !== 0) throw new Error('Failed to extract archive');
                    return true;
                }
            }
            return false;
        } finally {
            if (isTemp && fs.existsSync(sourcePath)) {
                fs.unlinkSync(sourcePath);
            }
        }
    }

    resolve_source_path(sourceUrl) {
        if (sourceUrl.startsWith('file://')) {
            return sourceUrl.replace('file://', '');
        }
        if (sourceUrl.startsWith('./') || sourceUrl.startsWith('../')) {
            return path.resolve(this.baseDir, sourceUrl);
        }
        if (fs.existsSync(sourceUrl)) {
            return path.resolve(sourceUrl);
        }
        return null;
    }

    get_cached_python() {
        const platform = os.platform();
        const candidates = [];
        candidates.push(path.join(this.runtimeRoot, 'python.exe'));
        candidates.push(path.join(this.runtimeRoot, 'Scripts', 'python.exe')); // Windows venv
        candidates.push(path.join(this.runtimeRoot, 'bin', 'python'));
        candidates.push(path.join(this.runtimeRoot, 'python', 'bin', 'python'));
        for (const cand of candidates) {
            if (fs.existsSync(cand)) {
                return cand;
            }
        }
        return null;
    }

    get_venv_python() {
        const platform = os.platform();
        if (platform === 'win32') {
            const candidate = path.join(this.baseDir, 'venv', 'Scripts', 'python.exe');
            return fs.existsSync(candidate) ? candidate : null;
        }
        const candidate = path.join(this.baseDir, 'venv', 'bin', 'python');
        return fs.existsSync(candidate) ? candidate : null;
    }

    get_system_python() {
        if (os.platform() === 'win32') {
            return 'python';
        }
        return 'python3';
    }

    verify_python_exec(pythonExec) {
        try {
            const result = spawnSync(pythonExec, ['--version'], { encoding: 'utf8' });
            if (result.error || result.status !== 0) {
                return false;
            }
            const output = (result.stdout || result.stderr).trim();
            const match = output.match(/Python (\d+)\.(\d+)\.(\d+)/);
            if (!match) {
                return false;
            }
            const major = Number(match[1]);
            const minor = Number(match[2]);
            if (major < MINIMUM_PYTHON_VERSION[0]) return false;
            if (major === MINIMUM_PYTHON_VERSION[0] && minor < MINIMUM_PYTHON_VERSION[1]) return false;
            
            // Dependency check
            const depCheck = spawnSync(pythonExec, ['-c', 'import websockets; import onnxruntime'], { encoding: 'utf8' });
            if (depCheck.error || depCheck.status !== 0) {
                return false;
            }
            
            return true;
        } catch (err) {
            return false;
        }
    }

    getRuntimeVersion() {
        return this.config.runtimeVersion || '1.0.0';
    }

    verify_platform_support(platform, arch) {
        const supported = ['windows', 'linux', 'macos'];
        if (!supported.includes(platform)) {
            throw new UnsupportedPlatformError(platform, arch);
        }
    }

    verify_architecture(platform, arch) {
        if (platform === 'windows' && arch !== 'x64') {
            throw new UnsupportedPlatformError(platform, arch);
        }
        if (platform === 'linux' && !['x64', 'arm64'].includes(arch)) {
            throw new UnsupportedPlatformError(platform, arch);
        }
        if (platform === 'macos' && !['x64', 'arm64'].includes(arch)) {
            throw new UnsupportedPlatformError(platform, arch);
        }
    }

    get_runtime_artifact() {
        let platformKey = os.platform();
        if (platformKey === 'win32') platformKey = 'windows';
        else if (platformKey === 'darwin') platformKey = 'macos';
        
        const arch = os.arch();
        this.verify_platform_support(platformKey, arch);
        this.verify_architecture(platformKey, arch);
        
        const manifestPath = path.join(this.baseDir, 'runtime', 'manifests', 'platform_manifest.json');
        if (!fs.existsSync(manifestPath)) {
            return null;
        }
        
        const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
        const artifact = manifest.artifacts.find(a => a.platform === platformKey && a.arch === arch);
        if (!artifact) {
            throw new UnsupportedPlatformError(platformKey, arch);
        }
        return artifact;
    }
}

module.exports = { RuntimeManager, UnsupportedPlatformError };
