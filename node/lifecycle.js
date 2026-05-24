/**
 * Phase 8 Lifecycle — orchestrates the full startup / teardown sequence.
 *
 * READY vs RUNNING semantics:
 *   READY:   transport connected, handshake done, detection gated (startPaused:true)
 *   RUNNING: detection active (startPaused:false or after resume())
 *
 * Detection is controlled by sending configure messages to the supervisor.
 */

const { STATES } = require('./state_machine');
const { ProcessManager } = require('./process_manager');
const { Transport } = require('./transport');
const { ModelManager } = require('./model_manager');
const { RuntimeManager } = require('./runtime_manager');
const { BootstrapLock } = require('./bootstrap_lock');
const { CapabilityManager } = require('./capability_manager');
const { performHandshake } = require('./protocol/handshake');
const { createEnvelope } = require('./protocol/messages');
const { validateConfigMutation, RestartRequiredError } = require('./config_validator');
const logger = require('./utils/logger');
const { spawn } = require('child_process');
const path = require('path');
const crypto = require('crypto');
const { PathManager } = require('./path_manager');
const benchmark = require('./benchmark');

const DIAGNOSTICS_TIMEOUT_MS = 100;

class DiagnosticsUnavailableError extends Error {
    constructor(type) {
        super(`Diagnostics unavailable: ${type} (runtime not connected or timed out)`);
        this.name = 'DiagnosticsUnavailableError';
        this.code = 'DIAGNOSTICS_UNAVAILABLE';
        this.diagnosticType = type;
    }
}

class Lifecycle {
    constructor(stateMachine, eventEmitter) {
        this.fsm = stateMachine;
        this.events = eventEmitter;
        this.processManager = new ProcessManager();
        this.transport = null;
        this.modelManager = null; // Will be lazily initialized with opts
        this.runtimeManager = new RuntimeManager();
        this.bootstrapLock = new BootstrapLock(this.runtimeManager.get_bootstrap_lock_path());
        this.capabilityManager = null;
        this.profilePath = null;
        this._manifest = null;
    }

