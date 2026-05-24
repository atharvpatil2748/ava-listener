"""
AVAListener — Configuration Schema
===============================
Defines the current schema version and supported config options.
"""

SCHEMA_VERSION = "1.0"

LOG_LEVELS = ["silent", "error", "warn", "info", "debug", "trace"]

DEFAULT_CONFIG = {
    "schema_version": SCHEMA_VERSION,
    "log_level": "info",
    "debug": {
        "vad": False,
        "asr": False,
        "matcher": False,
        "transport": False,
        "telemetry": False,
    },
    "metrics_to_disk": False,
    "metrics_file_path": "runtime_metrics.json",
}

PHRASE_PRIORITY_MODES = ["longest", "score", "canonical"]
