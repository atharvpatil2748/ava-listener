from typing import Dict, Any

class HealthReport:
    def __init__(self, metrics_collector):
        self._metrics = metrics_collector
        
    def generate_report(self) -> Dict[str, Any]:
        """
        Compute a health score (0.0 to 1.0) and detailed breakdown
        based on active telemetry.
        """
        score = 1.0
        warnings = []
        
        metrics = self._metrics.get_all_metrics()
        
        # Penalty for worker resets (max 0.3 penalty)
        reset_penalty = min(metrics.get("reset_count", 0) * 0.05, 0.3)
        if reset_penalty > 0:
            score -= reset_penalty
            warnings.append(f"Reset penalty applied: {reset_penalty:.2f}")

        # Penalty for queue depth (max 0.2 penalty)
        queue_penalty = min(metrics.get("queue_depth", 0) / 1000.0, 0.2)
        if queue_penalty > 0.05:
            score -= queue_penalty
            warnings.append(f"Queue depth penalty applied: {queue_penalty:.2f}")

        # Penalty for engine restarts / watchdog faults (max 0.3 penalty)
        restart_penalty = min(metrics.get("restart_count", 0) * 0.1, 0.3)
        if restart_penalty > 0:
            score -= restart_penalty
            warnings.append(f"Restart penalty applied: {restart_penalty:.2f}")
            
        # Memory pressure (max 0.2 penalty)
        mem_mb = metrics.get("memory_usage_mb") or 0.0
        mem_pressure = min((mem_mb / 1024.0) * 0.1, 0.2)
        if mem_pressure > 0.05:
            score -= mem_pressure
            warnings.append(f"Memory pressure penalty applied: {mem_pressure:.2f}")
            
        # Ensure score is bound between 0.0 and 1.0
        score = max(0.0, min(1.0, score))
        
        return {
            "health_score": score,
            "status": "HEALTHY" if score > 0.8 else ("DEGRADED" if score > 0.5 else "CRITICAL"),
            "warnings": warnings,
            "metrics_snapshot": metrics
        }
