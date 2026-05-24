# Migration Notes

## Intent

This document tracks migration steps from the prior Phase 8 startup flow to the new zero-setup bootstrap architecture.

## Migration actions

- Add dedicated implementation docs under `docs/implementation/`.
- Add `node/runtime_manager.js` and `node/model_manager.js` as runtime bootstrap wrappers.
- Keep existing Python runtime files unchanged.
- Add `bootstrap.lock` to protect concurrent startup.
- Define user cache structure and metadata files for runtime state.
- Remove model download actions from package install.

## Compatibility notes

- Existing local `venv` startup remains a fallback path.
- Existing runtime supervisor and worker startup behavior is preserved.
- New bootstrap infrastructure wraps the old runtime instead of rewriting it.
