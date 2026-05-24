import time
import copy
from typing import Any, Dict

class DiagnosticsAPI:
    def __init__(self, engine):
        self._engine = engine
        self._start_time = time.time()
        
    def get_runtime_snapshot(self) -> Dict[str, Any]:
        """
        Return a complete diagnostic snapshot of the runtime.
        """
        uptime = time.time() - self._start_time
        
        # Subsystem states
        subsystems = {
            "Matcher": self._engine._matcher_fsm.state.value,
            "Transport": self._engine._transport_fsm.state.value,
        }
        
        # ASR subsystem is inside streamer
        if hasattr(self._engine, "_streamer"):
            streamer = self._engine._streamer
            subsystems["ASR"] = streamer._asr_fsm.state.value if hasattr(streamer, "_asr_fsm") else "UNKNOWN"
            subsystems["Audio"] = streamer._audio_fsm.state.value if hasattr(streamer, "_audio_fsm") else "UNKNOWN"
            if hasattr(streamer, "_vad") and hasattr(streamer._vad, "_vad_fsm"):
                subsystems["VAD"] = streamer._vad._vad_fsm.state.value
                
        # Metrics
        metrics = {}
        if hasattr(self._engine, "metrics_collector"):
            metrics = self._engine.metrics_collector.get_all_metrics()
            
        current_state = self._engine._state_machine.state.value
        
        # Profile
        active_profile = ""
        if hasattr(self._engine, "_runtime_params"):
            active_profile = self._engine._runtime_params.get("profile_path", "")
            
        snapshot = {
            "uptime_seconds": uptime,
            "current_state": current_state,
            "subsystem_states": subsystems,
            "metrics": metrics,
            "active_profile": active_profile,
            "queue_status": metrics.get("queue_depth", 0)
        }
        
        return copy.deepcopy(snapshot)
