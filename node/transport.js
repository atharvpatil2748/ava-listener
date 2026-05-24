/**
 * Phase 8 Transport — WebSocket client with exact reconnect contract.
 *
 * Reconnect backoff: 200ms → 400ms → 800ms → 1600ms → 3200ms (max 5 attempts)
 * On exhaustion: emits 'failed'
 * On reconnect: emits 'reconnected', replays offline queue
 * Critical events (guaranteed/retry classes) are queued offline during disconnect.
 */

const WebSocket = require('ws');
const EventEmitter = require('events');
const crypto = require('crypto');
const logger = require('./utils/logger');

const PROTOCOL_VERSION = '1.0';

// Reliability classes (from architecture)
const GUARANTEED  = new Set(['wake', 'fatal_error']);
const RETRY       = new Set(['speech_start', 'speech_end', 'error']);
const BEST_EFFORT = new Set(['partial_transcript', 'hypothesis_update']);
// fire_and_forget: telemetry, debug — send once, no queue

// Reconnect delays: 200ms, 400ms, 800ms, 1600ms, 3200ms
const RECONNECT_DELAYS = [200, 400, 800, 1600, 3200];

class Transport extends EventEmitter {
    constructor(host = '127.0.0.1', port = null) {
        super();
        this.host = host;
        this.port = port;
        this.ws = null;
        this.sessionId = crypto.randomUUID();
        this.isConnected = false;
        this._reconnectAttempts = 0;
        this._reconnectTimer = null;
        this._stopped = false;           // set to true by close() to prevent reconnect
        this._offlineQueue = [];         // { envelope, reliabilityClass }
        this._previousState = null;      // state to restore on reconnect
    }

    connect() {
        if (!this.port) throw new Error('Transport: port not specified');
        return new Promise((resolve, reject) => {
            const url = `ws://${this.host}:${this.port}`;
            logger.info(`Connecting to ${url}...`);
            this.ws = new WebSocket(url);

            this.ws.on('open', () => {
                this.isConnected = true;
                this._reconnectAttempts = 0;
                logger.info('Connected to runtime WS');
                this.emit('connected');
                resolve();
            });

            this.ws.on('message', (data) => {
                try {
                    const msg = JSON.parse(data);
                    this._handleMessage(msg);
                } catch (e) {
                    logger.error('Failed to parse WS message:', e.message);
                }
            });

            this.ws.on('close', () => {
                const wasConnected = this.isConnected;
                this.isConnected = false;
                if (!this._stopped) {
                    this.emit('disconnected');
                    this._scheduleReconnect(wasConnected ? null : reject);
                }
            });

            this.ws.on('error', (err) => {
                // Always emit our own error event (listeners can handle it)
                this.emit('error', err);
                // Only reject the initial connect promise if we haven't connected yet
                if (!this.isConnected) {
                    reject(err);
                }
            });
        });
    }

    _scheduleReconnect(initialReject) {
        if (this._stopped) return;

        if (this._reconnectAttempts >= RECONNECT_DELAYS.length) {
            logger.error(`Max reconnect attempts (${RECONNECT_DELAYS.length}) exhausted. Emitting failed.`);
            this.emit('failed');
            if (initialReject) initialReject(new Error('Transport: max reconnect attempts exhausted'));
            return;
        }

        const delay = RECONNECT_DELAYS[this._reconnectAttempts];
        logger.info(`Reconnecting in ${delay}ms (attempt ${this._reconnectAttempts + 1}/${RECONNECT_DELAYS.length})...`);
        this.emit('recovering', { attempt: this._reconnectAttempts + 1, delay });

        this._reconnectTimer = setTimeout(() => {
            this._reconnectAttempts++;
            this.connect()
                .then(() => {
                    logger.info(`Reconnected after ${this._reconnectAttempts} attempt(s)`);
                    this.emit('reconnected', { attempts: this._reconnectAttempts });
                    this._reconnectAttempts = 0;
                    this._flushOfflineQueue();
                })
                .catch((err) => {
                    // Connection failed — the 'close' event will fire and retry
                    logger.warn(`Reconnect attempt ${this._reconnectAttempts} failed: ${err.message}`);
                });
        }, delay);
    }

    _flushOfflineQueue() {
        if (this._offlineQueue.length === 0) return;
        logger.info(`Flushing ${this._offlineQueue.length} offline queued message(s)`);
        const queue = [...this._offlineQueue];
        this._offlineQueue = [];
        for (const { envelope } of queue) {
            this._rawSend(envelope);
        }
    }

    _handleMessage(msg) {
        if (msg.type !== 'heartbeat' && msg.type !== 'status') {
            logger.info('Transport ← type:', msg.type);
        }
        // Auto-ack guaranteed/retry messages
        if (msg.correlationId) {
            const needsAck = GUARANTEED.has(msg.type) || RETRY.has(msg.type);
            if (needsAck) {
                this._rawSend({
                    type: 'ack',
                    schemaVersion: 1,
                    timestamp: Date.now() / 1000.0,
                    sessionId: this.sessionId,
                    correlationId: crypto.randomUUID(),
                    payload: { correlationId: msg.correlationId },
                });
            }
        }

        // Unwrap batch
        if (msg.type === 'batch') {
            const events = (msg.payload && msg.payload.events) ? msg.payload.events : [];
            for (const evt of events) {
                this.emit('message', evt);
            }
        } else {
            this.emit('message', msg);
        }
    }

    /**
     * Send an envelope, respecting reliability classes.
     * guaranteed/retry: queued offline if disconnected
     * fire_and_forget/best_effort: dropped if disconnected
     */
    send(envelope) {
        if (!envelope.sessionId) envelope.sessionId = this.sessionId;

        const cls = this._classifyMessage(envelope.type);

        if (!this.isConnected || !this.ws) {
            if (cls === 'guaranteed' || cls === 'retry') {
                this._offlineQueue.push({ envelope, reliabilityClass: cls });
                logger.warn(`Offline: queued ${envelope.type} (${cls})`);
            } else {
                logger.warn(`Offline: dropped ${envelope.type} (${cls})`);
            }
            return;
        }

        this._rawSend(envelope);
    }

    _rawSend(envelope) {
        try {
            logger.debug('WS send', envelope);
            this.ws.send(JSON.stringify(envelope));
        } catch (e) {
            logger.error('Send error:', e.message);
        }
    }

    _classifyMessage(type) {
        if (GUARANTEED.has(type))  return 'guaranteed';
        if (RETRY.has(type))       return 'retry';
        if (BEST_EFFORT.has(type)) return 'best_effort';
        return 'fire_and_forget';
    }

    /** Record previous SDK state for restoration on reconnect */
    setPreviousState(state) {
        this._previousState = state;
    }

    getPreviousState() {
        return this._previousState;
    }

    close() {
        this._stopped = true;
        if (this._reconnectTimer) {
            clearTimeout(this._reconnectTimer);
            this._reconnectTimer = null;
        }
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.isConnected = false;
    }
}

module.exports = { Transport, RECONNECT_DELAYS, GUARANTEED, RETRY, BEST_EFFORT };
