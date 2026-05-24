"""Message schemas for the WebSocket Transport Layer (Phase 7)."""

# The base envelope required for all messages
ENVELOPE_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string"},
        "schemaVersion": {"type": "integer"},
        "timestamp": {"type": "number"},
        "sessionId": {"type": "string"},
        "correlationId": {"type": "string"},
        "payload": {"type": "object"}
    },
    "required": ["type", "schemaVersion", "timestamp", "sessionId", "correlationId", "payload"],
    "additionalProperties": True
}

CONTROL_TYPES = {
    "start",
    "stop",
    "configure",
    "diagnostics_request",
    "diagnostics_response",
    "validate_profile",
    "health",
    "shutdown",
    "crash_worker",
    "ack",
    "batch",
    "handshake",
    "handshake_ack",
    "handshake_rejected",
    "status",
}

STREAM_TYPES = {
    "wake",
    "speech_start",
    "speech_end",
    "partial_transcript",
    "hypothesis_update",
    "telemetry",
    "error",
    "heartbeat"
}

# Example specific payload schemas could be added here.
# For Phase 7, enforcing the envelope and type is the baseline validation,
# while the payload content varies. We validate the envelope first.

def get_message_schema() -> dict:
    return ENVELOPE_SCHEMA
