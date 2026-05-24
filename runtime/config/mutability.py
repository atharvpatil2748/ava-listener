class RestartRequiredError(Exception):
    def __init__(self, message, code="RESTART_REQUIRED"):
        super().__init__(message)
        self.code = code

HOT_RELOAD_FIELDS = frozenset([
    "vad.sileroThreshold",
    "vad.aggressiveness",
    "confidence.defaultThreshold",
    "confidence.emaRiseAlpha",
    "confidence.emaDecayAlpha",
    "confidence.cooldownSeconds",
    "transcription.enableDebug"
])

RESTART_REQUIRED_FIELDS = frozenset([
    "asr.provider",
    "asr.modelPath",
    "asr.numThreads",
    "audio.sampleRate",
    "audio.blockSize"
])

def check_mutability(field_path: str, runtime_active: bool):
    """
    Raises RestartRequiredError if the field requires restart and runtime is active.
    Defaults to RESTART_REQUIRED if field not in HOT_RELOAD_FIELDS.
    """
    if not runtime_active:
        return
        
    if field_path in HOT_RELOAD_FIELDS:
        return
        
    # By default, anything not explicitly hot reloadable requires a restart
    raise RestartRequiredError(f"Modifying field '{field_path}' requires a restart.")
