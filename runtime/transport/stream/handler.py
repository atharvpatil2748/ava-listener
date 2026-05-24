"""
AVAListener — stdout Bridge
CRITICAL RULE: This is the ONLY module that writes to stdout.
All other modules must use utils/logger.py (→ stderr).

Wire protocol: one JSON object per line, always terminated with \n.
Node.js reads stdout line by line and parses each line as JSON.
"""
import sys
import json
import time
import threading
from config.settings import HEARTBEAT_INTERVAL_S


# ── Event emitters ────────────────────────────────────────────────────────────

def _emit(payload: dict) -> None:
    """Primary emitter: attempt IPC send, fallback to stdout.

    The IPC client is injected by the worker entrypoint as
    `runtime.ipc.channel._shared_client`. If present and connected we
    prefer IPC as the primary transport. Stdout remains as a deprecated
    compatibility fallback.
    """
    # Try IPC first (non-blocking). The worker runtime sets
    # runtime.ipc.channel._shared_client when it connects to Supervisor.
    try:
        import runtime.ipc.channel as _ipc_channel
        client = getattr(_ipc_channel, "_shared_client", None)
        if client:
            try:
                # Worker IPC messages follow the {"type": ..., "payload": {...}} shape
                # for Supervisor compatibility; wrap stdout payload under DIAGNOSTICS if needed.
                obj = payload.copy()
                # If already has 'event', map to IPC 'type' conventions
                t = obj.pop("event", None)
                if t:
                    ipc_type = t.upper()
                else:
                    ipc_type = "DIAGNOSTICS"
                send_ok = client.send({"type": ipc_type, "payload": obj})
                if send_ok:
                    return
            except Exception:
                # fall through to stdout fallback
                pass
    except Exception:
        pass

    # Stdout fallback (deprecated)
    line = json.dumps(payload, separators=(",", ":"))
    # Mark deprecated transport
    try:
        payload["deprecated_transport"] = "stdout"
    except Exception:
        pass
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def emit_wake(phrase: str, raw_confidence: float, smooth_confidence: float, latency_ms: float = 0.0) -> None:
    """Emit a wake detection event."""
    _emit({
        "event":             "wake",
        "phrase":            phrase,
        "raw_confidence":    round(raw_confidence, 3),
        "smooth_confidence": round(smooth_confidence, 3),
        "latency_ms":        round(latency_ms, 1),
        "ts":                time.time(),
    })


def emit_status(status: str, detail: str = "") -> None:
    """Emit a lifecycle status event (ready / stopped / error)."""
    _emit({
        "event":  "status",
        "status": status,
        "detail": detail,
        "ts":     time.time(),
    })


def emit_error(message: str) -> None:
    """Emit a recoverable error event."""
    _emit({
        "event":   "error",
        "message": message,
        "ts":      time.time(),
    })


# ── Heartbeat ─────────────────────────────────────────────────────────────────

# Module-level sentinel: the heartbeat thread is a process singleton.
# start_heartbeat() may be called on every engine.start() (e.g. across
# lifecycle test cycles), but only ONE heartbeat thread should ever exist.
# P6-FIX-2: added idempotency guard to prevent +N daemon threads per cycle.
_heartbeat_thread: threading.Thread | None = None


def start_heartbeat() -> None:
    """
    Start the heartbeat daemon thread (idempotent — safe to call multiple times).

    Only spawns a new thread if no alive heartbeat thread exists.
    Node.js uses this to detect silent crashes (if heartbeat stops → restart).
    Daemon=True means it dies automatically when the main thread exits.
    """
    global _heartbeat_thread

    # Guard: return immediately if already alive
    if _heartbeat_thread is not None and _heartbeat_thread.is_alive():
        return

    start_time = time.time()

    def _loop():
        while True:
            time.sleep(HEARTBEAT_INTERVAL_S)
            _emit({
                "event":    "heartbeat",
                "uptime_s": round(time.time() - start_time, 1),
                "ts":       time.time(),
            })

    _heartbeat_thread = threading.Thread(target=_loop, daemon=True, name="heartbeat")
    _heartbeat_thread.start()
