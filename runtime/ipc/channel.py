"""Simple TCP-based IPC channel. Supervisor acts as server; worker connects as client."""

import socket
import threading
import time
from typing import Callable, Optional

from .protocol import recv_json, send_json
from utils.logger import get_logger

log = get_logger("ipc")


class IPCServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.host = host
        self.port = port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((host, port))
        self._sock.listen(1)
        self.port = self._sock.getsockname()[1]
        self._client_sock: Optional[socket.socket] = None
        self._client_addr = None
        self._recv_thread: Optional[threading.Thread] = None
        self._on_receive: Optional[Callable[[dict], None]] = None
        self._stop = False

    def accept_async(self, on_receive: Callable[[dict], None]) -> None:
        self._on_receive = on_receive
        self._recv_thread = threading.Thread(target=self._accept_loop, daemon=True, name="ipc-accept")
        self._recv_thread.start()

    def _accept_loop(self) -> None:
        while not self._stop:
            try:
                self._client_sock, self._client_addr = self._sock.accept()
                # read loop
                while not self._stop:
                    obj = recv_json(self._client_sock)
                    if obj is None:
                        # EOF/disconnect
                        break
                    log.debug("IPC receive: %s", obj)
                    if self._on_receive:
                        try:
                            self._on_receive(obj)
                        except Exception:
                            pass
            except Exception:
                time.sleep(0.1)

    def send(self, obj: dict) -> bool:
        if not self._client_sock:
            return False
        log.debug("IPC send: %s", obj)
        return send_json(self._client_sock, obj)

    def close(self) -> None:
        self._stop = True
        try:
            if self._client_sock:
                self._client_sock.close()
        except Exception:
            pass
        try:
            self._sock.close()
        except Exception:
            pass


class IPCClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.host = host
        self.port = port
        self._sock: Optional[socket.socket] = None
        self._on_receive: Optional[Callable[[dict], None]] = None
        self._stop_recv = False
        self._recv_thread: Optional[threading.Thread] = None

    def start_receiving(self, on_receive: Callable[[dict], None]) -> None:
        if not self._sock:
            return
        self._on_receive = on_receive
        self._stop_recv = False
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True, name="ipc-client-recv")
        self._recv_thread.start()

    def _recv_loop(self) -> None:
        from .protocol import recv_json
        while not getattr(self, "_stop_recv", False) and self._sock:
            try:
                obj = recv_json(self._sock)
                if obj is None:
                    break
                log.debug("IPC client receive: %s", obj)
                if getattr(self, "_on_receive", None):
                    try:
                        self._on_receive(obj)
                    except Exception as e:
                        log.error("IPC receive callback error: %s", e)
            except Exception:
                time.sleep(0.1)

    def connect(self, timeout_s: float = 10.0) -> bool:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((self.host, self.port))
                self._sock = sock
                return True
            except Exception:
                time.sleep(0.1)
        return False

    def send(self, obj: dict) -> bool:
        if not self._sock:
            return False
        log.debug("IPC send: %s", obj)
        return send_json(self._sock, obj)

    def close(self) -> None:
        self._stop_recv = True
        try:
            if self._sock:
                self._sock.close()
        except Exception:
            pass


__all__ = ["IPCServer", "IPCClient"]
