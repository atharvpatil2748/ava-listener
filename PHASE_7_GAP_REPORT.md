# Phase 7 Gap Report

## Core Deficiencies Preventing Promotion

### Gap 1: Missing Node SDK Client
**Description:** Phase 7 mandates creating a WebSocket client for the Node SDK. The current implementation only mocked client interactions via a Python test script (`scripts/test_websocket.py`).
**Required Fix:** 
- Implement an actual Node.js client (`sdk/client.js` or equivalent) that connects to the Python WebSocket server.
- Write a Node.js test script to verify connection, heartbeat, and roundtrip messaging end-to-end.

### Gap 2: Missing Transport Reliability Classes
**Description:** The plan requires implementing transport reliability classes (`guaranteed`, `retry`, `best_effort`, `fire_and_forget`). Currently, `WSServer.broadcast()` blasts raw payloads synchronously via `asyncio` without evaluating message priority or awaiting acknowledgments.
**Required Fix:**
- Introduce a message queuing layer mapped to transport priority.
- `wake` and critical error events MUST require explicit client acknowledgment (`ACK`).
- Unacknowledged critical events must be retried or preserved.
- `partial_transcript` and `telemetry` can remain fire-and-forget.

### Gap 3: Event Loss During Reconnection
**Description:** Reconnect behavior is tested, but offline durability is not. When a client disconnects, `WSServer` drops all broadcast payloads. Wake events that occur between connection drop and re-establishment are permanently lost, directly violating "preserve critical-event delivery guarantees".
**Required Fix:**
- Implement an offline event buffer for `guaranteed` and `retry` level messages.
- Upon client reconnection, immediately flush the offline buffer so no critical events are lost.

### Summary
The Python baseline for WebSocket protocol handling and validation is successfully in place. However, the networking durability (queues, offline buffering, ACKs) and actual Javascript cross-boundary integration are entirely absent. These gaps must be completely resolved before Phase 7 can be marked Done.
