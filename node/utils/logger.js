class Logger {
    constructor() {
        this.level = 'info';
    }
    
    debug(...args) { if (this.level === 'debug') console.debug('[NodeSDK][DEBUG]', ...args); }
    info(...args) { console.info('[NodeSDK][INFO]', ...args); }
    warn(...args) { console.warn('[NodeSDK][WARN]', ...args); }
    error(...args) { console.error('[NodeSDK][ERROR]', ...args); }
}

module.exports = new Logger();
