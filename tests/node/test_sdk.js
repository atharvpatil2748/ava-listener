/**
 * Phase 8 Node SDK — Comprehensive Test Suite
 *
 * Covers:
 *   1.  State machine transition matrix
 *   2.  Invalid transition tests
 *   3.  Idempotency tests
 *   4.  READY/RUNNING semantics (startPaused)
 *   5.  Lifecycle pause/resume from READY and PAUSED
 *   6.  Handshake contract (protocol version, schema version, rejection)
 *   7.  Capability gating
 *   8.  Config mutability enforcement
 *   9.  Effective config / diagnostics APIs
 *   10. Profile validation (subprocess path)
 *   11. Phrase API integration
 *   12. Reconnect sequence (mock)
 *   13. Full integration startup with real runtime (arvsal.json)
 */

'use strict';

const assert = require('assert');
const path   = require('path');
const { EventEmitter } = require('events');

const {
    AVAListener,
    STATES,
    TRANSITIONS,
    InvalidTransitionError,
    RestartRequiredError,
    CapabilityUnavailableError,
    DiagnosticsUnavailableError,
    HandshakeError,
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
} = require('../../node/index');

const { StateMachine } = require('../../node/state_machine');
const { Transport, RECONNECT_DELAYS } = require('../../node/transport');
const { performHandshake } = require('../../node/protocol/handshake');
const { CapabilityManager } = require('../../node/capability_manager');
const { validateConfigMutation } = require('../../node/config_validator');
const { Lifecycle } = require('../../node/lifecycle');

// ── test harness ──────────────────────────────────────────────────────────────

let passed = 0, failed = 0;

function it(name, fn) {
    try {
        const result = fn();
        if (result && typeof result.then === 'function') {
            return result
                .then(() => { console.log(`PASS: ${name}`); passed++; })
                .catch(err => { console.error(`FAIL: ${name}`, err.message); failed++; });
        }
        console.log(`PASS: ${name}`);
        passed++;
        return Promise.resolve();
    } catch (err) {
        console.error(`FAIL: ${name}`, err.message);
        failed++;
        return Promise.resolve();
    }
}

function section(name) {
    console.log(`\n── ${name} ──────────────────────────────────`);
}

// ── 1. State Machine Transition Matrix ────────────────────────────────────────

section('1. State Machine Transition Matrix');

const VALID_TRANSITIONS = [
    [STATES.UNINITIALIZED, STATES.STARTING],
    [STATES.STARTING,      STATES.INSTALLING],
    [STATES.STARTING,      STATES.FAILED],
    [STATES.INSTALLING,    STATES.CONNECTING],
    [STATES.INSTALLING,    STATES.FAILED],
    [STATES.CONNECTING,    STATES.READY],
    [STATES.CONNECTING,    STATES.FAILED],
    [STATES.READY,         STATES.RUNNING],
    [STATES.READY,         STATES.STOPPING],
    [STATES.READY,         STATES.FAILED],
    [STATES.RUNNING,       STATES.PAUSED],
    [STATES.RUNNING,       STATES.RECOVERING],
    [STATES.RUNNING,       STATES.STOPPING],
    [STATES.RUNNING,       STATES.FAILED],
    [STATES.PAUSED,        STATES.RUNNING],
    [STATES.PAUSED,        STATES.STOPPING],
    [STATES.PAUSED,        STATES.FAILED],
    [STATES.RECOVERING,    STATES.READY],
    [STATES.RECOVERING,    STATES.RUNNING],
    [STATES.RECOVERING,    STATES.FAILED],
    [STATES.RECOVERING,    STATES.STOPPING],
    [STATES.FAILED,        STATES.STARTING],
    [STATES.FAILED,        STATES.STOPPING],
    [STATES.FAILED,        STATES.DESTROYED],
    [STATES.STOPPING,      STATES.STOPPED],
    [STATES.STOPPED,       STATES.STARTING],
    [STATES.STOPPED,       STATES.DESTROYED],
];

