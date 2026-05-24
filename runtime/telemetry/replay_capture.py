import json
import os
import time
from collections import deque
from typing import Dict, Any

class ReplayCapture:
    def __init__(self, output_dir: str = "logs/replay", max_events: int = 10000):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.max_events = max_events
        
    def start_capture(self, correlation_id: str):
        self.active_sessions[correlation_id] = {
            "correlation_id": correlation_id,
            "start_timestamp_ns": time.time_ns(),
            "hypotheses": deque(maxlen=self.max_events),
            "matcher_outputs": deque(maxlen=self.max_events),
            "state_transitions": deque(maxlen=self.max_events)
        }
        
    def record_hypothesis(self, correlation_id: str, text: str, stability: int):
        if correlation_id in self.active_sessions:
            self.active_sessions[correlation_id]["hypotheses"].append({
                "timestamp_ns": time.time_ns(),
                "text": text,
                "stability": stability
            })
            
    def record_matcher_output(self, correlation_id: str, phrase: str, confidence: float):
        if correlation_id in self.active_sessions:
            self.active_sessions[correlation_id]["matcher_outputs"].append({
                "timestamp_ns": time.time_ns(),
                "phrase": phrase,
                "confidence": confidence
            })
            
    def record_transition(self, correlation_id: str, from_state: str, to_state: str):
        if correlation_id in self.active_sessions:
            self.active_sessions[correlation_id]["state_transitions"].append({
                "timestamp_ns": time.time_ns(),
                "from": from_state,
                "to": to_state
            })
            
    def flush(self, correlation_id: str) -> str:
        """Manually flush a session to disk."""
        if correlation_id in self.active_sessions:
            session_data = self.active_sessions[correlation_id]
            session_data["end_timestamp_ns"] = time.time_ns()
            # Convert deques to lists for JSON serialization
            export_data = {
                "correlation_id": session_data["correlation_id"],
                "start_timestamp_ns": session_data["start_timestamp_ns"],
                "end_timestamp_ns": session_data["end_timestamp_ns"],
                "hypotheses": list(session_data["hypotheses"]),
                "matcher_outputs": list(session_data["matcher_outputs"]),
                "state_transitions": list(session_data["state_transitions"])
            }
            filename = os.path.join(self.output_dir, f"replay_{correlation_id}.json")
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)
            return filename
        return ""
        
    def shutdown(self):
        """Flush all active sessions on shutdown."""
        for cid in list(self.active_sessions.keys()):
            self.flush(cid)
