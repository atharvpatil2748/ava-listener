# Phase 7 Implementation Map: WebSocket Transport Layer

## Scope & Philosophy
The goal is to replace the fragile stdout parsing between the Node SDK and the Supervisor/Worker runtime with a robust WebSocket-based transport.
- The Python runtime acts as the **WebSocket Server**.
- The Node.js SDK acts as the **WebSocket Client**.
- The transport plane separates `Control` (start, stop, validate_profile) from `Stream` (wake, transcripts, telemetry).
- Stdout / IPC pathways remain as non-negotiable fallbacks/shims during the migration.
- Existing wake behavior and supervisor architectures are strictly preserved.

## Step 1: Transport Core & Server
- **Objective:** Create an asynchronous WebSocket server hosted by the Python runtime boundary (the Supervisor process).
- **Location:** `runtime/transport/websocket_server.py`
- **Responsibilities:**
  - Bind to `127.0.0.1` (V1 trust boundary).
  - Accept multiple/single WS client connections (from Node SDK).
  - Forward runtime IPC events from the Worker into WebSocket frames.
  - Forward WebSocket incoming commands to the Worker via IPC.

## Step 2: Message Schemas & Validation
- **Objective:** Establish the typed message protocol and validation layer.
- **Location:** `runtime/transport/protocol/`
- **Schemas:**
  - Common envelope: `type`, `schemaVersion`, `timestamp`, `sessionId`, `correlationId`, `payload`.
  - Control plane: `start`, `stop`, `configure`, `diagnostics_request`, `diagnostics_response`, `validate_profile`, `health`, `shutdown`.
  - Stream plane: `wake`, `speech_start`, `speech_end`, `partial_transcript`, `hypothesis_update`, `telemetry`, `error`, `heartbeat`.
- **Validation:** JSON schema validation rejecting malformed payloads before they reach runtime logic.

## Step 3: Resilience & Fault Tolerance
- **Objective:** Ensure the WS layer handles network blips transparently without losing critical events.
- **Features:**
  - Heartbeat (`ping`/`pong`) mechanisms.
  - Reconnect / retry logic for SDK side.
  - Delivery guarantees for critical events (`wake`, `error`).

## Step 4: Migration & Node SDK Client
- **Objective:** Introduce the Node SDK WS client.
- **Location:** Node SDK structure (`sdk/` or similar JS wrappers).
- **Features:** Wrap the Node.js implementation to connect to the WS server spawned by Python.
- **Backward Compatibility:** Python `main.py --mode supervised` will start the WS server but continue emitting JSON to stdout so existing `scripts/` are not broken.

## Step 5: Validation & Testing
- **WebSocket transport tests:** Verify message roundtrips and parsing.
- **Reconnect tests:** Drop connection, reconnect, and verify queue persistence.
- **Schema tests:** Inject malformed JSON and verify explicit rejection.
- All existing tests (`verify_startup.py`, `wake_regression.py`, `test_supervisor_recovery.py`) must continue passing.
