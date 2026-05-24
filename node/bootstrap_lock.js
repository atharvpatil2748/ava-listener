const fs = require('fs');
const path = require('path');

class BootstrapLock {
    constructor(lockPath) {
        this.lockPath = lockPath;
        this.acquired = false;
    }

    acquire(timeoutMs = 30000, retryIntervalMs = 200) {
        const start = Date.now();
        while (true) {
            try {
                const lockDir = path.dirname(this.lockPath);
                if (!fs.existsSync(lockDir)) {
                    fs.mkdirSync(lockDir, { recursive: true });
                }
                const content = JSON.stringify({ pid: process.pid, timestamp: new Date().toISOString() });
                fs.writeFileSync(this.lockPath, content, { flag: 'wx' });
                this.acquired = true;
                return;
            } catch (err) {
                if (err.code !== 'EEXIST') {
                    throw err;
                }
                if (Date.now() - start >= timeoutMs) {
                    throw new Error(`Could not acquire bootstrap lock after ${timeoutMs}ms`);
                }
                const stat = fs.statSync(this.lockPath);
                const ageMs = Date.now() - stat.mtimeMs;
                if (ageMs > 10 * 60 * 1000) {
                    // stale lock; remove it and retry once
                    try {
                        fs.unlinkSync(this.lockPath);
                    } catch (_) {}
                    continue;
                }
                Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, retryIntervalMs);
            }
        }
    }

    release() {
        if (!this.acquired) return;
        try {
            if (fs.existsSync(this.lockPath)) {
                fs.unlinkSync(this.lockPath);
            }
        } catch (err) {
            // swallow failure to release lock in cleanup
        } finally {
            this.acquired = false;
        }
    }

    isLocked() {
        return fs.existsSync(this.lockPath);
    }
}

module.exports = { BootstrapLock };