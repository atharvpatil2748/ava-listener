import asyncio
import json
import time
import sys
import os
import websockets

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from runtime.transport.websocket_server import WSServer

async def run_tests():
    print("Starting WSServer...")
    server = WSServer(host="127.0.0.1", port=0)
    server.start_in_thread()
    time.sleep(0.5)
    uri = f"ws://127.0.0.1:{server.port}"
    print(f"Server started at {uri}")

    try:
        # Test Guaranteed (needs ACK)
        print("Testing Guaranteed class (wake)...")
        async with websockets.connect(uri) as ws:
            server.broadcast({"type": "wake", "payload": {}})
            msg_str = await asyncio.wait_for(ws.recv(), timeout=2.0)
            msg = json.loads(msg_str)
            assert msg["type"] == "wake"
            corr_id = msg["correlationId"]
            assert corr_id in server.pending_acks
            # Send ACK
            await ws.send(json.dumps({
                "type": "ack",
                "schemaVersion": 1,
                "timestamp": time.time(),
                "sessionId": "s1",
                "correlationId": "c1",
                "payload": {"correlationId": corr_id}
            }))
            await asyncio.sleep(0.2)
            assert corr_id not in server.pending_acks
        print("  PASS")

        # Test Retry class (needs ACK)
        print("Testing Retry class (speech_start)...")
        async with websockets.connect(uri) as ws:
            server.broadcast({"type": "speech_start", "payload": {}})
            msg_str = await asyncio.wait_for(ws.recv(), timeout=2.0)
            msg = json.loads(msg_str)
            assert msg["type"] == "speech_start"
            corr_id = msg["correlationId"]
            assert corr_id in server.pending_acks
            # Do NOT send ACK. Let it retry.
            msg_str_2 = await asyncio.wait_for(ws.recv(), timeout=2.0)
            msg2 = json.loads(msg_str_2)
            assert msg2["correlationId"] == corr_id
            
            # Now send ACK
            await ws.send(json.dumps({
                "type": "ack",
                "schemaVersion": 1,
                "timestamp": time.time(),
                "sessionId": "s1",
                "correlationId": "c1",
                "payload": {"correlationId": corr_id}
            }))
            await asyncio.sleep(0.2)
            assert corr_id not in server.pending_acks
        print("  PASS")

        # Test Best Effort (Batching)
        print("Testing Best Effort class (batching)...")
        async with websockets.connect(uri) as ws:
            server.broadcast({"type": "partial_transcript", "payload": {"text": "h"}})
            server.broadcast({"type": "partial_transcript", "payload": {"text": "he"}})
            msg_str = await asyncio.wait_for(ws.recv(), timeout=2.0)
            msg = json.loads(msg_str)
            assert msg["type"] == "batch"
            events = msg["payload"]["events"]
            assert len(events) == 2
            assert events[0]["type"] == "partial_transcript"
            assert events[1]["payload"]["text"] == "he"
        print("  PASS")
        
    finally:
        server.stop()

if __name__ == "__main__":
    asyncio.run(run_tests())
