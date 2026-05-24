# Phase 6 Audit Notes

This audit records gaps remaining for Phase 6 to meet the Definition of Done.

Missing or partial items:

1. Worker isolation
   - Worker process entrypoint exists, but full decoupling of all runtime subsystems to the worker boundary must be verified.

2. IPC architecture
   - TCP JSON IPC implemented, but engine emitters (wake, error, diagnostics) are not yet routed over IPC.
   - stdout forwarding is still active as a compatibility path; must be deprecated in favor of IPC.

3. Recovery escalation policy
   - `RecoveryPolicy` exists and supervisor honours escalation steps; step actions beyond restarting the worker (provider reload, runtime restart, degraded mode) are currently placeholders.

4. Fallback bootstrap path
   - `main.py` supports `--mode supervised` and `--mode direct` (default).

5. Validation and tests
   - `scripts/verify_startup.py` and regression scripts should be executed; automated unit/integration tests need to be added.

Action items to close Phase 6:
- Wire engine event emitters to IPC channel so WAKE/ERROR/DIAGNOSTICS flow via IPC.
- Implement provider reload and runtime restart handlers.
- Add and run supervised-mode integration tests (worker crash recovery, restart throttling, supervisor survival).
- Update Node SDK to prefer supervised mode for production launches.