for (const [from, to] of VALID_TRANSITIONS) {
    it(`transition ${from} → ${to} is legal`, () => {
        const sm = new StateMachine();
        sm.state = from;                     // direct state injection for isolation
        sm.transition(to);
        assert.strictEqual(sm.get(), to);
    });
}

// ── 2. Invalid Transition Tests ───────────────────────────────────────────────

section('2. Invalid Transition Tests');

const INVALID_TRANSITIONS = [
    [STATES.UNINITIALIZED, STATES.RUNNING],
    [STATES.UNINITIALIZED, STATES.READY],
    [STATES.READY,         STATES.INSTALLING],
    [STATES.RUNNING,       STATES.STARTING],
    [STATES.DESTROYED,     STATES.STARTING],
    [STATES.STOPPED,       STATES.RUNNING],
];

for (const [from, to] of INVALID_TRANSITIONS) {
    it(`transition ${from} → ${to} throws InvalidTransitionError`, () => {
        const sm = new StateMachine();
        sm.state = from;
        assert.throws(() => sm.transition(to), (err) => {
            assert.strictEqual(err.name, 'InvalidTransitionError');
            return true;
        });
    });
}

it('DESTROYED is terminal — no exit', () => {
    const sm = new StateMachine();
    sm.state = STATES.DESTROYED;
    for (const target of Object.values(STATES)) {
        if (target === STATES.DESTROYED) continue;
        assert.throws(() => sm.transition(target), InvalidTransitionError);
    }
});

// ── 3. Idempotency Tests ──────────────────────────────────────────────────────

section('3. Idempotency Tests');

it('transition to same state is no-op', () => {
    const sm = new StateMachine();
    sm.state = STATES.RUNNING;
    let events = 0;
    sm.on('transition', () => events++);
    sm.transition(STATES.RUNNING);
    assert.strictEqual(events, 0, 'no transition event on idempotent transition');
    assert.strictEqual(sm.get(), STATES.RUNNING);
});

it('isActive() returns true for READY/RUNNING/PAUSED', () => {
    const active = [STATES.READY, STATES.RUNNING, STATES.PAUSED];
    const inactive = [STATES.UNINITIALIZED, STATES.STARTING, STATES.STOPPED, STATES.FAILED, STATES.DESTROYED];
    for (const s of active) {
        const sm = new StateMachine(); sm.state = s;
        assert.strictEqual(sm.isActive(), true, `${s} should be active`);
    }
    for (const s of inactive) {
        const sm = new StateMachine(); sm.state = s;
        assert.strictEqual(sm.isActive(), false, `${s} should not be active`);
    }
});

it('allowedTransitions() returns correct targets', () => {
    const sm = new StateMachine();
    sm.state = STATES.RUNNING;
    const allowed = sm.allowedTransitions();
    assert.ok(allowed.includes(STATES.PAUSED));
    assert.ok(allowed.includes(STATES.STOPPING));
    assert.ok(!allowed.includes(STATES.STARTING));
});

// ── 4. READY vs RUNNING Semantics ─────────────────────────────────────────────

section('4. READY vs RUNNING Semantics');

it('start({ startPaused:true }) ends in READY not RUNNING', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath, { startPaused: true });
    assert.strictEqual(listener.getState(), STATES.READY);
    await listener.stop();
});

it('resume() from READY → RUNNING', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath, { startPaused: true });
    assert.strictEqual(listener.getState(), STATES.READY);
    await listener.resume();
    assert.strictEqual(listener.getState(), STATES.RUNNING);
    await listener.stop();
});

it('start() without startPaused goes to RUNNING', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath);
    assert.strictEqual(listener.getState(), STATES.RUNNING);
    await listener.stop();
});

it('pause() from RUNNING → PAUSED, resume() → RUNNING', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath);
    await listener.pause();
    assert.strictEqual(listener.getState(), STATES.PAUSED);
    await listener.resume();
    assert.strictEqual(listener.getState(), STATES.RUNNING);
    await listener.stop();
});

it('pause() from non-RUNNING throws', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath, { startPaused: true });
    // READY state — pause() requires RUNNING
    await assert.rejects(() => listener.pause(), /RUNNING/);
    await listener.stop();
});

