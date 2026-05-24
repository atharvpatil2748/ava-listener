"""Worker process entrypoint for supervised mode."""

import argparse
import os
import threading
import time
import sys
from utils.logger import get_logger
from runtime.ipc.channel import IPCClient
from runtime.ipc.messages import HEARTBEAT, STATUS

log = get_logger("worker")


def _heartbeat_loop(ipc: IPCClient, interval_s: float = 5.0):
    while True:
        try:
            if not ipc.send({"type": HEARTBEAT, "payload": {"ts": time.time()}}):
                log.error("Supervisor IPC disconnected! Terminating worker to prevent zombie leak.")
                os._exit(1)
        except Exception:
            pass
        time.sleep(interval_s)


def run_worker(profile: str | None = None, ipc_host: str = "127.0.0.1", ipc_port: int = 0, debug: bool = False):
    # Start IPC client
    ipc = IPCClient(host=ipc_host, port=ipc_port)
    connected = ipc.connect(timeout_s=5.0)
    if connected:
        log.info("Connected to supervisor IPC %s:%s", ipc_host, ipc_port)
        ipc.send({"type": STATUS, "payload": {"status": "worker_starting", "ts": time.time()}})
        hb = threading.Thread(target=_heartbeat_loop, args=(ipc,), daemon=True, name="hb")
        hb.start()
        # Expose the connected IPC client to other modules (transport handler)
        try:
            import runtime.ipc.channel as _ipc_channel
            _ipc_channel._shared_client = ipc
        except Exception:
            pass
    else:
        log.warning("Could not connect to supervisor IPC at %s:%s — continuing without IPC", ipc_host, ipc_port)

    # Instantiate and start the engine just like main.py would
    try:
        from core.engine import WakeEngine
        engine = WakeEngine()
        if profile:
            engine.load_profile(profile, debug_overlay=debug)
        engine.start()
        # Block until engine stops
        while True:
            time.sleep(1.0)
    except Exception as exc:
        log.exception("Worker fatal error: %s", exc)
        try:
            if connected:
                ipc.send({"type": "ERROR", "payload": {"message": str(exc), "ts": time.time()}})
        except Exception:
            pass
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=str, help="Path to profile JSON")
    parser.add_argument("--ipc-host", type=str, default="127.0.0.1")
    parser.add_argument("--ipc-port", type=int, default=0)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    if args.debug:
        from utils.logger import enable_trace
        enable_trace()
    run_worker(profile=args.profile, ipc_host=args.ipc_host, ipc_port=args.ipc_port, debug=args.debug)


if __name__ == "__main__":
    main()
