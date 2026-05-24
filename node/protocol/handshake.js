/**
 * Phase 8 handshake — architecture-compliant two-step protocol:
 *
 *   Client → { type:"handshake", schemaVersion:1, protocolVersion:"1.0" }
 *   Server → { type:"handshake_ack", payload:{ protocolVersion, schemaVersion, manifest, capabilities } }
 *           OR { type:"handshake_rejected", payload:{ error, expected, received } }
 *
 * On incompatible version the promise rejects with HandshakeError.
 * On success, resolves with the full manifest payload.
 */

const { createEnvelope } = require('./messages');
const logger = require('../utils/logger');

const PROTOCOL_VERSION = '1.0';
const SCHEMA_VERSION = 1;

class HandshakeError extends Error {
    constructor(message, code) {
        super(message);
        this.name = 'HandshakeError';
        this.code = code || 'HANDSHAKE_FAILED';
    }
}

// Schema version migration hooks — for future schema bumps
const SCHEMA_MIGRATIONS = {
    // Example future hook:
    // 2: (payload) => { /* transform v1 payload to v2 */ return payload; }
};

function applyMigrations(payload, fromVersion, toVersion) {
    let result = payload;
    for (let v = fromVersion + 1; v <= toVersion; v++) {
        if (SCHEMA_MIGRATIONS[v]) {
            result = SCHEMA_MIGRATIONS[v](result);
            logger.info(`Applied handshake schema migration to v${v}`);
        }
    }
    return result;
}

async function performHandshake(transport) {
    return new Promise((resolve, reject) => {
        const timeout = setTimeout(
            () => reject(new HandshakeError('Handshake timed out after 15s', 'HANDSHAKE_TIMEOUT')),
            15000
        );

        const onMessage = (msg) => {
            // Only log meaningful handshake messages (not heartbeats/status spam)
            if (msg.type !== 'heartbeat' && msg.type !== 'status') {
                logger.info('Handshake ← type:', msg.type);
            }

            if (msg.type === 'handshake_rejected') {
                clearTimeout(timeout);
                transport.removeListener('message', onMessage);
                const p = msg.payload || {};
                reject(new HandshakeError(
                    `Handshake rejected: ${p.error} (expected=${p.expected}, received=${p.received})`,
                    p.error || 'HANDSHAKE_REJECTED'
                ));
                return;
            }

            if (msg.type === 'handshake_ack') {
                clearTimeout(timeout);
                transport.removeListener('message', onMessage);

                const p = msg.payload || {};

                // Validate versions
                if (p.protocolVersion !== PROTOCOL_VERSION) {
                    reject(new HandshakeError(
                        `Protocol version mismatch: expected ${PROTOCOL_VERSION}, got ${p.protocolVersion}`,
                        'PROTOCOL_VERSION_MISMATCH'
                    ));
                    return;
                }
                const serverSchema = p.schemaVersion;
                if (serverSchema !== SCHEMA_VERSION) {
                    if (serverSchema < SCHEMA_VERSION) {
                        logger.warn(`Server schema v${serverSchema} older than client v${SCHEMA_VERSION}; applying migrations`);
                        p.manifest = applyMigrations(p.manifest, serverSchema, SCHEMA_VERSION);
                    } else {
                        reject(new HandshakeError(
                            `Schema version mismatch: client is v${SCHEMA_VERSION}, server is v${serverSchema}. Upgrade the SDK.`,
                            'SCHEMA_VERSION_MISMATCH'
                        ));
                        return;
                    }
                }

                logger.info('Handshake complete. Capabilities:', JSON.stringify(p.capabilities));
                resolve(p);
                return;
            }
        };

        transport.on('message', onMessage);

        // Send the handshake initiation message
        transport.send({
            type: 'handshake',
            schemaVersion: SCHEMA_VERSION,
            protocolVersion: PROTOCOL_VERSION,
            timestamp: Date.now() / 1000.0,
            sessionId: transport.sessionId,
            correlationId: require('crypto').randomUUID(),
            payload: {
                protocolVersion: PROTOCOL_VERSION,
                schemaVersion: SCHEMA_VERSION,
            },
        });

        logger.info(`Handshake → protocolVersion=${PROTOCOL_VERSION} schemaVersion=${SCHEMA_VERSION}`);
    });
}

module.exports = { performHandshake, HandshakeError, PROTOCOL_VERSION, SCHEMA_VERSION };
