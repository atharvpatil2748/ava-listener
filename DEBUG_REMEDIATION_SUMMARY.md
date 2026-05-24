# Debug Mode Logic Remediation & Audit

## 1. Audit of `transcription.enableDebug` and `DEBUG_TRANSCRIPT_PARTIAL`
I conducted a thorough audit to investigate your hypothesis that `transcription.enableDebug` was acting as a functional gate for hypothesis emission. 
- **Findings**: `transcription.enableDebug` properly translates into `DEBUG_TRANSCRIPT_PARTIAL` and `DEBUG_TRANSCRIPT_FINAL` flags via the runtime telemetry toggles. However, `DEBUG_TRANSCRIPT_PARTIAL` is used **exclusively** for `log.debug()` and `log.trace()` statements in `runtime/audio/worker.py`. 
- **Conclusion**: The flag does **not** introduce any logic branches that prevent partial hypotheses from reaching the engine. The ASR decoding path and hypothesis emission logic via `on_hypothesis()` execute identically regardless of whether debug mode is enabled or disabled. The missing partial transcripts in `debug: false` were merely filtered out by the logger (by design), but they were successfully passed to the engine.

## 2. Root Cause: `DEBUG_VAD_BYPASS`
During the audit, I discovered that the true violation of the "observability-only" requirement was the `DEBUG_VAD_BYPASS` flag in `defaults.py`.
- **Issue**: It was hardcoded to `True` globally. This forcefully disabled VAD gating and funneled 100% of audio chunks to the Sherpa ASR model (`effective_speech = True`). This coupled a debug setting directly with core signal processing paths, which heavily altered the latency, resource usage, and endpointing behavior of the runtime.
- **Resolution**: I completely removed `DEBUG_VAD_BYPASS` from `defaults.py`, `worker.py`, and `pipeline.py`. 
- **Outcome**: The VAD logic now strictly dictates `effective_speech = self._is_speaking` in **both** production and debug modes. This ensures functional parity; `debug: true` now strictly only affects logging visibility (metrics, trace, and debug levels) without mutating the pipeline behavior.

## 3. Test Suite Remediation (Phase 0.5 Alignment)
When running `scripts/wake_regression.py` after the fixes, the suite failed due to `PhraseRegistry` yielding `0/0 phrases`.
- **Issue**: The Phase 0.5 refactor shifted phrase parsing away from `config.settings` and into `PhraseRegistry`, but `tests/test_pipeline.py` and `tests/replay/test_replay.py` only called `load_profile()` and didn't actually populate the registry or rebuild the variant index. Additionally, the orchestrator itself was missing the `rebuild_index()` call after registering loaded phrases.
- **Resolution**: 
  - Restored `PhraseRegistry` iteration in the test suites: `registry.add_phrase(PhraseConfig.from_dict(...))`.
  - Added `from detection.variants import rebuild_index` and `rebuild_index()` calls to `orchestrator.py`, `test_pipeline.py`, and `test_replay.py` to ensure the memory maps are appropriately structured for fuzzy matching.
- **Outcome**: The wake regression suite now passes successfully (**127/127** checks).
