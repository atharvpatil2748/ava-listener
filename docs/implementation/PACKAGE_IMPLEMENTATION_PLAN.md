# Package Implementation Plan

This directory contains all project-level implementation planning artifacts for the AVAListener runtime packaging work.

## Purpose

- Keep architecture decisions in versioned repository files.
- Avoid large planning text inside chat responses.
- Track progress through a single source of truth.
- Document migration steps, diagrams, and rollout strategy.

## Contents

- `ARCHITECTURE.md` — architecture definition and component boundaries.
- `STARTUP_FLOW.md` — startup and bootstrap sequence.
- `MIGRATION_NOTES.md` — migration strategy and compatibility notes.
- `PHASE_TRACKER.md` — source of truth for progress and phase status.
- `DECISIONS.md` — documented rationale and tradeoffs.
- `CHANGELOG.md` — implementation-level change history.
- `diagrams/` — reference diagrams in markdown.

## Rules

1. New architecture or bootstrap changes must update these docs.
2. `PHASE_TRACKER.md` is the single source of truth for project progress.
3. `DECISIONS.md` records rationale, not opinion.
4. `CHANGELOG.md` records meaningful implementation changes.
5. Diagrams should use Mermaid or plain ASCII.
