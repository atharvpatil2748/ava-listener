# Compatibility wrapper (Phase 1 Modularization)
import sys
from runtime.config.schema import *
import runtime.config.schema as _impl
for name in dir(_impl):
    if not name.startswith('__'):
        globals()[name] = getattr(_impl, name)