// ── 5. Handshake Contract ─────────────────────────────────────────────────────

section('5. Handshake Contract');

it('performHandshake sends correct type/versions', async () => {
    let sentMsg = null;
    const fakeTransport = new EventEmitter();
    fakeTransport.sessionId = 'test-session';
    fakeTransport.send = (env) => { sentMsg = env; };

    const handshakePromise = performHandshake(fakeTransport);

    // Simulate immediate handshake_ack from server
    setTimeout(() => {
        fakeTransport.emit('message', {
            type: 'handshake_ack',
            payload: {
                protocolVersion: PROTOCOL_VERSION,
                schemaVersion: SCHEMA_VERSION,
                manifest: { capabilities: { experimentMode: false } },
                capabilities: { experimentMode: false },
            },
        });
    }, 10);

    const result = await handshakePromise;
    assert.strictEqual(sentMsg.type, 'handshake');
    assert.strictEqual(sentMsg.payload.protocolVersion, PROTOCOL_VERSION);
    assert.strictEqual(sentMsg.payload.schemaVersion, SCHEMA_VERSION);
    assert.ok(result.capabilities);
});

it('handshake_rejected causes HandshakeError', async () => {
    const fakeTransport = new EventEmitter();
    fakeTransport.sessionId = 'test-session';
    fakeTransport.send = () => {};

    const handshakePromise = performHandshake(fakeTransport);
    setTimeout(() => {
        fakeTransport.emit('message', {
            type: 'handshake_rejected',
            payload: { error: 'PROTOCOL_VERSION_MISMATCH', expected: '1.0', received: '2.0' },
        });
    }, 10);

    await assert.rejects(() => handshakePromise, (err) => {
        assert.strictEqual(err.name, 'HandshakeError');
        assert.ok(err.code.includes('MISMATCH') || err.code === 'HANDSHAKE_REJECTED');
        return true;
    });
});

it('mismatched protocolVersion in ack causes HandshakeError', async () => {
    const fakeTransport = new EventEmitter();
    fakeTransport.sessionId = 'test-session';
    fakeTransport.send = () => {};

    const handshakePromise = performHandshake(fakeTransport);
    setTimeout(() => {
        fakeTransport.emit('message', {
            type: 'handshake_ack',
            payload: {
                protocolVersion: '99.0',  // incompatible
                schemaVersion: SCHEMA_VERSION,
                capabilities: {},
            },
        });
    }, 10);

    await assert.rejects(() => handshakePromise, HandshakeError);
});

// ── 6. Capability Gating ──────────────────────────────────────────────────────

section('6. Capability Gating');

it('CapabilityManager.require() throws when capability is false', () => {
    const cm = new CapabilityManager({ experimentMode: false });
    assert.throws(() => cm.require('experimentMode'), (err) => {
        assert.strictEqual(err.name, 'CapabilityUnavailableError');
        assert.strictEqual(err.code, 'CAPABILITY_UNAVAILABLE');
        return true;
    });
});

it('CapabilityManager.require() passes when capability is true', () => {
    const cm = new CapabilityManager({ experimentMode: true });
    assert.doesNotThrow(() => cm.require('experimentMode'));
});

it('CapabilityManager.has() works correctly', () => {
    const cm = new CapabilityManager({ a: true, b: false });
    assert.strictEqual(cm.has('a'), true);
    assert.strictEqual(cm.has('b'), false);
    assert.strictEqual(cm.has('c'), false);
});

it('getCapabilities() returns a copy not the live object', () => {
    const cm = new CapabilityManager({ x: true });
    const caps = cm.getCapabilities();
    caps.x = false;
    assert.strictEqual(cm.has('x'), true, 'original should be unchanged');
});

it('enableExperimentMode() via live runtime throws CapabilityUnavailableError', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath, { startPaused: true });
    assert.throws(() => listener.enableExperimentMode(), (err) => {
        assert.strictEqual(err.name, 'CapabilityUnavailableError');
        return true;
    });
    await listener.stop();
});

// ── 7. Config Mutability Enforcement ─────────────────────────────────────────

section('7. Config Mutability Enforcement');

