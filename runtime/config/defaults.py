"""
AVAListener — Central Configuration (Phase 0.5)
================================================
All tunable audio, ASR, and matching parameters live here.
No magic numbers anywhere else.

Phase 0.5 change: WAKEWORDS, WAKE_PHRASES, and CONTEXT_WORDS have been
removed from this file. All phrase/variant/threshold data now lives in
profiles/*.json and enters the engine exclusively through the PhraseRegistry.

A commented-out rollback reference is preserved at the bottom of this file
per the Phase 0.5 rollback strategy.
"""
import os

# -- Paths -------------------------------------------------------------------
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(BASE_DIR, "models")

# -- ASR / Audio -------------------------------------------------------------
SAMPLE_RATE  = 16000
BLOCK_SIZE   = 1600   # 100ms chunks — optimal latency/stability balance
TRAILING_PAD_FRAMES = 2  # silent chunks fed to Sherpa after VAD gates off (200ms)
NUM_THREADS  = 2      # Sherpa ONNX inference threads

# Sherpa endpoint detection (seconds of silence before stream finalizes)
ENDPOINT_RULE1_SILENCE  = 0.6   # 600ms trailing silence to finalize (wakeword-tuned)
ENDPOINT_RULE2_SILENCE  = 1.2   # hard commit sooner
ENDPOINT_RULE3_UTTERANCE = 20.0  # max utterance length

# Silence reset: how many consecutive silent chunks before ASR stream resets
SILENCE_RESET_FRAMES = 30       # 30 x 100ms = 3s — extended so endpoint fires before reset

# -- VAD & Endpointing -------------------------------------------------------
VAD_AGGRESSIVENESS       = 1        # 0=least, 3=most aggressive
VAD_FRAME_SAMPLES        = 480      # 30ms at 16kHz (WebRTC max)
RMS_FLOOR                = 0.005    # Absolute minimum energy fallback
SILERO_THRESHOLD         = 0.15     # Reduced for calibration; tune upward later
DEBUG_VAD_BYPASS         = True     # If True, logs VAD stats but lets ALL audio reach ASR

# Adaptive noise floor and speech confirmation
NOISE_FLOOR_MULTIPLIER   = 1.8
NOISE_HISTORY_FRAMES     = 40       # ~4s of recent silence RMS values
MIN_SPEECH_FRAMES        = 3        # consecutive speech-positive frames before speech_start
MIN_SILENCE_FRAMES       = 8        # consecutive silence frames before speech_end
MIN_SPEECH_MS            = 250      # minimal acceptable speech segment
MIN_VALID_UTTERANCE_MS   = 600      # utterances shorter than this are treated as noise

# Smart reset / stream lifetime policy
RESET_COOLDOWN_SECONDS   = 15.0
IDLE_STREAM_TIMEOUT_S    = 60.0

# -- Matching ----------------------------------------------------------------
# Jaro-Winkler similarity threshold for anchor matching (0-1)
JARO_THRESHOLD = 0.82

# rapidfuzz token_set_ratio threshold (0-100)
FUZZY_THRESHOLD = 65

# -- Phrase Boundary Logic ---------------------------------------------------
REQUIRE_FULL_PHRASE = True
ALLOW_PREFIX_MATCHING = False

# -- Confidence --------------------------------------------------------------
# Default fallback threshold — used only when the registry is empty or
# a phrase has no explicit threshold set. Normally the registry provides
# per-phrase thresholds from the loaded profile.
DEFAULT_THRESHOLD    = 0.78
CONFIDENCE_THRESHOLD = DEFAULT_THRESHOLD   # backward-compat alias for scorer.py
WINDOW_SECONDS       = 3.5     # rolling hypothesis window width

# Weights inside compute_confidence()
WEIGHT_MATCH      = 0.65
WEIGHT_CONTEXT    = 0.20
WEIGHT_STABILITY  = 0.15

