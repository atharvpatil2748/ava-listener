# Changelog

## 2026-05-23

- Created `docs/implementation/` package and tracking artifacts.
- Added `bootstrap.lock` artifact.
- Added runtime manager and model manager skeleton files in `node/`.
- Added startup flow and architecture documentation.
- Added runtime sources configuration and model manifest schema artifacts.
- Added metadata templates for runtime state, installed models, checksums, and bootstrap state.
- Added bootstrap state recovery behavior to startup flow.
- Added migration notes and phase tracker entry.

- 2026-05-23 (implementation)
	- Implemented `ModelManager` with manifest loading, checksum verification, local `file://` and remote download support, retry logic, and metadata persistence.
	- Integrated `RuntimeManager` bootstrap into `Lifecycle.start()` with `BootstrapLock` acquisition, verify/install flow, and safe release.
	- Added `verifyOrDownload()` wiring for model verification after runtime readiness.
	- Finalized Phase 9 packaging with full fallback ordering, zip/tar extraction, HTTP downloads, and dependency checks.
	- Began Phase 10 (Cross-Platform Distribution) by implementing the OS/arch-specific runtime source resolution matrix (`runtime_sources.json`).
	- Completed Phase 10A: Added `platform_manifest.json` and strict architecture validation logic (`UnsupportedPlatformError`) to `RuntimeManager`.
	- Completed Phase 10B: Created `ReleaseManager` to handle GitHub release manifest resolution and dynamic runtime SHA256 checksum validation.
	- Completed Phase 10B Validation Gate: Enforced strict manifest error handling (`ReleaseManifestError`, `AssetResolutionError`) and exhaustive edge-case testing.
	- Completed Phase 10C (npm Package Validation): Created `PackageValidator` to enforce `.npmignore` constraints, strict size limits (50MB soft/100MB hard), and validate cold-cache install flows.
	- Completed Phase 10D (CI/CD): Authored `.github/workflows` for node tests, package constraints, and release validations. Created `CIManager` to generate `ci_report.json` analytics.
	- Fixed external installation bug by properly exporting `AVAListener` via `main`, `exports`, and `files` keys in `package.json`, and implemented `external_import_test.js` to prevent regressions.
