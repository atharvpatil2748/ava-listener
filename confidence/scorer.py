# Compatibility wrapper (Phase 1 Modularization)
import sys
from runtime.matcher.scorers.phonetic import *
import runtime.matcher.scorers.phonetic as _impl
for name in dir(_impl):
    if not name.startswith('__'):
        globals()[name] = getattr(_impl, name)