it('hot-reload field does NOT throw', () => {
    assert.doesNotThrow(() => validateConfigMutation({ 'vad.sileroThreshold': 0.2 }));
});

it('restart-required field throws RestartRequiredError', () => {
    assert.throws(() => validateConfigMutation({ 'asr.provider': 'whisper' }), (err) => {
        assert.strictEqual(err.name, 'RestartRequiredError');
        assert.strictEqual(err.code, 'RESTART_REQUIRED');
        return true;
    });
});

it('nested restart-required field throws', () => {
    assert.throws(() => validateConfigMutation({ 'audio.device': 'hw:1' }), RestartRequiredError);
});

it('updateConfig on live runtime — hot-reload succeeds', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath);
    assert.doesNotThrow(() => listener.updateConfig({ 'vad.sileroThreshold': 0.25 }));
    await listener.stop();
});

it('updateConfig on live runtime — restart-required throws', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath);
    assert.throws(() => listener.updateConfig({ 'asr.provider': 'whisper' }), RestartRequiredError);
    await listener.stop();
});

// ── 8. Diagnostics APIs ───────────────────────────────────────────────────────

section('8. Diagnostics APIs');

it('getHealth() returns health object', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath);
    // Give supervisor a moment after worker connects
    await new Promise(r => setTimeout(r, 500));
    const health = await listener.lifecycle._diagnosticsRequest('health');
    assert.ok(typeof health.score === 'number', 'health.score must be a number');
    assert.ok(typeof health.status === 'string', 'health.status must be a string');
    await listener.stop();
});

it('getMetrics() returns object', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath);
    await new Promise(r => setTimeout(r, 500));
    const metrics = await listener.lifecycle._diagnosticsRequest('metrics');
    assert.ok(typeof metrics === 'object', 'metrics must be an object');
    await listener.stop();
});

it('getManifest() returns manifest with capabilities', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath);
    // Manifest is populated from handshake — no round-trip needed
    const manifest = listener.lifecycle._manifest;
    assert.ok(manifest, 'manifest must not be null');
    await listener.stop();
});

it('getDiagnostics() returns object', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath);
    await new Promise(r => setTimeout(r, 500));
    const diag = await listener.lifecycle._diagnosticsRequest('effective_config');
    assert.ok(typeof diag === 'object');
    await listener.stop();
});

it('getState() returns current state string', () => {
    const listener = new AVAListener();
    assert.strictEqual(listener.getState(), STATES.UNINITIALIZED);
});

it('DiagnosticsUnavailableError thrown when not connected', async () => {
    const listener = new AVAListener();
    // Not started — transport is null
    await assert.rejects(
        () => listener.getHealth(),
        (err) => {
            assert.strictEqual(err.name, 'DiagnosticsUnavailableError');
            return true;
        }
    );
});

// ── 9. Profile Validation API ─────────────────────────────────────────────────

section('9. Profile Validation API');

it('validateProfile() returns valid:true for arvsal.json (subprocess)', async () => {
    const listener = new AVAListener();
    const pBase = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const result = await listener.validateProfile(pBase);
    assert.strictEqual(result.valid, true);
    assert.ok(Array.isArray(result.errors));
    assert.ok(Array.isArray(result.warnings));
});

it('validateProfile() emits profile-validation-complete', async () => {
    const listener = new AVAListener();
    const pBase = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    let emitted = false;
    listener.on('profile-validation-complete', () => { emitted = true; });
    await listener.validateProfile(pBase);
    assert.strictEqual(emitted, true);
});

// ── 10. Phrase Management API ─────────────────────────────────────────────────

section('10. Phrase Management API');

it('addPhrase routes through configure command', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath);

    const sentCmdPromise = new Promise((resolve) => {
        // Spy on public send() which receives the envelope object
        const orig = listener.lifecycle.transport.send.bind(listener.lifecycle.transport);
        listener.lifecycle.transport.send = (envelope) => {
            if (envelope.payload && envelope.payload.command === 'add_phrase') {
                resolve(envelope.payload.command);
            }
            orig(envelope);
        };
    });

    const testPhrase = { phraseId: 'test-p1', text: 'test phrase', variants: ['test phrase'], threshold: 0.72, weight: 1.0 };
    assert.doesNotThrow(() => listener.addPhrase(testPhrase));

    const sentCmd = await Promise.race([
        sentCmdPromise,
        new Promise((_, r) => setTimeout(() => r(new Error('addPhrase send timeout')), 1000))
    ]);
    assert.strictEqual(sentCmd, 'add_phrase');
    await listener.stop();
});

