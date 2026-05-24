# AVAListener — Smoke Tests (Phase 0)
# =====================================
# Fast startup-safety checks that must pass before ANY implementation phase begins.
# These tests run WITHOUT a microphone. They verify imports, config loading,
# model file presence, and matcher logic only.
#
# Usage (from ava-listener/):
#   python -m pytest tests/smoke/ -v
#   python tests/smoke/test_smoke.py
