import time
import os

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

class MetricsCollector:
    def __init__(self):
        self.wake_count = 0
        self.false_trigger_count = 0
        self.latency_ms_history = []
        self.queue_depth = 0
        self.reset_count = 0
        self.restart_count = 0
        self.audio_drop_count = 0
        
    def record_wake(self, latency_ms: float):
        self.wake_count += 1
        self.latency_ms_history.append(latency_ms)
        if len(self.latency_ms_history) > 1000:
            self.latency_ms_history.pop(0)
            
    def record_false_trigger(self):
        self.false_trigger_count += 1
        
    def record_reset(self):
        self.reset_count += 1
        
    def record_restart(self):
        self.restart_count += 1
        
    def record_audio_drop(self):
        self.audio_drop_count += 1
        
    def set_queue_depth(self, depth: int):
        self.queue_depth = depth

    @property
    def avg_latency_ms(self) -> float:
        if not self.latency_ms_history:
            return 0.0
        return sum(self.latency_ms_history) / len(self.latency_ms_history)
        
    def get_system_metrics(self):
        if not HAS_PSUTIL:
            return {"memory_usage_mb": None, "cpu_usage_percent": None}
            
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        return {
            "memory_usage_mb": mem_info.rss / 1024 / 1024,
            "cpu_usage_percent": process.cpu_percent()
        }

    def get_all_metrics(self):
        sys_metrics = self.get_system_metrics()
        from runtime.telemetry.events import get_telemetry_drop_count
        return {
            "wake_count": self.wake_count,
            "false_trigger_count": self.false_trigger_count,
            "avg_latency_ms": self.avg_latency_ms,
            "queue_depth": self.queue_depth,
            "reset_count": self.reset_count,
            "restart_count": self.restart_count,
            "audio_drop_count": self.audio_drop_count,
            "telemetry_drop_count": get_telemetry_drop_count(),
            "memory_usage_mb": sys_metrics["memory_usage_mb"],
            "cpu_usage_percent": sys_metrics["cpu_usage_percent"]
        }
