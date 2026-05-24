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
        # Client disconnects, server broadcasts, client reconnects
        print("Testing Reconnect Durability...")
        async with websockets.connect(uri) as ws1:
            pass # just connect and close
            
        await asyncio.sleep(0.2)
        assert len(server.clients) == 0

        # Broadcast guaranteed event while offline
        server.broadcast({"type": "wake", "payload": {"status": "offline_msg"}})
        
        # It should go to offline queue or pending_acks then moved to offline_queue
        await asyncio.sleep(0.6) # allow retry loop to move to offline
        assert len(server.offline_queue) > 0

        # Reconnect
        async with websockets.connect(uri) as ws2:
            # We should immediately receive the queued wake event
            msg_str = await asyncio.wait_for(ws2.recv(), timeout=2.0)
            msg = json.loads(msg_str)
            assert msg["type"] == "wake"
            assert msg["payload"]["status"] == "offline_msg"
        
        print("  PASS")
        
    finally:
        server.stop()

if __name__ == "__main__":
    asyncio.run(run_tests())