# EMA confidence smoothing (smoothed = alpha*raw + (1-alpha)*prev)
EMA_RISE_ALPHA   = 0.70
EMA_DECAY_ALPHA  = 0.30

# Stability saturation cap
STABILITY_CAP = 12

# -- Cooldown ----------------------------------------------------------------
COOLDOWN_SECONDS = 2.0   # hard block after any trigger (global fallback)

# -- Audio pipeline queue ----------------------------------------------------
AUDIO_QUEUE_MAX      = 20    # warn when queue > this (2s backlog)
WORKER_QUEUE_TIMEOUT = 1.0   # worker blocks this long on empty queue

# -- IPC / Bridge ------------------------------------------------------------
HEARTBEAT_INTERVAL_S = 5.0

# -- Phrase arbitration / runtime policy ------------------------------------
PHRASE_PRIORITY_MODE = "longest"  # longest / score / canonical

# -- Telemetry / production diagnostics -------------------------------------
METRICS_TO_DISK = False
METRICS_FILE_PATH = os.path.join(BASE_DIR, "runtime_metrics.json")

# -- Logging defaults -------------------------------------------------------
LOG_LEVEL = "info"
LOG_DEBUG_SUBSYSTEMS = {
    "vad": False,
    "asr": False,
    "matcher": False,
    "transport": False,
    "telemetry": False,
}

# -- ASR Transcript Logging -------------------------------------------------
DEBUG_TRANSCRIPTS = False
DEBUG_TRANSCRIPT_PARTIAL = False
DEBUG_TRANSCRIPT_FINAL = False


# ===========================================================================
# ROLLBACK REFERENCE — Phase 0.5
# ===========================================================================
# The WAKEWORDS, WAKE_PHRASES, and CONTEXT_WORDS constants were removed in
# Phase 0.5. They are preserved here as comments for rollback purposes only.
#
# To revert Phase 0.5: uncomment the block below and restore the imports
# in detection/matcher.py and detection/variants.py to read from this module.
#
# WAKEWORDS = [
#     {
#         "phrase":    "assistant",
#         "threshold": 0.72,
"""
AVAListener — Central Configuration (Phase 0.5)
================================================
All tunable audio, ASR, and matching parameters live here.
No magic numbers anywhere else.

Phase 0.5 change: WAKEWORDS, WAKE_PHRASES, and CONTEXT_WORDS have been
removed from this file. All phrase/variant/threshold data now lives in
profiles/*.json and enters the engine exclusively through the PhraseRegistry.

A commented-out rollback reference is preserved at the bottom of this file
per the Phase 0.5 rollback strategy.
"""
import os

import platform

# -- Paths -------------------------------------------------------------------
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _get_default_cache_dir():
    sys_plat = platform.system()
    if sys_plat == "Windows":
        return os.path.join(os.environ.get("LOCALAPPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Local")), "AVAListener")
    elif sys_plat == "Darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "AVAListener")
    else:
        return os.path.join(os.path.expanduser("~"), ".local", "share", "avalistener")

# Phase 9: Load models from global cache root propagated from Node.js, or fallback to identical native resolution
_CACHE_ROOT = os.environ.get("AVA_CACHE_DIR", _get_default_cache_dir())
MODELS_DIR  = os.path.join(_CACHE_ROOT, "models")

# -- ASR / Audio -------------------------------------------------------------
SAMPLE_RATE  = 16000
BLOCK_SIZE   = 1600   # 100ms chunks — optimal latency/stability balance
TRAILING_PAD_FRAMES = 2  # silent chunks fed to Sherpa after VAD gates off (200ms)
NUM_THREADS  = 2      # Sherpa ONNX inference threads

# Sherpa endpoint detection (seconds of silence before stream finalizes)
ENDPOINT_RULE1_SILENCE  = 0.6   # 600ms trailing silence to finalize (wakeword-tuned)
ENDPOINT_RULE2_SILENCE  = 1.2   # hard commit sooner
ENDPOINT_RULE3_UTTERANCE = 20.0  # max utterance length