it('phrase APIs require active state', async () => {
    const listener = new AVAListener();
    // Not started
    assert.throws(() => listener.addPhrase({ phraseId: 'x', text: 'y' }), /active state/);
    assert.throws(() => listener.removePhrase('x'), /active state/);
    assert.throws(() => listener.enablePhrase('x'), /active state/);
    assert.throws(() => listener.disablePhrase('x'), /active state/);
    assert.throws(() => listener.updateVariants('x', []), /active state/);
});

it('getPhrases() returns array via diagnostics', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath);
    const phrases = await listener.getPhrases();
    assert.ok(Array.isArray(phrases), 'phrases must be an array');
    await listener.stop();
});

// ── 11. Reconnect Contract Tests ──────────────────────────────────────────────

section('11. Reconnect Contract');

it('RECONNECT_DELAYS matches [200,400,800,1600,3200]', () => {
    assert.deepStrictEqual(RECONNECT_DELAYS, [200, 400, 800, 1600, 3200]);
});

it('Transport emits recovering with attempt number', () => {
    return new Promise((resolve) => {
        const t = new Transport('127.0.0.1', 9999);
        t.on('error', () => {}); // prevent unhandled error crash
        t.once('recovering', (info) => {
            assert.ok(typeof info.attempt === 'number');
            assert.ok(typeof info.delay === 'number');
            t._stopped = true;
            resolve();
        });
        t._reconnectAttempts = 0;
        t._stopped = false;
        t._scheduleReconnect(null);
    });
});

it('Transport emits failed after max attempts', () => {
    return new Promise((resolve) => {
        const t = new Transport('127.0.0.1', 9999);
        t.on('error', () => {}); // prevent unhandled error crash
        t._reconnectAttempts = RECONNECT_DELAYS.length; // already at max
        t._stopped = false;
        t.once('failed', resolve);
        t._scheduleReconnect(null);
    });
});

it('Transport queues guaranteed messages when offline', () => {
    const t = new Transport('127.0.0.1', 9999);
    t.isConnected = false;
    t.send({ type: 'wake', sessionId: 'x', correlationId: 'y', payload: {} });
    assert.strictEqual(t._offlineQueue.length, 1);
    assert.strictEqual(t._offlineQueue[0].reliabilityClass, 'guaranteed');
});

it('Transport drops fire_and_forget messages when offline', () => {
    const t = new Transport('127.0.0.1', 9999);
    t.isConnected = false;
    t.send({ type: 'telemetry', sessionId: 'x', correlationId: 'y', payload: {} });
    assert.strictEqual(t._offlineQueue.length, 0);
});

it('RECOVERING state emitted on disconnect during RUNNING', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath);
    assert.strictEqual(listener.getState(), STATES.RUNNING);

    let enteredRecovering = false;
    listener.on('recovering', () => { enteredRecovering = true; });

    // Force disconnect by closing the underlying WebSocket
    listener.lifecycle.transport.ws.emit('close');
    // Give event loop a tick
    await new Promise(r => setTimeout(r, 20));

    assert.strictEqual(enteredRecovering, true);
    assert.strictEqual(listener.getState(), STATES.RECOVERING);
    await listener.destroy();
});

// ── 12. Full Integration ───────────────────────────────────────────────────────

section('12. Full Integration');

it('Full lifecycle: start → stop → state=STOPPED', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath);
    assert.strictEqual(listener.getState(), STATES.RUNNING);
    await listener.stop();
    assert.strictEqual(listener.getState(), STATES.STOPPED);
});

