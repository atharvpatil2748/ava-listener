import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict

@dataclass
class TelemetryEvent:
    schema_version: int = 1
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = ""
    subsystem: str = ""
    event_type: str = ""
    timestamp_ns: int = field(default_factory=time.time_ns)
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
