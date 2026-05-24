const WebSocket = require('ws');
const EventEmitter = require('events');
const crypto = require('crypto');

class AVAListenerClient extends EventEmitter {
    constructor(port = 5050, host = '127.0.0.1') {
        super();
        this.port = port;
        this.host = host;
        this.ws = null;
        this.sessionId = crypto.randomUUID();
        this.isConnected = false;
    }

    connect() {
        return new Promise((resolve, reject) => {
            this.ws = new WebSocket(`ws://${this.host}:${this.port}`);
            
            this.ws.on('open', () => {
                this.isConnected = true;
                this.emit('connected');
                resolve();
            });

            this.ws.on('message', (data) => {
                try {
                    const msg = JSON.parse(data);
                    this.handleMessage(msg);
                } catch (err) {
                    this.emit('error', new Error('Failed to parse message: ' + err.message));
                }
            });

            this.ws.on('close', () => {
                this.isConnected = false;
                this.emit('disconnected');
            });

            this.ws.on('error', (error) => {
                this.emit('error', error);
                if (!this.isConnected) {
                    reject(error);
                }
            });
        });
    }

    handleMessage(msg) {
        if (!msg || !msg.type) return;

        // Auto-ack if correlationId is present (for guaranteed/retry classes)
        if (msg.correlationId) {
            const needsAck = ['wake', 'fatal_error', 'speech_start', 'speech_end', 'error'].includes(msg.type);
            if (needsAck) {
                this.sendAck(msg.correlationId);
            }
        }

        if (msg.type === 'batch') {
            const events = msg.payload.events || [];
            for (const evt of events) {
                this.emit(evt.type, evt.payload);
            }
        } else {
            this.emit(msg.type, msg.payload);
        }
    }

    getEffectiveConfig() {
        return new Promise((resolve, reject) => {
            const correlationId = crypto.randomUUID();
            const timeout = setTimeout(() => reject(new Error('Timeout waiting for effective config')), 5000);
            
            const onResponse = (payload) => {
                if (payload.correlationId === correlationId) {
                    clearTimeout(timeout);
                    this.removeListener('diagnostics_response', onResponse);
                    resolve(payload.result); // assuming result has {values, sources}
                }
            };
            this.on('diagnostics_response', onResponse);
            
            this.send({
                type: 'diagnostics_request',
                correlationId,
                payload: { type: 'effective_config' }
            });
        });
    }

    validateProfile(path) {
        return new Promise((resolve, reject) => {
            const correlationId = crypto.randomUUID();
            const timeout = setTimeout(() => reject(new Error('Timeout waiting for validate profile')), 5000);
            
            const onResponse = (payload) => {
                if (payload.correlationId === correlationId) {
                    clearTimeout(timeout);
                    this.removeListener('validate_profile_response', onResponse);
                    resolve(payload.result);
                }
            };
            this.on('validate_profile_response', onResponse);
            
            this.send({
                type: 'validate_profile',
                correlationId,
                payload: { path }
            });
        });
    }

    sendAck(correlationId) {
        this.send({
            type: 'ack',
            payload: { correlationId }
        });
    }

    send(messageObj) {
        if (!this.isConnected || !this.ws) return;

        const envelope = {
            type: messageObj.type || 'unknown',
            schemaVersion: 1,
            timestamp: Date.now() / 1000,
            sessionId: this.sessionId,
            correlationId: messageObj.correlationId || crypto.randomUUID(),
            payload: messageObj.payload || {}
        };

        this.ws.send(JSON.stringify(envelope));
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
            this.isConnected = false;
        }
    }
}

module.exports = AVAListenerClient;
