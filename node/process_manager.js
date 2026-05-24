const { spawn } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');
const logger = require('./utils/logger');

const { PathManager } = require('./path_manager');

class ProcessManager {
    constructor() {
        this.proc = null;
    }

    spawnSupervisor(profilePath, options = {}) {
        return new Promise((resolve, reject) => {
            if (this.proc) {
                return reject(new Error('Supervisor is already running.'));
            }

            const packageRoot = PathManager.get_package_root();
            const args = ['-m', 'runtime.main', '--ws-port', '0']; // 0 for random port
            if (profilePath) {
                args.push('--profile', profilePath);
            }
            if (options.debug) {
                args.push('--debug');
            }

            const { RuntimeManager } = require('./runtime_manager');
            const rm = new RuntimeManager();
            let pythonExec = rm.get_python_exec();

            if (!pythonExec) {
                // Absolute ultimate fallback (should not happen if verification passed)
                pythonExec = process.platform === 'win32'
                    ? path.join(PathManager.get_package_root(), '..', 'venv', 'Scripts', 'python.exe')
                    : 'python';
            }

            logger.info(`Spawning supervisor: ${pythonExec} ${args.join(' ')}`);
            
            const env = Object.assign({}, process.env);
            const { ModelManager } = require('./model_manager');
            const modelManager = new ModelManager(options);
            env.AVA_CACHE_DIR = modelManager.cacheRoot;

            this.proc = spawn(pythonExec, args, { cwd: packageRoot, env });

            let wsPort = null;
            let resolved = false;

            this.proc.stdout.on('data', (data) => {
                // Ignore stdout
            });

            this.proc.stderr.on('data', (data) => {
                const lines = data.toString().split('\n');
                for (const line of lines) {
                    if (line.includes('WebSocket Server listening on ws://')) {
                        const match = line.match(/ws:\/\/127\.0\.0\.1:(\d+)/);
                        if (match) {
                            wsPort = parseInt(match[1], 10);
                            if (!resolved) {
                                resolved = true;
                                resolve(wsPort);
                            }
                        }
                    }
                }
                process.stderr.write(data);
            });

            this.proc.on('close', (code) => {
                logger.warn(`Supervisor process exited with code ${code}`);
                this.proc = null;
                if (!resolved) reject(new Error('Supervisor exited before starting server.'));
            });
        });
    }

    async stop() {
        if (this.proc) {
            return new Promise(resolve => {
                const proc = this.proc;
                this.proc = null;
                
                const timer = setTimeout(() => {
                    try {
                        proc.kill('SIGTERM');
                    } catch (e) {}
                    resolve();
                }, 3000);

                proc.once('close', () => {
                    clearTimeout(timer);
                    resolve();
                });

                if (proc.stdin) {
                    proc.stdin.end();
                } else {
                    try {
                        proc.kill('SIGTERM');
                    } catch (e) {}
                }
            });
        }
    }
}

module.exports = { ProcessManager };
