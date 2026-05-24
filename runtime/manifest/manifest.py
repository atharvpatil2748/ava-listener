"""Runtime manifest — declares capabilities exposed to the Node SDK via handshake_ack."""

PROTOCOL_VERSION = "1.0"
SCHEMA_VERSION = 1

# Capability flags surfaced to the SDK in the handshake_ack manifest.
# Add future capability keys here and wire require() calls in the SDK.
CAPABILITIES = {
    "experimentMode": False,
    "liveConfigReload": True,
    "phraseRegistry": True,
    "diagnosticsAPI": True,
    "profileValidation": True,
}


def get_manifest() -> dict:
    """Return the full runtime manifest dict sent during handshake."""
    import platform, sys
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "schemaVersion": SCHEMA_VERSION,
        "capabilities": CAPABILITIES,
        "platform": platform.system().lower(),
        "pythonVersion": sys.version.split()[0],
    }