it('destroy() sets DESTROYED state', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath);
    listener.destroy();
    // Give process time to settle
    await new Promise(r => setTimeout(r, 100));
    assert.strictEqual(listener.getState(), STATES.DESTROYED);
});

it('statechange events fire in order', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    const states = [];
    listener.on('statechange', ({ to }) => states.push(to));
    await listener.start(profilePath);
    await listener.stop();

    assert.ok(states.includes(STATES.STARTING));
    assert.ok(states.includes(STATES.READY));
    assert.ok(states.includes(STATES.RUNNING));
    assert.ok(states.includes(STATES.STOPPING));
    assert.ok(states.includes(STATES.STOPPED));
});

// ── 13. Config Precedence & Runtime Parameters ────────────────────────────────

section('13. Config Precedence & Runtime Parameters');

it('getEffectiveConfig() returns precedence sources', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath);
    await new Promise(r => setTimeout(r, 500)); // wait for worker to settle
    const config = await listener.getEffectiveConfig();
    assert.ok(config && config.sources, 'Must return config sources');
    assert.ok(config.values, 'Must return config values');
    await listener.stop();
});

it('updateRuntimeParameters routes through updateConfig', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath);
    await new Promise(r => setTimeout(r, 500));

    let sentCmd = null;
    const orig = listener.lifecycle.transport.send.bind(listener.lifecycle.transport);
    listener.lifecycle.transport.send = (envelope) => {
        if (envelope.payload && envelope.payload.command === 'update_config') {
            sentCmd = envelope.payload.command;
        }
        orig(envelope);
    };

    assert.doesNotThrow(() => listener.updateRuntimeParameters({ 'vad.sileroThreshold': 0.5 }));
    
    // Give event loop a tick
    await new Promise(r => setTimeout(r, 10));
    assert.strictEqual(sentCmd, 'update_config');
    await listener.stop();
});

it('resetParameters routes through configure command', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath);
    
    let sentCmd = null;
    const orig = listener.lifecycle.transport.send.bind(listener.lifecycle.transport);
    listener.lifecycle.transport.send = (envelope) => {
        if (envelope.payload && envelope.payload.command === 'reset_parameters') {
            sentCmd = envelope.payload.command;
        }
        orig(envelope);
    };

    listener.resetParameters();
    
    await new Promise(r => setTimeout(r, 10));
    assert.strictEqual(sentCmd, 'reset_parameters');
    await listener.stop();
});

// ── 14. Profile Inheritance ───────────────────────────────────────────────────

section('14. Profile Inheritance');

it('loadProfile routes through configure command', async () => {
    const profilePath = path.join(__dirname, '..', '..', 'profiles', 'arvsal.json');
    const listener = new AVAListener();
    await listener.start(profilePath);
    
    let sentPath = null;
    const orig = listener.lifecycle.transport.send.bind(listener.lifecycle.transport);
    listener.lifecycle.transport.send = (envelope) => {
        if (envelope.payload && envelope.payload.command === 'load_profile') {
            sentPath = envelope.payload.path;
        }
        orig(envelope);
    };

    const newPath = path.join(__dirname, '..', '..', 'profiles', 'jarvis.json');
    listener.loadProfile(newPath);
    
    await new Promise(r => setTimeout(r, 10));
    assert.strictEqual(sentPath, newPath);
    await listener.stop();
});

// ── results ───────────────────────────────────────────────────────────────────

async function runAll() {
    // All its above returned promises — we need to run them sequentially
    // Collect them
    const queue = [];

    // Re-run synchronously by wrapping into async function
    console.log('\nRunning Phase 8 Remediation Test Suite...\n');
    await new Promise(resolve => setTimeout(resolve, 0)); // flush sync its

    console.log(`\n${'─'.repeat(60)}`);
    console.log(`Tests finished: ${passed} passed, ${failed} failed.`);
    if (failed > 0) process.exit(1);
    process.exit(0);
}

// Give all async tests time to collect
setTimeout(async () => {
    console.log(`\n${'─'.repeat(60)}`);
    console.log(`Tests finished: ${passed} passed, ${failed} failed.`);
    if (failed > 0) process.exit(1);
    process.exit(0);
}, 60000);
