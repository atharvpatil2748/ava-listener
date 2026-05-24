# Compatibility wrapper — all runtime code imports get_logger from here.
# The real logger implementation lives in runtime/telemetry/logging.py.
# Phase 5 logging infrastructure (runtime/logging/) is additive, not replacing this.
import sys
from runtime.telemetry.logging import *  # noqa: F401,F403 — intentional re-export
