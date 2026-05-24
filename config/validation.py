# Compatibility wrapper (Phase 1 Modularization)
import sys
from runtime.config.validation import *
import runtime.config.validation as _impl
for name in dir(_impl):
    if not name.startswith('__'):
        globals()[name] = getattr(_impl, name)
