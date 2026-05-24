# Phase 6 Implementation Map

Mapping of required Phase 6 components to implemented files and TODOs.

- Supervisor process
  - Implemented: `runtime/supervisor/supervisor.py`
  - TODO: integrate richer IPC control and status APIs

- Worker process
  - Implemented: `runtime/worker/worker_process.py`, `runtime/worker/bootstrap.py`
  - TODO: route all runtime events (WAKE, ERROR, DIAGNOSTICS) over IPC

- IPC
  - Implemented: `runtime/ipc/channel.py`, `runtime/ipc/protocol.py`, `runtime/ipc/messages.py`
  - TODO: fully wire engine emitters to IPC

- Recovery policy
  - Implemented: `runtime/supervisor/restart_policy.py` (`RestartPolicy`, `RecoveryPolicy`)
  - TODO: implement provider reload & runtime restart handlers

- Bootstrap modes
  - Implemented: `main.py --mode=direct|supervised`
  - Default behavior unchanged (direct)

- Tests
  - TODO: add automated tests for recovery and supervisor survival

- Documentation
  - Added checkpoint and implementation map files under `ava-listener/`.