    /**
     * Start the runtime.
     * @param {string|null} profilePath  - path to profile JSON
     * @param {object} [opts]
     * @param {boolean} [opts.startPaused=false] - if true, enters READY but not RUNNING
     */
    async start(profilePath, opts = {}) {
        const mergedOpts = { ...this._opts, ...opts };
        const { startPaused = false, debug = false } = mergedOpts;
        
        if (!this.modelManager) {
            this.modelManager = new ModelManager(mergedOpts);
        }
        
        if (debug) {
            logger.level = 'debug';
        }
        
        this.profilePath = profilePath;
        this.fsm.transition(STATES.STARTING);
        benchmark.mark('bootstrap_start');

        try {
            // Diagnostic: starting bootstrap sequence
            logger.info('Lifecycle.start: entering start sequence', { state: this.fsm.get() });
            try {
                const bs = this.runtimeManager.load_bootstrap_state();
                logger.info('Lifecycle.start: bootstrap_state', bs || null);
            } catch (e) {
                logger.info('Lifecycle.start: bootstrap_state read error', e.message);
            }
            try {
                const rs = this.runtimeManager.load_runtime_state ? this.runtimeManager.load_runtime_state() : null;
                logger.info('Lifecycle.start: runtime_state', rs || null);
            } catch (e) {}

            // 1. runtime bootstrap: acquire lock, verify or install runtime
            let lockAcquired = false;
            try {
                this.bootstrapLock.acquire(30000);
                lockAcquired = true;

                const bsState = this.runtimeManager.load_bootstrap_state();
                if (!this.runtimeManager.can_resume_bootstrap(bsState)) {
                    this.runtimeManager.rollback_bootstrap_state(bsState);
                }

                // Diagnostic trace: check cached/runtime/venv/system python before installing
                logger.info('Runtime bootstrap: verifying cached runtime');
                benchmark.mark('runtime_verify_start');
                const tRuntimeVerifyStart = performance.now();
                let runtimeOk = this.runtimeManager.verify_runtime();
                const runtimeVerifyMs = performance.now() - tRuntimeVerifyStart;
                benchmark.mark('runtime_verify_end');
                benchmark.measure('runtime_verification_ms', 'runtime_verify_start', 'runtime_verify_end');

                if (runtimeOk) {
                    logger.info('Runtime bootstrap: cached runtime verified');
                } else {
                    logger.info('Runtime bootstrap: attempting install from configured sources');
                    benchmark.mark('runtime_install_start');
                    const installed = this.runtimeManager.install_runtime();
                    benchmark.mark('runtime_install_end');
                    benchmark.measure('runtime_install_ms', 'runtime_install_start', 'runtime_install_end');

                    if (installed && this.runtimeManager.verify_runtime()) {
                        logger.info('Runtime bootstrap: install and verification successful');
                        runtimeOk = true;
                    } else {
                        logger.warn('Runtime bootstrap: installation failed, falling back to existing python (venv/system)');
                        const candidate = this.runtimeManager.get_python_exec();
                        if (candidate) {
                            const ok = this.runtimeManager.verify_python_exec(candidate);
                            if (ok) {
                                logger.info(`Runtime bootstrap: using existing python at ${candidate}`);
                                runtimeOk = true;
                                this.runtimeManager.save_runtime_state({
                                    runtimeVersion: this.runtimeManager.getRuntimeVersion() || 'system',
                                    installedAt: new Date().toISOString(),
                                    health: 'external-python',
                                    pythonPath: candidate,
                                });
                            }
                        }
                    }
                }

                if (!runtimeOk) {
                    throw new Error('Runtime verification failed: no valid python environment found');
                }
            } finally {
                if (lockAcquired) this.bootstrapLock.release();
            }

            // 2. validate config (subprocess, no models)
            if (profilePath) await this.validateProfile(profilePath);

            // 3. verify/download models
            this.fsm.transition(STATES.INSTALLING);
            benchmark.mark('model_verify_start');
            const tModelVerifyStart = performance.now();
            await this.modelManager.validate_manifest_urls();
            await this.modelManager.verifyOrDownload();
            const modelVerifyMs = performance.now() - tModelVerifyStart;
            benchmark.mark('model_verify_end');
            benchmark.measure('model_verification_ms', 'model_verify_start', 'model_verify_end');

            try {
                const breakdownPath = path.join(PathManager.get_package_root(), 'benchmarks', 'startup_breakdown.json');
                let breakdown = {};
                if (fs.existsSync(breakdownPath)) {
                    breakdown = JSON.parse(fs.readFileSync(breakdownPath, 'utf8'));
                }
                breakdown.runtime_verify_ms = runtimeVerifyMs;
                breakdown.model_verify_ms = modelVerifyMs;
                fs.writeFileSync(breakdownPath, JSON.stringify(breakdown, null, 2));
            } catch (e) {
                logger.debug('Failed to write startup breakdown: ' + e.message);
            }

            // 3. spawn supervisor
            benchmark.mark('worker_spawn_start');
            const wsPort = await this.processManager.spawnSupervisor(profilePath, opts);
            benchmark.mark('worker_spawn_end');
            benchmark.measure('worker_spawn_ms', 'worker_spawn_start', 'worker_spawn_end');

            // 4. connect transport
            this.fsm.transition(STATES.CONNECTING);
            this.transport = new Transport('127.0.0.1', wsPort);

            // Wire transport lifecycle events
            this.transport.on('error', (err) => {
                logger.debug('Transport error:', err.message);
            });
            this.transport.on('message',     (msg) => {
                logger.debug('WS receive', msg);
                this._onTransportMessage(msg);
            });
            this.transport.on('recovering',  (info) => {
                logger.debug('reconnect attempts started', info);
                benchmark.mark('restart_start');
                // Record previous state before entering RECOVERING
                this.transport.setPreviousState(this.fsm.get());
                if (this.fsm.isActive() || this.fsm.get() === STATES.READY) {
                    this.fsm.transition(STATES.RECOVERING);
                }
                this.events.emit('recovering', info);
            });
            this.transport.on('reconnected', (info) => {
                benchmark.mark('restart_end');
                benchmark.measure('restart_recovery_ms', 'restart_start', 'restart_end');
                const prev = this.transport.getPreviousState();
                if (this.fsm.get() === STATES.RECOVERING) {
                    // Restore: back to READY first, then RUNNING if was running
                    this.fsm.transition(STATES.READY);
                    if (prev === STATES.RUNNING || prev === STATES.PAUSED) {
                        if (!startPaused && prev === STATES.RUNNING) {
                            this.fsm.transition(STATES.RUNNING);
                        }
                    }
                }
                this.events.emit('reconnected', info);
            });
            this.transport.on('failed', () => {
                this.fsm.transition(STATES.FAILED);
            });

            benchmark.mark('ws_connect_start');
            await this.transport.connect();
            benchmark.mark('ws_connect_end');
            benchmark.measure('ws_connection_ms', 'ws_connect_start', 'ws_connect_end');

            // 5. handshake (architecture-compliant)
            benchmark.mark('handshake_start');
            const manifestPayload = await performHandshake(this.transport);
            benchmark.mark('handshake_end');
            benchmark.measure('handshake_ms', 'handshake_start', 'handshake_end');

            // 6. initialize capability manager from handshake manifest
            this._manifest = manifestPayload.manifest || manifestPayload;
            this.capabilityManager = new CapabilityManager(
                (manifestPayload.capabilities) || (this._manifest && this._manifest.capabilities) || {}
            );

            // 7. Wait for worker to signal ready status
            benchmark.mark('worker_ready_start');
            await new Promise((resolve, reject) => {
                const timeout = setTimeout(() => {
                    this.transport.removeListener('message', onMsg);
                    reject(new Error('Timed out waiting for runtime ready status'));
                }, 15000); // give models time to load

                const onMsg = (msg) => {
                    if (msg.type === 'status' && msg.payload && msg.payload.status === 'ready') {
                        clearTimeout(timeout);
                        this.transport.removeListener('message', onMsg);
                        resolve();
                    }
                };
                this.transport.on('message', onMsg);
            });
            benchmark.mark('worker_ready_end');
            benchmark.measure('worker_ready_ms', 'worker_ready_start', 'worker_ready_end');

            // 8. State: always enter READY; only enter RUNNING if not startPaused
            this.fsm.transition(STATES.READY);
            if (!startPaused) {
                this._sendDetectionGate(false); // un-gate detection
                this.fsm.transition(STATES.RUNNING);
            } else {
                this._sendDetectionGate(true); // keep detection gated
            }

            benchmark.mark('bootstrap_end');
            benchmark.measure('startup_time_ms', 'bootstrap_start', 'bootstrap_end');

        } catch (e) {
            logger.error('Failed to start:', e.message);
            if (this.fsm.get() !== STATES.FAILED) {
                this.fsm.transition(STATES.FAILED);
            }
            throw e;
        }
    }

