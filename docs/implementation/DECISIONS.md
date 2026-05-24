# Decisions

## Implementation planning as code artifacts

Decision: Implementation planning and architecture tracking must live in repository documents, not in chat responses.

Rationale:
- version control captures design changes
- documentation becomes reviewable and auditable
- team members can inspect architecture without reading chat transcripts

Tradeoff:
- requires discipline to keep docs synchronized with code

## Bootstrap lock file

Decision: Add `bootstrap.lock` to prevent concurrent startup bootstrap operations.

Rationale:
- protects runtime install and model download flows from corruption
- enforces single-install semantics on first startup

## Cache-based runtime distribution

Decision: Use a user-local cache instead of packaging an embedded Python runtime with npm.

Rationale:
- avoids large package payloads
- supports fresh-machine bootstrap without bundling platform-specific Python
- allows runtime repair without modifying package contents

## Model downloads during runtime startup only

Decision: Model downloads may only occur during `listener.start()`.

Rationale:

## 2026-05-23 — Implementation updates

- Integrated runtime bootstrap using `RuntimeManager` and `BootstrapLock` into `Lifecycle.start()`.
- Implemented `ModelManager` for manifest-driven model verification and downloads with checksum validation.
- Finalized Phase 9 packaging flow with multi-tier fallbacks, dynamic zip/tar extraction, and dependencies verification.

## Platform-specific runtime distribution
Decision: Structure the runtime payload into platform-specific asset zips (windows-x64, linux-x64, linux-arm64, macos-x64, macos-arm64) via `runtime_sources.json` and `platform_manifest.json`.
Rationale:
- Allows the installer to dynamically select the correct runtime artifact based on the host OS architecture without bloating the npm package.
- Enforces strict compatibility checks (`UnsupportedPlatformError`) before attempting any installation.
- Leverages `child_process` and `os` natively to avoid external dependencies like `unzipper` or `tar`.

## GitHub Release Asset Verification
Decision: Introduce a `ReleaseManager` backed by `release_manifest.json` to cryptographically verify runtime payloads via SHA-256 before extraction.
Rationale:
- Ensures security and integrity against MITM attacks or corrupted downloads.
- Maps `assetName` to exact Github URLs, abstracting away download complexity.
- Keeps release logic modular and testable outside of the core `RuntimeManager` bootstrap sequence.
- Employs strict, isolated error boundaries (`ReleaseManifestError`, `AssetResolutionError`) to gracefully reject malformed JSON, missing schemas, or unsupported mappings during the early initialization phase.

## npm Package Constraints
Decision: Enforce a strict `hardLimitMB` (100MB) via `package_constraints.json` and a rigid `.npmignore` strategy during `npm pack`.
Rationale:
- Prevents accidentally bundling heavy local artifacts (like `.venv` or massive `models/` checkpoints) into the published registry package.
- Offloads heavy static binaries to the `ReleaseManager` post-install phase rather than inflating the core npm module.

## CI/CD Strategy
Decision: Adopt a matrix-driven GitHub Actions pipeline targeting Ubuntu, Windows, and macOS alongside an internal `CIManager` telemetry generator.
Rationale:
- Validates the cross-platform assertions embedded in `RuntimeManager` and `ReleaseManager` dynamically on real virtualized host environments.
- Extracts JSON-based success metrics (`ci_report.json`) to programmatically verify stability before authorizing production releases.
