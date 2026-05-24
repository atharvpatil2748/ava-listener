import json
import logging
import queue
import threading
from typing import Any, Dict
from runtime.telemetry.schema import TelemetryEvent

log = logging.getLogger("telemetry_events")

class TelemetryDispatcher:
    def __init__(self):
        self._queue = queue.Queue(maxsize=1000)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True, name="telemetry-worker")
        self.dropped_count = 0
        
    def start(self):
        self._stop_event.clear()
        if not self._thread.is_alive():
            self._thread.start()
            
    def stop(self):
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)
            
    def _worker(self):
        while not self._stop_event.is_set():
            try:
                event = self._queue.get(timeout=0.1)
                log.info(json.dumps(event.to_dict()))
            except queue.Empty:
                continue
            except Exception as e:
                log.error("Telemetry worker error: %s", e)
                
    def emit(self, correlation_id: str, subsystem: str, event_type: str, payload: Dict[str, Any]):
        event = TelemetryEvent(
            correlation_id=correlation_id,
            subsystem=subsystem,
            event_type=event_type,
            payload=payload
        )
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(event)
                self.dropped_count += 1
            except Exception:
                pass

_dispatcher = TelemetryDispatcher()

def get_telemetry_drop_count() -> int:
    return _dispatcher.dropped_count

def start_telemetry_worker():
    _dispatcher.start()

def stop_telemetry_worker():
    _dispatcher.stop()

def emit_structured_event(
    correlation_id: str,
    subsystem: str,
    event_type: str,
    payload: Dict[str, Any]
) -> None:
    _dispatcher.emit(correlation_id, subsystem, event_type, payload)
