import asyncio
import json
import threading
import time
import pytest
import websockets
import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from runtime.transport.websocket_server import WSServer
from runtime.transport.protocol.schemas import get_message_schema

@pytest.fixture
def ws_server():
    server = WSServer(host="127.0.0.1", port=0) # bind to random open port
    server.start_in_thread()
    # Wait for server to bind and be ready
    time.sleep(0.5)
    yield server
    server.stop()

@pytest.mark.asyncio
async def test_websocket_connect_and_receive(ws_server):
    uri = f"ws://127.0.0.1:{ws_server.port}"
    async with websockets.connect(uri) as ws:
        # Broadcast a message from server
        msg = {
            "type": "wake",
            "schemaVersion": 1,
            "timestamp": time.time(),
            "sessionId": "test-session",
            "correlationId": "test-corr",
            "payload": {"phrase": "hello"}
        }
        # Server broadcasts asynchronously
        ws_server.broadcast(msg)
        
        # Client receives
        response_str = await asyncio.wait_for(ws.recv(), timeout=2.0)
        response = json.loads(response_str)
        assert response["type"] == "wake"
        assert response["payload"]["phrase"] == "hello"

@pytest.mark.asyncio
async def test_schema_validation_rejects_malformed(ws_server):
    uri = f"ws://127.0.0.1:{ws_server.port}"
    
    received_msgs = []
    def on_msg(m): received_msgs.append(m)
    ws_server.on_message = on_msg
    
    async with websockets.connect(uri) as ws:
        # Send invalid message (missing required fields like schemaVersion)
        invalid_msg = {
            "type": "start",
            "payload": {}
        }
        await ws.send(json.dumps(invalid_msg))
        
        # Client should receive an error reply
        error_str = await asyncio.wait_for(ws.recv(), timeout=2.0)
        error_msg = json.loads(error_str)
        assert error_msg["type"] == "error"
        assert error_msg["payload"]["code"] == "PROTOCOL_ERROR"
        assert "Schema violation" in error_msg["payload"]["error"]
        
        # Server's on_message should not have been called
        assert len(received_msgs) == 0

@pytest.mark.asyncio
async def test_schema_validation_accepts_valid(ws_server):
    uri = f"ws://127.0.0.1:{ws_server.port}"
    
    received_msgs = []
    def on_msg(m): received_msgs.append(m)
    ws_server.on_message = on_msg
    
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
        
        # Give server time to process
        await asyncio.sleep(0.1)
        assert len(received_msgs) == 1
        assert received_msgs[0]["type"] == "start"

@pytest.mark.asyncio
async def test_reconnect_resilience(ws_server):
    uri = f"ws://127.0.0.1:{ws_server.port}"
    
    # First connection
    async with websockets.connect(uri) as ws1:
        assert len(ws_server.clients) == 1
        
    # Give server time to clean up disconnected client
    await asyncio.sleep(0.1)
    # Server might not clean up until it tries to send, but let's test it by broadcasting
    ws_server.broadcast({"type": "heartbeat", "payload": {}})
    await asyncio.sleep(0.1)
    
    assert len(ws_server.clients) == 0
    
    # Reconnect
    async with websockets.connect(uri) as ws2:
        assert len(ws_server.clients) == 1
        ws_server.broadcast({
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