# Silence reset: how many consecutive silent chunks before ASR stream resets
SILENCE_RESET_FRAMES = 30       # 30 x 100ms = 3s — extended so endpoint fires before reset

# -- VAD & Endpointing -------------------------------------------------------
VAD_AGGRESSIVENESS       = 1        # 0=least, 3=most aggressive
VAD_FRAME_SAMPLES        = 480      # 30ms at 16kHz (WebRTC max)
RMS_FLOOR                = 0.005    # Absolute minimum energy fallback
SILERO_THRESHOLD         = 0.15     # Reduced for calibration; tune upward later

# Adaptive noise floor and speech confirmation
NOISE_FLOOR_MULTIPLIER   = 1.8
NOISE_HISTORY_FRAMES     = 40       # ~4s of recent silence RMS values
MIN_SPEECH_FRAMES        = 3        # consecutive speech-positive frames before speech_start
MIN_SILENCE_FRAMES       = 8        # consecutive silence frames before speech_end
MIN_SPEECH_MS            = 250      # minimal acceptable speech segment
MIN_VALID_UTTERANCE_MS   = 600      # utterances shorter than this are treated as noise

# Smart reset / stream lifetime policy
RESET_COOLDOWN_SECONDS   = 15.0
IDLE_STREAM_TIMEOUT_S    = 60.0

# -- Matching ----------------------------------------------------------------
# Jaro-Winkler similarity threshold for anchor matching (0-1)
JARO_THRESHOLD = 0.82

# rapidfuzz token_set_ratio threshold (0-100)
FUZZY_THRESHOLD = 65

# -- Phrase Boundary Logic ---------------------------------------------------
REQUIRE_FULL_PHRASE = True
ALLOW_PREFIX_MATCHING = False

# -- Confidence --------------------------------------------------------------
# Default fallback threshold — used only when the registry is empty or
# a phrase has no explicit threshold set. Normally the registry provides
# per-phrase thresholds from the loaded profile.
DEFAULT_THRESHOLD    = 0.78
CONFIDENCE_THRESHOLD = DEFAULT_THRESHOLD   # backward-compat alias for scorer.py
WINDOW_SECONDS       = 3.5     # rolling hypothesis window width

# Weights inside compute_confidence()
WEIGHT_MATCH      = 0.65
WEIGHT_CONTEXT    = 0.20
WEIGHT_STABILITY  = 0.15

# EMA confidence smoothing (smoothed = alpha*raw + (1-alpha)*prev)
EMA_RISE_ALPHA   = 0.70
EMA_DECAY_ALPHA  = 0.30

# Stability saturation cap
STABILITY_CAP = 12

# -- Cooldown ----------------------------------------------------------------
COOLDOWN_SECONDS = 2.0   # hard block after any trigger (global fallback)

# -- Audio pipeline queue ----------------------------------------------------
AUDIO_QUEUE_MAX      = 20    # warn when queue > this (2s backlog)
WORKER_QUEUE_TIMEOUT = 1.0   # worker blocks this long on empty queue

# -- IPC / Bridge ------------------------------------------------------------
HEARTBEAT_INTERVAL_S = 5.0

# -- Phrase arbitration / runtime policy ------------------------------------
PHRASE_PRIORITY_MODE = "longest"  # longest / score / canonical

# -- Telemetry / production diagnostics -------------------------------------
METRICS_TO_DISK = False
METRICS_FILE_PATH = os.path.join(BASE_DIR, "runtime_metrics.json")

# -- Logging defaults -------------------------------------------------------
LOG_LEVEL = "info"
LOG_DEBUG_SUBSYSTEMS = {
    "vad": False,
    "asr": False,
    "matcher": False,
    "transport": False,
    "telemetry": False,
}

# -- ASR Transcript Logging -------------------------------------------------
DEBUG_TRANSCRIPTS = False
DEBUG_TRANSCRIPT_PARTIAL = False
DEBUG_TRANSCRIPT_FINAL = False



