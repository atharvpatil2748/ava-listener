# Compatibility wrapper (Phase 1 Modularization)
import sys
from runtime.audio.stream import *
import runtime.audio.stream as _impl
for name in dir(_impl):
    if not name.startswith('__'):
        globals()[name] = getattr(_impl, name)
