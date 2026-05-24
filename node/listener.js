/**
 * Phase 8 AVAListener — public API facade.
 *
 * All capability-gated methods call capabilityManager.require() before execution.
 * All diagnostics methods delegate to lifecycle._diagnosticsRequest() with 100ms timeout.
 * All phrase methods route through the registry only (no hardcoded assistant names).
 */

const EventEmitter = require('events');
const { StateMachine } = require('./state_machine');
const { Lifecycle, DiagnosticsUnavailableError } = require('./lifecycle');
const logger = require('./utils/logger');

class AVAListener extends EventEmitter {
    constructor(opts = {}) {
        super();
        this._opts = opts;
        this.fsm = new StateMachine();
        this.lifecycle = new Lifecycle(this.fsm, this);

        // Forward state transitions to public event emitter
        this.fsm.on('transition', ({ from, to }) => {
            logger.debug('state transitions', from, '→', to);
            this.emit('statechange', { from, to });
            this.emit(to.toLowerCase());
        });
    }

    // ── Lifecycle API ─────────────────────────────────────────────────────────

    /**
     * Start the runtime.
     * @param {string|null} [profilePath]
     * @param {object}      [opts]
     * @param {boolean}     [opts.startPaused=false]
     *   If true the runtime enters READY but detection remains gated.
     *   Call resume() to transition to RUNNING.
     */
    start(profilePath, opts = {}) {
        if (typeof profilePath === 'object' && profilePath !== null && !opts.startPaused) {
            // Allow start(opts) shorthand
            opts = profilePath;
            profilePath = opts.profile || null;
        } else if (!profilePath && this._opts.profile) {
            profilePath = this._opts.profile;
        }
        const mergedOpts = { ...this._opts, ...opts };
        return this.lifecycle.start(profilePath, mergedOpts);
    }

    pause()   { return this.lifecycle.pause(); }
    resume()  { return this.lifecycle.resume(); }
    stop()    { return this.lifecycle.stop(); }
    restart() { return this.lifecycle.restart(); }
    destroy() { return this.lifecycle.destroy(); }

    // ── Profile & Config API ─────────────────────────────────────────────────

    loadProfile(profilePath) {
        this.lifecycle.loadProfile(profilePath);
    }

    validateProfile(profilePath) {
        return this.lifecycle.validateProfile(profilePath);
    }

    updateConfig(patch) {
        this.lifecycle.updateConfig(patch);
    }

    getEffectiveConfig() {
        return this.lifecycle.getEffectiveConfig();
    }

    getRuntimeParameters() {
        return this.lifecycle.getRuntimeParameters();
    }

    updateRuntimeParameters(params) {
        this.lifecycle.updateRuntimeParameters(params);
    }

    resetParameters() {
        this.lifecycle.resetParameters();
    }

    // ── Diagnostics API ───────────────────────────────────────────────────────

    /**
     * Returns the current FSM state string.
     */
    getState() {
        return this.fsm.get();
    }

    /**
     * @returns {Promise<{score:number, status:string}>}
     * @throws DiagnosticsUnavailableError if runtime is disconnected or times out
     */
    getHealth() {
        return this.lifecycle.getHealth();
    }

    /**
     * @returns {Promise<object>}
     * @throws DiagnosticsUnavailableError
     */
    getMetrics() {
        return this.lifecycle.getMetrics();
    }

    /**
     * @returns {Promise<object>}
     * @throws DiagnosticsUnavailableError
     */
    getDiagnostics() {
        return this.lifecycle.getDiagnostics();
    }

    /**
     * @returns {Promise<object>} Full runtime manifest
     * @throws DiagnosticsUnavailableError
     */
    getManifest() {
        return this.lifecycle.getManifest();
    }

    // ── Capability API ────────────────────────────────────────────────────────

    /**
     * Enable experiment mode — gated by 'experimentMode' capability.
     * Throws CapabilityUnavailableError if runtime does not advertise the capability.
     */
    enableExperimentMode() {
        if (!this.lifecycle.capabilityManager) {
            throw new Error('Runtime not initialized — call start() first');
        }
        this.lifecycle.capabilityManager.require('experimentMode');
        this.lifecycle.transport.send(
            require('./protocol/messages').createEnvelope('configure', { experiment_mode: true })
        );
    }

    /**
     * Returns a snapshot of runtime capabilities (from handshake manifest).
     */
    getCapabilities() {
        if (!this.lifecycle.capabilityManager) return {};
        return this.lifecycle.capabilityManager.getCapabilities();
    }

    // ── Phrase Management API ─────────────────────────────────────────────────
    // All operations route through the phrase registry only — no hardcoded names.

    /**
     * @param {{ phraseId:string, text:string, variants:string[], threshold:number, weight:number }} phraseObj
     */
    addPhrase(phraseObj) {
        this.lifecycle.addPhrase(phraseObj);
    }

    removePhrase(phraseId) {
        this.lifecycle.removePhrase(phraseId);
    }

    enablePhrase(phraseId) {
        this.lifecycle.enablePhrase(phraseId);
    }

    disablePhrase(phraseId) {
        this.lifecycle.disablePhrase(phraseId);
    }

    /**
     * @param {string}   phraseId
     * @param {string[]} variants
     */
    updateVariants(phraseId, variants) {
        this.lifecycle.updateVariants(phraseId, variants);
    }

    /**
     * @returns {Promise<Array>} list of active phrase objects
     * @throws DiagnosticsUnavailableError
     */
    getPhrases() {
        return this.lifecycle.getPhrases();
    }
}

module.exports = { AVAListener };