    _sendDetectionGate(paused) {
        if (this.transport && this.transport.isConnected) {
            this.transport.send(createEnvelope('configure', { detection_paused: paused }));
        }
    }

    async pause() {
        const s = this.fsm.get();
        if (s !== STATES.RUNNING) throw new Error(`pause() requires RUNNING state, currently ${s}`);
        this.fsm.transition(STATES.PAUSED);
        this._sendDetectionGate(true);
    }

    async resume() {
        const s = this.fsm.get();
        if (s === STATES.READY) {
            // Explicit first resume from READY → RUNNING
            this._sendDetectionGate(false);
            this.fsm.transition(STATES.RUNNING);
        } else if (s === STATES.PAUSED) {
            this._sendDetectionGate(false);
            this.fsm.transition(STATES.RUNNING);
        } else {
            throw new Error(`resume() requires READY or PAUSED state, currently ${s}`);
        }
    }

    async stop() {
        const s = this.fsm.get();
        if (s === STATES.STOPPED || s === STATES.DESTROYED) return;
        logger.info('Lifecycle.stop: initiating shutdown', { state: s });
        try {
            const bs = this.runtimeManager.load_bootstrap_state();
            logger.info('Lifecycle.stop: bootstrap_state before stop', bs || null);
        } catch (e) {}
        this.fsm.transition(STATES.STOPPING);
        if (this.transport) {
            if (this.transport.isConnected) {
                this.transport.send(createEnvelope('shutdown'));
            }
            this.transport.close();
            this.transport = null;
        }
        await this.processManager.stop();
        // Diagnostic: ensure child process cleared
        if (this.processManager.proc) {
            logger.warn('Lifecycle.stop: supervisor process still exists after stop', { pid: this.processManager.proc.pid });
        } else {
            logger.info('Lifecycle.stop: supervisor process cleared');
        }
        try {
            const lockExists = this.bootstrapLock.isLocked();
            logger.info('Lifecycle.stop: bootstrap lock exists after stop', lockExists);
        } catch (e) {}
        this.fsm.transition(STATES.STOPPED);
    }

