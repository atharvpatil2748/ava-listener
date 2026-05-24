# Compatibility wrapper (Phase 1 Modularization)
import sys
from runtime.transport.stream.handler import *
import runtime.transport.stream.handler as _impl
for name in dir(_impl):
    if not name.startswith('__'):
        globals()[name] = getattr(_impl, name)
