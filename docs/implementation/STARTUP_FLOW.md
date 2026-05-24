# Startup Flow

## High-level sequence

1. `AVAListener.start()` is called.
2. Emit `bootstrap-start`.
3. Acquire `bootstrap.lock`.
4. Read `metadata/bootstrap_state.json`.
5. If safe, resume from `bootstrap_state.json`.
   - otherwise rollback to last stable state.
6. `RuntimeManager.verify_runtime()`.
7. `ModelManager.verify_models()`.
8. Download missing assets only during `start()`.
9. Emit `download-progress` events during install.
10. Launch supervisor via the selected Python runtime.
11. Perform handshake with runtime.
12. Emit `runtime-ready`.
13. Release `bootstrap.lock`.

## Bootstrap recovery

The bootstrap process must use `metadata/bootstrap_state.json` to track recovery.

Required fields:

- `phase` — current bootstrap phase name.
- `status` — `in-progress`, `completed`, or `failed`.
- `lastCompletedStep` — last successfully completed step.
- `timestamp` — ISO 8601 time of the last state update.

Startup behavior:

- Read `bootstrap_state.json` at the beginning of startup.
- If the previous run ended in `failed`, determine whether it is safe to resume.
- If resume is safe, continue from the next step.
- If resume is unsafe, rollback to the last stable checkpoint and restart bootstrap.

## Locking

Bootstrap locking prevents:

- concurrent startup installs
- duplicate runtime downloads
- model corruption

Lock state must be released on success or failure.

## Runtime selection priority

1. cached runtime from user cache
2. local project `venv`
3. verified system Python

System Python verification must check:

- version compatibility
- required dependencies
- architecture match

If no valid runtime is available, startup fails cleanly.
