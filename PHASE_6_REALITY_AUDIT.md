# Phase 6 — Reality Audit (Supervisor Architecture)

Phase-6 Completion: 40%

This file is a strict, evidence-based audit of the codebase against the
Phase 6 / Supervisor Architecture requirements (no new code was added).

Summary verdict: PARTIAL — core supervisor scaffold exists and basic
restart/backoff is implemented, but the IPC architecture and several
escalation actions are not wired or remain placeholders; stdout/stdin
transport is still the active path.

---

## 1) Worker isolation

Requirement: runtime worker must run in a separate process; VAD/ASR/candidate
tracking/audio must be owned by the worker; supervisor must survive worker
termination.

- Worker runs in a separate subprocess when supervised: [PARTIAL]
  Evidence:
  - Supervisor spawns a worker subprocess via `subprocess.Popen`:
    [ava-listener/runtime/supervisor/supervisor.py](ava-listener/runtime/supervisor/supervisor.py#L77-L90)
  - `main.py` exposes supervised mode (runtime can be launched as Supervisor):
    [ava-listener/main.py](main.py#L68-L76)
  Notes: functionality is implemented, but supervised mode is opt-in (`--mode supervised`)
  and the Node SDK is not yet updated to prefer supervised launches (see TODOs in
  `PHASE_6_CHECKPOINT.md`). This means a separate-process worker is available
  but not enforced by the surrounding launch tooling → PARTIAL.

- VAD, ASR, candidate tracking, audio ownership inside worker: [PASS]
  Evidence:
  - The supervised worker entrypoint instantiates the engine and starts it in
    the worker process: [ava-listener/runtime/worker/worker_process.py](runtime/worker/worker_process.py#L36-L41)
  - The engine (`WakeEngine`) owns runtime subsystems; because `WakeEngine`
    is created inside the worker entrypoint, those subsystems run in the
    worker process when supervised.

- Supervisor survives worker termination (restarts): [PASS]
  Evidence:
  - Supervisor monitors child exit (`poll()`), records recovery step, and
    spawns a replacement via `_spawn_worker()`: [ava-listener/runtime/supervisor/supervisor.py](ava-listener/runtime/supervisor/supervisor.py#L112-L119)
  - Supervisor uses a restart throttle (`RestartPolicy`) in `_handle_worker_exit`: [ava-listener/runtime/supervisor/supervisor.py](ava-listener/runtime/supervisor/supervisor.py#L200-L208)


## 2) Communication path

Requirement: define and verify Supervisor ↔ Worker ↔ Node SDK communication
paths; remove stdout/stdin as the primary transport and use IPC.

- Listing active communication paths (current state):
  - Node SDK ↔ Supervisor: stdout/stdin JSON (legacy; still active). Evidence:
    - `runtime/transport/stream/handler.py` is the stdout bridge that writes
      JSON lines intended for Node: [ava-listener/runtime/transport/stream/handler.py](runtime/transport/stream/handler.py#L1-L8)
    - Supervisor forwards worker stdout JSON lines to its own stdout in
      `_reader_loop_stdout()`: [ava-listener/runtime/supervisor/supervisor.py](runtime/supervisor/supervisor.py#L112-L122)

  - Supervisor ↔ Worker: subprocess pipes (stdin/stdout) are used by Supervisor
    to talk to the worker (Supervisor reads worker stdout and proxies worker stdin).
    Evidence: Supervisor spawns worker with `stdin=PIPE, stdout=PIPE, stderr=PIPE`:
    [ava-listener/runtime/supervisor/supervisor.py](runtime/supervisor/supervisor.py#L83-L91)

  - Worker ↔ Supervisor planned IPC: TCP JSON IPC modules exist
    (`runtime/ipc/channel.py`, `runtime/ipc/protocol.py`, `runtime/ipc/messages.py`),
    but the IPC channel is NOT wired: [ava-listener/runtime/ipc/channel.py](runtime/ipc/channel.py#L1-L12)

- Legacy stdout/stdin forwarding still exists: [FAIL → compatibility path present]
  Evidence:
  - `emit_*` helpers write JSON to stdout: [ava-listener/runtime/transport/stream/handler.py](runtime/transport/stream/handler.py#L19-L23)
  - Supervisor reads worker stdout JSON and re-emits it: [ava-listener/runtime/supervisor/supervisor.py](runtime/supervisor/supervisor.py#L112-L122)
  Conclusion: stdout/stdin is still the active communication path.

- Duplicate paths / compatibility shims detected: [PARTIAL]
  Evidence:
  - IPC modules were implemented, but Supervisor does not create an `IPCServer`,
    and the worker attempts to connect to an `IPCClient` (worker -> IPC client):
    - `runtime/ipc/channel.py` defines `IPCServer` and `IPCClient`.
    - `runtime/worker/worker_process.py` uses `IPCClient` but the Supervisor
      does not instantiate `IPCServer` → IPC is present but unused: [runtime/worker/worker_process.py](runtime/worker/worker_process.py#L7-L15)
  - Therefore there are two conceptual transports (stdout pipes and IPC sockets)
    but only the stdout path is functional at present.


## 3) Recovery policy (escalation & backoff)

Requirement: implement multi-step recovery with exponential backoff 1s→2s→4s→8s→16s
and escalation actions.

- Recovery escalation data & backoff sequence present: [PASS]
  Evidence:
  - `RecoveryPolicy` defines escalation steps and backoff sequence: [ava-listener/runtime/supervisor/restart_policy.py](runtime/supervisor/restart_policy.py#L20-L36)
  - Backoff sequence is 1000,2000,4000,8000,16000 ms: [ava-listener/runtime/supervisor/restart_policy.py](runtime/supervisor/restart_policy.py#L38-L48)

- Supervisor uses the recovery policy and waits backoff before actions: [PASS]
  Evidence:
  - On worker exit Supervisor records failure, computes step and backoff, emits a `recovery_step` event, sleeps the requested backoff, and maps step → action: [ava-listener/runtime/supervisor/supervisor.py](runtime/supervisor/supervisor.py#L132-L164)

- Restart throttling implemented: [PASS]
  Evidence:
  - `RestartPolicy` tracks timestamps and enforces `max_restarts` within a window; Supervisor checks `can_restart()` in `_handle_worker_exit`: [ava-listener/runtime/supervisor/restart_policy.py](runtime/supervisor/restart_policy.py#L1-L18)
  - `_handle_worker_exit()` uses `restart_policy.can_restart()` before spawning: [ava-listener/runtime/supervisor/supervisor.py](runtime/supervisor/supervisor.py#L200-L208)

- Escalation action implementation completeness: [PARTIAL → placeholders exist]
  Evidence / notes:
  - Supervisor maps higher-level steps to actions, but `provider_reload` and `runtime_restart`
    are currently implemented as placeholders that call the worker restart logic
    (no provider hot-reload or full runtime restart orchestration yet):
    [ava-listener/runtime/supervisor/supervisor.py](runtime/supervisor/supervisor.py#L150-L159)
  - `degraded_mode` sets an internal flag and stops automatic restarts as a placeholder: [ava-listener/runtime/supervisor/supervisor.py](runtime/supervisor/supervisor.py#L160-L166)
  - `fatal` stops restarting entirely (emits `worker_fatal`) — implemented.


## 4) Heartbeat / liveness

Requirement: Supervisor must detect heartbeat loss and recover.

- Heartbeat monitoring mechanism: [PARTIAL]
  Evidence:
  - Supervisor updates `_last_heartbeat` when it parses worker stdout JSON `event == "heartbeat"`: [ava-listener/runtime/supervisor/supervisor.py](runtime/supervisor/supervisor.py#L118-L122)
  - The engine's existing stdout heartbeat emitter (`start_heartbeat`) writes heartbeat JSON to stdout: [ava-listener/runtime/transport/stream/handler.py](runtime/transport/stream/handler.py#L73-L91)
  - The newly added worker IPC heartbeat (in `runtime/worker/worker_process.py`) sends HEARTBEAT messages via the `IPCClient`, but Supervisor has not been wired to accept IPC heartbeats (no `IPCServer` present in Supervisor) → the worker IPC heartbeat is currently unused: [runtime/worker/worker_process.py](runtime/worker/worker_process.py#L8-L16)
  Conclusion: heartbeat/liveness via stdout is functional; heartbeat via the new IPC path is not wired → PARTIAL.


## 5) Architecture enforcement checks

Run static checks/searches for known forbidden patterns and ownership violations.

- Direct stdout transport usage: [FAIL]
  Evidence: stdout bridge remains and is still the only module that writes to stdout: [ava-listener/runtime/transport/stream/handler.py](runtime/transport/stream/handler.py#L1-L8)

- Hidden singleton state / module-level globals: [PARTIAL]
  Evidence: module-level `_heartbeat_thread` sentinel exists by design in `runtime/transport/stream/handler.py` to make the heartbeat idempotent. A broader automated detection of hidden singletons is inconclusive; manual review recommended for critical modules.

- Direct process spawning outside Supervisor: [PASS]
  Evidence: within `runtime/` the only direct `subprocess.Popen` usage is inside `runtime/supervisor/supervisor.py` (no unexpected process spawns): search results show subprocess usage localized to supervisor.

- Hardcoded assistant names in `runtime/`: [PARTIAL]
  Evidence: there are commented examples and references to `arvsal` in `runtime/config/defaults.py` and `runtime/matcher/registry/phrase_registry.py`, but they are commented-out example data (not active constants):
  - [ava-listener/runtime/config/defaults.py](runtime/config/defaults.py#L120-L128)
  - [ava-listener/runtime/matcher/registry/phrase_registry.py](runtime/matcher/registry/phrase_registry.py#L48-L52)
  Action: remove commented assistant examples or move them to `profiles/` to avoid confusion; currently not active but present.

- Ownership violations / forbidden imports: [PASS]
  Evidence: key matcher modules have comments indicating they no longer import `WAKEWORDS` and phrase config was migrated to registry. Grep shows references are commented/in migration notes (no active forbidden imports found): e.g. `runtime/matcher/evaluator.py` documents the change.


## 6) Migration table (old → new → status)

- stdin/stdout transport
  → `runtime/transport/stream/handler.py` (stdout bridge)
  → STATUS: still active (not migrated) — **not migrated**

- direct runtime bootstrap (single-process)
  → `main.py --mode=direct` (default)
  → STATUS: still supported; `--mode=supervised` added but not mandated — **partial**

- worker ownership (VAD/ASR/audio/matcher)
  → `runtime/worker/worker_process.py` → `WakeEngine` instantiates subsystems
  → STATUS: **migrated** when supervised mode is used; otherwise direct mode keeps them in the same process — **partial**

- restart handling
  → `runtime/supervisor/restart_policy.py` + `runtime/supervisor/supervisor.py`
  → STATUS: restart throttling and escalation/backoff implemented — **partial** (escalation actions are placeholders)

- heartbeat handling
  → stdout heartbeat (`runtime/transport/stream/handler.py`) and IPC heartbeat (`runtime/worker/worker_process.py`)
  → STATUS: stdout heartbeat remains functional; IPC heartbeat present but not wired — **partial**


## Remaining blockers (actionable)

- Wire Supervisor ↔ Worker IPC: Supervisor must instantiate `IPCServer` and accept `HEARTBEAT`, `STATUS`, `WAKE`, `ERROR`, `DIAGNOSTICS` messages, and stop relying on stdout as primary transport.
- Route engine emitters (`emit_wake`, `emit_error`, `emit_diagnostics`) to IPC instead of stdout; deprecate stdout bridge.
- Implement real provider reload and runtime restart handlers (not just placeholders) as documented in Phase 6.
- Update Node SDK/process manager to spawn `main.py --mode supervised` by default for production use.
- Add integration tests confirming: worker crash recovery, restart throttling, heartbeat failure recovery, supervisor survival. Run `scripts/verify_startup.py`, `scripts/wake_regression.py`, and `scripts/check_architecture.py --strict` and fix issues they report.
- Remove or relocate commented assistant examples from `runtime/config/defaults.py` into `profiles/` to avoid accidental violation of the Generic Engine Identity rule.


## Ready for promotion: NO

Rationale: The supervisor scaffold, restart policy, and worker entrypoint are implemented, but the Phase 6 Definition of Done requires the IPC architecture to be primary (not stdout), full wiring of WAKE/ERROR/DIAGNOSTICS over IPC, and concrete escalation handlers beyond placeholders. Those items remain incomplete and block promotion.


---

All evidence above is strictly derived from repository files. No runtime assumptions were made and no new code was added during this audit.
