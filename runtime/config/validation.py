"""
AVAListener — Configuration Validation
=====================================
Validate external config dicts against the runtime schema.
"""

from typing import Any
from config.schema import SCHEMA_VERSION, LOG_LEVELS, PHRASE_PRIORITY_MODES


def validate_config(config: dict[str, Any]) -> None:
    """Raise ValueError for invalid configuration."""
    if not isinstance(config, dict):
        raise ValueError("Config must be a dictionary")

    schema_version = config.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported schema_version {schema_version!r}; expected {SCHEMA_VERSION!r}"
        )

    log_level = config.get("log_level")
    if log_level not in LOG_LEVELS:
        raise ValueError(
            f"Invalid log_level {log_level!r}; expected one of {LOG_LEVELS}"
        )

    debug = config.get("debug")
    if not isinstance(debug, dict):
        raise ValueError("debug must be a mapping of subsystem booleans")
    for key in ["vad", "asr", "matcher", "transport", "telemetry"]:
        if key not in debug:
            raise ValueError(f"Missing debug subsystem toggle: {key}")
        if not isinstance(debug[key], bool):
            raise ValueError(f"debug.{key} must be a boolean")

    if not isinstance(config.get("metrics_to_disk"), bool):
        raise ValueError("metrics_to_disk must be a boolean")

    metrics_path = config.get("metrics_file_path")
    if not isinstance(metrics_path, str) or not metrics_path.strip():
        raise ValueError("metrics_file_path must be a non-empty string")

    phrase_priority = config.get("phrase_priority_mode")
    if phrase_priority is not None and phrase_priority not in PHRASE_PRIORITY_MODES:
        raise ValueError(
            f"Invalid phrase_priority_mode {phrase_priority!r}; expected one of {PHRASE_PRIORITY_MODES}"
        )
