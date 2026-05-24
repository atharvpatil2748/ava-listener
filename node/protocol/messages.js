const crypto = require('crypto');
const { SCHEMA_VERSION } = require('./version');

function createEnvelope(type, payload, sessionId) {
    return {
        type,
        schemaVersion: SCHEMA_VERSION,
        timestamp: Date.now() / 1000.0,
        sessionId: sessionId || 'node_sdk',
        correlationId: crypto.randomUUID(),
        payload: payload || {}
    };
}

module.exports = { createEnvelope };
