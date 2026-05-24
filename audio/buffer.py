# Compatibility wrapper (Phase 1 Modularization)
import sys
from runtime.audio.realtime.ring_buffer import *
import runtime.audio.realtime.ring_buffer as _impl
for name in dir(_impl):
    if not name.startswith('__'):
        globals()[name] = getattr(_impl, name)