    async restart() {
        const s = this.fsm.get();
        if (s === STATES.DESTROYED) throw new Error('Cannot restart DESTROYED instance');
        this.events.emit('restarting');
        await this.stop();
        await this.start(this.profilePath);
    }

    destroy() {
        this.stop().catch(() => {});
        this.fsm.transition(STATES.DESTROYED);
        this.events.removeAllListeners();
    }

    // ── Profile APIs ──────────────────────────────────────────────────────────

    loadProfile(profilePath) {
        this._requireActive();
        this.profilePath = profilePath;
        this.transport.send(createEnvelope('configure', { command: 'load_profile', path: profilePath }));
    }

    validateProfile(profilePath) {
        return new Promise((resolve, reject) => {
            if (this.transport && this.transport.isConnected) {
                // Runtime-connected path
                const correlationId = crypto.randomUUID();
                const timer = setTimeout(() => {
                    this.transport.removeListener('message', onResponse);
                    reject(new DiagnosticsUnavailableError('validate_profile'));
                }, 5000);

                const onResponse = (msg) => {
                    if (msg.type === 'validate_profile_response' && msg.payload && msg.payload.correlationId === correlationId) {
                        clearTimeout(timer);
                        this.transport.removeListener('message', onResponse);
                        const result = msg.payload.result;
                        this.events.emit('profile-validation-complete', { path: profilePath, result });
                        resolve(result);
                    }
                };
                this.transport.on('message', onResponse);
                this.transport.send(createEnvelope('validate_profile', { path: profilePath, correlationId }));
            } else {
                const candidate = this.runtimeManager.get_python_exec();
                const pythonExec = candidate ? candidate : (process.platform === 'win32' ? 'python' : 'python3');
                const proc = spawn(
                    pythonExec,
                    ['-m', 'runtime.config.profile_validator', profilePath],
                    { cwd: PathManager.get_package_root() }
                );

                let output = '';
                proc.stdout.on('data', d => { output += d; });
                proc.on('close', (code) => {
                    const valid = code === 0;
                    const result = { valid, errors: [], warnings: [] };
                    output.split('\n').forEach(line => {
                        if (line.startsWith('ERROR: ')) result.errors.push(line.replace('ERROR: ', '').trim());
                        if (line.startsWith('WARN: '))  result.warnings.push(line.replace('WARN: ', '').trim());
                    });
                    this.events.emit('profile-validation-complete', { path: profilePath, result });
                    resolve(result);
                });
                proc.on('error', reject);
            }
        });
    }

    // ── Config APIs ───────────────────────────────────────────────────────────

