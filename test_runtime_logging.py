from core.engine import WakeEngine

engine = WakeEngine()

engine.enable_debug("matcher")
engine.set_log_level("DEBUG")

print("Runtime log update successful")