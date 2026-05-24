"""WebSocket server for Phase 7."""

import asyncio
import json
import logging
import time
import uuid
import websockets
import logging
from typing import Callable, Any, Optional, Dict, List
from utils.logger import get_logger

from .protocol.validator import MessageValidator, ProtocolError

log = get_logger("ws_server")

GUARANTEED = {"wake", "fatal_error"}
RETRY = {"speech_start", "speech_end", "error"}
BEST_EFFORT = {"partial_transcript", "hypothesis_update"}
FIRE_AND_FORGET = {"telemetry", "debug"}

class WSServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.host = host
        self.port = port
        self.server = None
        self.clients = set()
        self.validator = MessageValidator()
        self.on_message: Optional[Callable[[dict], None]] = None
        self.loop = None
        self._thread = None
        self._stop_event = None
        
        # Reliability State
        self.offline_queue = [] # List of msg dicts
        self.pending_acks: Dict[str, dict] = {} # corr_id -> {"msg": dict, "class": str, "retries": int, "next_retry": float}
        self.best_effort_batch = []

    async def _handler(self, websocket):
        self.clients.add(websocket)
        log.info("WS Client connected")
        
        # Flush offline queue on reconnect
        if self.offline_queue:
            log.info(f"Flushing {len(self.offline_queue)} offline messages")
            for msg in list(self.offline_queue):
                await self._send_to_clients(msg)
            self.offline_queue.clear()
            
        try:
            async for message in websocket:
                try:
                    # Validate payload before runtime logic
                    valid_msg = self.validator.validate_message(message)
                    msg_type = valid_msg.get("type")
                    
                    if msg_type == "ack":
                        ack_id = valid_msg.get("payload", {}).get("correlationId")
                        if ack_id in self.pending_acks:
                            del self.pending_acks[ack_id]
                        continue

                    if self.on_message:
                        self.on_message(valid_msg)
                except ProtocolError as e:
                    # Reject malformed payloads
                    log.warning(f"WS protocol error: {e}")
                    error_reply = {
                        "type": "error",
                        "schemaVersion": 1,
                        "timestamp": time.time(),
                        "sessionId": "",
                        "correlationId": "",
                        "payload": {"error": str(e), "code": "PROTOCOL_ERROR"}
                    }
                    await websocket.send(json.dumps(error_reply))
                except Exception as e:
                    log.exception("WS handler unexpected error")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
            log.info("WS Client disconnected")

    async def _serve(self, stop_event: asyncio.Event):
        async with websockets.serve(self._handler, self.host, self.port) as server:
            self.server = server
            self.port = server.sockets[0].getsockname()[1]
            log.info(f"WebSocket Server listening on ws://{self.host}:{self.port}")
            
            # Start background tasks
            batch_task = asyncio.create_task(self._batch_loop())
            retry_task = asyncio.create_task(self._retry_loop())
            
            await stop_event.wait()
            batch_task.cancel()
            retry_task.cancel()
            log.info("WebSocket Server shutting down")

    async def _batch_loop(self):
        while True:
            await asyncio.sleep(0.1)
            if self.best_effort_batch:
                batch_msg = {
                    "type": "batch",
                    "schemaVersion": 1,
                    "timestamp": time.time(),
                    "sessionId": "server",
                    "correlationId": str(uuid.uuid4()),
                    "payload": {"events": self.best_effort_batch}
                }
                self.best_effort_batch = []
                await self._send_to_clients(batch_msg)

    async def _retry_loop(self):
        while True:
            await asyncio.sleep(0.05)
            now = time.time()
            to_retry = []
            to_drop = []
            
            for corr_id, item in list(self.pending_acks.items()):
                if item["next_retry"] <= now:
                    if item["class"] == "retry":
                        item["retries"] += 1
                        if item["retries"] > 3:
                            to_drop.append(corr_id)
                        else:
                            # 100ms -> 200ms -> 400ms
                            backoff = 0.1 * (2 ** (item["retries"] - 1))
                            item["next_retry"] = now + backoff
                            to_retry.append(item["msg"])
                    elif item["class"] == "guaranteed":
                        # retry until ACK. Just retry every 500ms? Let's use 500ms fixed
                        item["next_retry"] = now + 0.5
                        to_retry.append(item["msg"])

            for corr_id in to_drop:
                del self.pending_acks[corr_id]
                
            if to_retry:
                if not self.clients:
                    # Offline! Move to offline queue
                    for msg in to_retry:
                        if msg["correlationId"] in self.pending_acks:
                            del self.pending_acks[msg["correlationId"]]
                        self.offline_queue.append(msg)
                else:
                    for msg in to_retry:
                        await self._send_to_clients(msg)

    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self._stop_event = asyncio.Event()
        self.loop.run_until_complete(self._serve(self._stop_event))

    def start_in_thread(self):
        import threading
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="ws-server")
        self._thread.start()
        time.sleep(0.1)

    def stop(self):
        if self.loop and self._stop_event:
            self.loop.call_soon_threadsafe(self._stop_event.set)
        if self._thread:
            self._thread.join(timeout=2)

    async def _send_to_clients(self, msg: dict):
        if not self.clients:
            return
        msg_str = json.dumps(msg)
        disconnected = set()
        for ws in self.clients:
            try:
                await ws.send(msg_str)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(ws)
        for ws in disconnected:
            self.clients.discard(ws)

    def broadcast(self, message_obj: dict):
        if not self.loop:
            return
            
        out_msg = {
            "type": message_obj.get("type", "unknown"),
            "schemaVersion": message_obj.get("schemaVersion", 1),
            "timestamp": message_obj.get("timestamp", time.time()),
            "sessionId": message_obj.get("sessionId", "server"),
            "correlationId": message_obj.get("correlationId", str(uuid.uuid4())),
            "payload": message_obj.get("payload", message_obj)
        }
        
        for k in ["type", "schemaVersion", "timestamp", "sessionId", "correlationId"]:
            if k in message_obj:
                out_msg[k] = message_obj[k]

        msg_type = out_msg["type"]
        corr_id = out_msg["correlationId"]

        if msg_type in BEST_EFFORT:
            def _add_to_batch():
                self.best_effort_batch.append(out_msg)
                if len(self.best_effort_batch) >= 10:
                    batch_msg = {
                        "type": "batch",
                        "schemaVersion": 1,
                        "timestamp": time.time(),
                        "sessionId": "server",
                        "correlationId": str(uuid.uuid4()),
                        "payload": {"events": self.best_effort_batch}
                    }
                    self.best_effort_batch = []
                    asyncio.create_task(self._send_to_clients(batch_msg))
            self.loop.call_soon_threadsafe(_add_to_batch)
            return

        def _handle_send():
            if msg_type in GUARANTEED:
                if not self.clients:
                    self.offline_queue.append(out_msg)
                    return
                self.pending_acks[corr_id] = {"msg": out_msg, "class": "guaranteed", "retries": 0, "next_retry": time.time() + 0.5}
            elif msg_type in RETRY:
                if not self.clients:
                    self.offline_queue.append(out_msg)
                    return
                # First retry is after 100ms
                self.pending_acks[corr_id] = {"msg": out_msg, "class": "retry", "retries": 0, "next_retry": time.time() + 0.1}
            
            # FIRE_AND_FORGET or others just send
            if self.clients:
                asyncio.create_task(self._send_to_clients(out_msg))

        self.loop.call_soon_threadsafe(_handle_send)