    updateConfig(patch) {
        validateConfigMutation(patch); // throws RestartRequiredError if needed
        this._requireActive();
        this.transport.send(createEnvelope('configure', { command: 'update_config', params: patch }));
    }

    getEffectiveConfig() {
        return this._diagnosticsRequest('effective_config');
    }

    getRuntimeParameters() {
        return this._diagnosticsRequest('effective_config');
    }

    updateRuntimeParameters(params) {
        this.updateConfig(params);
    }

    resetParameters() {
        this._requireActive();
        this.transport.send(createEnvelope('configure', { command: 'reset_parameters' }));
    }

    // ── Diagnostics APIs ──────────────────────────────────────────────────────

    getHealth() {
        return this._diagnosticsRequest('health');
    }

    getMetrics() {
        return this._diagnosticsRequest('metrics');
    }

    getDiagnostics() {
        return this._diagnosticsRequest('effective_config');
    }

    getManifest() {
        if (this._manifest) return Promise.resolve({ ...this._manifest });
        return this._diagnosticsRequest('manifest');
    }

    getPhrases() {
        return this._diagnosticsRequest('phrases');
    }

    /**
     * Internal helper: sends a diagnostics_request and waits up to 100ms for response.
     * Throws DiagnosticsUnavailableError on timeout.
     */
    _diagnosticsRequest(type) {
        if (!this.transport || !this.transport.isConnected) {
            return Promise.reject(new DiagnosticsUnavailableError(type));
        }

        return new Promise((resolve, reject) => {
            const correlationId = crypto.randomUUID();
            const timer = setTimeout(() => {
                this.transport.removeListener('message', onResp);
                reject(new DiagnosticsUnavailableError(type));
            }, DIAGNOSTICS_TIMEOUT_MS);

            const onResp = (msg) => {
                if (msg.type === 'diagnostics_response' &&
                    msg.payload &&
                    (msg.payload.correlationId === correlationId || msg.correlationId === correlationId)) {
                    clearTimeout(timer);
                    this.transport.removeListener('message', onResp);
                    resolve(msg.payload.result);
                }
            };
            this.transport.on('message', onResp);

            // Send with correlationId both at envelope level and in payload
            // Supervisor echoes the envelope-level correlationId back in payload.correlationId
            const envelope = createEnvelope('diagnostics_request', { type, correlationId });
            envelope.correlationId = correlationId;  // ensure envelope-level matches
            this.transport.send(envelope);
        });
    }

    // ── Phrase APIs ───────────────────────────────────────────────────────────

    addPhrase(phraseObj) {
        this._requireActive();
        this.transport.send(createEnvelope('configure', { command: 'add_phrase', ...phraseObj }));
    }

    removePhrase(phraseId) {
        this._requireActive();
        this.transport.send(createEnvelope('configure', { command: 'remove_phrase', phraseId }));
    }

    enablePhrase(phraseId) {
        this._requireActive();
        this.transport.send(createEnvelope('configure', { command: 'enable_phrase', phraseId }));
    }

    disablePhrase(phraseId) {
        this._requireActive();
        this.transport.send(createEnvelope('configure', { command: 'disable_phrase', phraseId }));
    }

    updateVariants(phraseId, variants) {
        this._requireActive();
        this.transport.send(createEnvelope('configure', { command: 'update_variants', phraseId, variants }));
    }

    // ── Internal ──────────────────────────────────────────────────────────────

    _requireActive() {
        if (!this.fsm.isActive()) {
            throw new Error(`Requires active state (READY/RUNNING/PAUSED), currently ${this.fsm.get()}`);
        }
    }

    _onTransportMessage(msg) {
        // Internal response types are handled by their promise listeners above
        const internalTypes = new Set([
            'handshake_ack', 'handshake_rejected',
            'diagnostics_response',
            'validate_profile_response',
        ]);
        if (!internalTypes.has(msg.type)) {
            this.events.emit(msg.type, msg.payload);
        }
    }
}

module.exports = { Lifecycle, DiagnosticsUnavailableError };
