/**
 * Phase 8 State Machine — strict READY vs RUNNING semantics.
 *
 * READY:   transport connected, models loaded, runtime initialized, detection GATED (paused)
 * RUNNING: active detection enabled
 *
 * Transition rules:
 *   UNINITIALIZED → STARTING
 *   STARTING      → INSTALLING | FAILED
 *   INSTALLING    → CONNECTING | FAILED
 *   CONNECTING    → READY | FAILED
 *   READY         → RUNNING | STOPPING | FAILED      (detection gated until resume())
 *   RUNNING       → PAUSED | RECOVERING | STOPPING | FAILED
 *   PAUSED        → RUNNING | STOPPING | FAILED
 *   RECOVERING    → READY | RUNNING | FAILED | STOPPING
 *   FAILED        → STARTING | STOPPING | DESTROYED
 *   STOPPING      → STOPPED
 *   STOPPED       → STARTING | DESTROYED
 *   DESTROYED     → (terminal — no exits)
 */

const EventEmitter = require('events');

const STATES = Object.freeze({
    UNINITIALIZED: 'UNINITIALIZED',
    INSTALLING:    'INSTALLING',
    STARTING:      'STARTING',
    CONNECTING:    'CONNECTING',
    READY:         'READY',
    RUNNING:       'RUNNING',
    PAUSED:        'PAUSED',
    RECOVERING:    'RECOVERING',
    FAILED:        'FAILED',
    STOPPING:      'STOPPING',
    STOPPED:       'STOPPED',
    DESTROYED:     'DESTROYED',
});

// Legal transition adjacency list
const TRANSITIONS = {
    [STATES.UNINITIALIZED]: [STATES.STARTING],
    [STATES.STARTING]:      [STATES.INSTALLING, STATES.FAILED],
    [STATES.INSTALLING]:    [STATES.CONNECTING, STATES.FAILED],
    [STATES.CONNECTING]:    [STATES.READY, STATES.FAILED],
    [STATES.READY]:         [STATES.RUNNING, STATES.RECOVERING, STATES.STOPPING, STATES.FAILED],
    [STATES.RUNNING]:       [STATES.PAUSED, STATES.RECOVERING, STATES.STOPPING, STATES.FAILED],
    [STATES.PAUSED]:        [STATES.RUNNING, STATES.RECOVERING, STATES.STOPPING, STATES.FAILED],
    [STATES.RECOVERING]:    [STATES.READY, STATES.RUNNING, STATES.PAUSED, STATES.FAILED, STATES.STOPPING],
    [STATES.FAILED]:        [STATES.STARTING, STATES.STOPPING, STATES.DESTROYED],
    [STATES.STOPPING]:      [STATES.STOPPED],
    [STATES.STOPPED]:       [STATES.STARTING, STATES.DESTROYED],
    [STATES.DESTROYED]:     [],  // terminal
};

class InvalidTransitionError extends Error {
    constructor(from, to) {
        super(`Invalid state transition: ${from} → ${to}`);
        this.name = 'InvalidTransitionError';
        this.code = 'INVALID_TRANSITION';
        this.from = from;
        this.to = to;
    }
}

class StateMachine extends EventEmitter {
    constructor() {
        super();
        this.state = STATES.UNINITIALIZED;
    }

    /**
     * Attempt a state transition.
     * Idempotent: transitioning to the current state is a no-op.
     * Throws InvalidTransitionError on illegal moves.
     */
    transition(newState) {
        if (!STATES[newState]) {
            throw new InvalidTransitionError(this.state, newState);
        }

        // Idempotent
        if (this.state === newState) return;

        const allowed = TRANSITIONS[this.state] || [];
        if (!allowed.includes(newState)) {
            throw new InvalidTransitionError(this.state, newState);
        }

        const oldState = this.state;
        this.state = newState;
        this.emit('transition', { from: oldState, to: newState });
        this.emit(newState.toLowerCase());
    }

    get() {
        return this.state;
    }

    /**
     * Returns true if the runtime is in an operational state where commands can be issued.
     */
    isActive() {
        return [STATES.READY, STATES.RUNNING, STATES.PAUSED].includes(this.state);
    }

    /**
     * Returns the full allowed transition list from the current state (useful for diagnostics).
     */
    allowedTransitions() {
        return [...(TRANSITIONS[this.state] || [])];
    }
}

module.exports = { StateMachine, STATES, TRANSITIONS, InvalidTransitionError };
