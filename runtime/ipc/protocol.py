"""JSON-over-TCP IPC protocol helpers."""

import json
import socket
from typing import Optional


def recv_json(sock: socket.socket) -> Optional[dict]:
    try:
        data = sock.recv(65536)
        if not data:
            return None
        # Assume newline-delimited JSON frames or single JSON blob
        text = data.decode("utf-8", errors="replace").strip()
        try:
            return json.loads(text)
        except Exception:
            # Try split lines
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    return json.loads(line)
                except Exception:
                    continue
            return None
    except Exception:
        return None


def send_json(sock: socket.socket, obj: dict) -> bool:
    try:
        payload = json.dumps(obj, separators=(",", ":")) + "\n"
        sock.sendall(payload.encode("utf-8"))
        return True
    except Exception:
        return False


__all__ = ["recv_json", "send_json"]
