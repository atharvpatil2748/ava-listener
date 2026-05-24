# Phase 6 — Supervisor Architecture Checkpoint

Status: In progress — supervisor scaffold implemented; additional artifacts pending.

Required items:

- [x] Supervisor process implemented: `runtime/supervisor/supervisor.py`
- [x] Restart throttling implemented: `runtime/supervisor/restart_policy.py` (`RestartPolicy`)
- [x] Recovery escalation policy added: `RecoveryPolicy` in `restart_policy.py` (steps + backoff)
- [x] Worker process entrypoint created: `runtime/worker/worker_process.py`
- [x] IPC channel/protocol/message stubs added: `runtime/ipc/{channel,protocol,messages}.py`
- [ ] IPC wiring integrated as primary transport (supervisor ↔ worker)
- [ ] Tests: worker crash recovery, restart throttling, supervisor survival
- [ ] Update Node SDK to spawn `main.py --mode supervised` for supervised launches
- [ ] Documentation and implementation map

Notes:
- Current supervisor implements escalation placeholders: provider reload and runtime restart map to worker restart for now.
- IPC is implemented as a simple TCP JSON channel; worker sends HEARTBEAT messages.
- No full replacement of stdout-based event forwarding has been completed yet; it's retained for compatibility.
