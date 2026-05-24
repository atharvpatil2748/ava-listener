import json
from jsonschema import validate, ValidationError
from .schemas import get_message_schema, CONTROL_TYPES, STREAM_TYPES

class ProtocolError(Exception):
    """Raised when a message violates the protocol schema."""
    pass

class MessageValidator:
    def __init__(self):
        self.envelope_schema = get_message_schema()
        self.allowed_types = CONTROL_TYPES | STREAM_TYPES

    def validate_message(self, message_str: str) -> dict:
        """
        Parses and validates a raw JSON string against the protocol.
        Raises ProtocolError if malformed or invalid.
        """
        try:
            msg = json.loads(message_str)
        except json.JSONDecodeError as e:
            raise ProtocolError(f"Invalid JSON: {str(e)}")

        try:
            validate(instance=msg, schema=self.envelope_schema)
        except ValidationError as e:
            raise ProtocolError(f"Schema violation: {e.message}")

        msg_type = msg.get("type")
        if msg_type not in self.allowed_types:
            raise ProtocolError(f"Unknown message type: '{msg_type}'")

        return msg
