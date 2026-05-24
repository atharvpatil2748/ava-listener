import asyncio
import json
import threading
import time
import sys
import os
import websockets

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.transport.websocket_server import WSServer

async def run_tests():
    print("Starting WSServer...")
    server = WSServer(host="127.0.0.1", port=0)
    server.start_in_thread()
    time.sleep(0.5)
    uri = f"ws://127.0.0.1:{server.port}"
    print(f"Server started at {uri}")

    try:
        # Test 1: Connect and receive broadcast
        print("Test 1: Connect and receive broadcast")
        async with websockets.connect(uri) as ws:
            msg = {
                "type": "wake",
                "schemaVersion": 1,
                "timestamp": time.time(),
                "sessionId": "test-session",
                "correlationId": "test-corr",
                "payload": {"phrase": "hello"}
            }
            server.broadcast(msg)
            response_str = await asyncio.wait_for(ws.recv(), timeout=2.0)
            response = json.loads(response_str)
            assert response["type"] == "wake", f"Expected wake, got {response['type']}"
            assert response["payload"]["phrase"] == "hello", "Payload phrase mismatch"
        print("  PASS")

        # Test 2: Schema validation rejects malformed
        print("Test 2: Schema validation rejects malformed")
        received_msgs = []
        server.on_message = lambda m: received_msgs.append(m)
        async with websockets.connect(uri) as ws:
            invalid_msg = {
                "type": "start",
                "payload": {}
            }
            await ws.send(json.dumps(invalid_msg))
            error_str = await asyncio.wait_for(ws.recv(), timeout=2.0)
            error_msg = json.loads(error_str)
            assert error_msg["type"] == "error", "Expected error message"
            assert error_msg["payload"]["code"] == "PROTOCOL_ERROR", "Expected PROTOCOL_ERROR"
            assert len(received_msgs) == 0, "Server should not process malformed msg"
        print("  PASS")

        # Test 3: Schema validation accepts valid
        print("Test 3: Schema validation accepts valid")
        received_msgs.clear()
        async with websockets.connect(uri) as ws:
            valid_msg = {
                "type": "start",
                "schemaVersion": 1,
                "timestamp": time.time(),
                "sessionId": "s1",
                "correlationId": "c1",
                "payload": {}
            }
            await ws.send(json.dumps(valid_msg))
            await asyncio.sleep(0.2)
            assert len(received_msgs) == 1, f"Expected 1 valid message, got {len(received_msgs)}"
            assert received_msgs[0]["type"] == "start", "Message type mismatch"
        print("  PASS")

        # Test 4: Reconnect resilience
        print("Test 4: Reconnect resilience")
        async with websockets.connect(uri) as ws1:
            assert len(server.clients) == 1
        
        await asyncio.sleep(0.2)
        server.broadcast({"type": "heartbeat", "payload": {}})
        await asyncio.sleep(0.2)
        assert len(server.clients) == 0, "Server should have dropped disconnected client"
        
        async with websockets.connect(uri) as ws2:
            assert len(server.clients) == 1
            server.broadcast({
                "type": "wake",
                "schemaVersion": 1,
                "timestamp": time.time(),
                "sessionId": "s1",
                "correlationId": "c1",
                "payload": {}
            })
            response = await asyncio.wait_for(ws2.recv(), timeout=2.0)
            msg = json.loads(response)
            assert msg["type"] == "wake"
        print("  PASS")

    finally:
        print("Stopping server...")
        server.stop()

if __name__ == "__main__":
    asyncio.run(run_tests())
    print("All tests passed.")
