# Phase 2 Checkpoint: Subsystem Tracking & State Machines

## 1. Exact Replay Baseline Inventory

**Replay fixtures:**
- **original_phase0**: 19
- **phase0_5_additions**: 4
- **total**: 23

**Added Fixtures and Rationale:**
- `listen alone`: Added to verify that a solitary sub-phrase like "listen" will correctly trigger its own registered wake match independent of the longer variant.
- `listen arv candidate only`: Added to verify that incomplete multi-word phrases (e.g. "listen arv") properly remain as tracking candidates without prematurely executing as full triggers.
- `listen arvsal full`: Added to verify that multi-word overlaps trigger accurately when fully matched.
- `wake alone`: Added to ensure standalone ambiguous prefixes like "wake" do not inadvertently trigger "wake up arvsal" unless explicitly authorized.

## 2. Regression Contract

For all future phases (Phase 3 through 8):
- **Cannot modify existing fixtures.** Phase 0 and Phase 0.5 tests represent the engine’s permanent source of truth for base wake conditions.
- **Cannot alter expected outputs.** Existing outputs mapped in `tests/replay/test_replay.py` must never flip state.
- **May only append new fixtures.** If new core behaviors or profiles are added, they must be represented as net-new test additions.

## 3. Baseline Diff Validation
`scripts/check_baseline_integrity.py` has been established and actively gates regressions by verifying fixture totals, string labels, boolean trigger triggers, and mapped outcomes.

## 4. Subsystem Lifecycle States Verified
The new `SubsystemLifecycle` tracking seamlessly binds onto the active pipelines:
- Correct progression flow validated: `OFFLINE → INITIALIZING → READY → ACTIVE`
- Safe recovery paths proven valid: `ACTIVE → RECOVERING → ACTIVE` 
- Shutdown path: `ACTIVE → OFFLINE`
No illegal skips (such as `OFFLINE → ACTIVE` directly, or `ACTIVE → INITIALIZING`) exist within the live lifecycle loop.

## 5. Freeze Phase 2 APIs
The following core Phase 2 components are formally **frozen** and their signatures will not be broken during future phases:
- `SubsystemState`
- `SubsystemLifecycle`
- `listener.set_log_level(level)`
- `listener.enable_debug(subsystem)`
- `listener.disable_debug(subsystem)`
- `listener.enable_trace()`
- `listener.disable_trace()`

**Status**: Phase 2 fully validated. Proceeding to Phase 3.
