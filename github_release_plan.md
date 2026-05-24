# GitHub Release Plan: v0.1.0

## Repository Structure Validation
The repository has been fully audited. All source code, benchmarks, and configuration files have been categorized correctly. Artifacts and temporary files have been strictly separated and flagged for ignore mechanisms.

## GitHub Release Checklist
- [ ] Ensure `.github/workflows/ci.yml` matrix (Node 18/20, Python 3.10/3.11, Ubuntu/Mac/Windows) runs and passes completely on the `main` branch.
- [ ] Draft a new Release on GitHub.
- [ ] Select tag: `v0.1.0`.
- [ ] Target branch: `main`.
- [ ] Release Title: `AVA-Listener v0.1.0 - Phase 11 Optimization Completion`.
- [ ] Body: Insert the contents of `RELEASE_NOTES_v0.1.0.md` into the release description.
- [ ] Publish Release.

## Tag Strategy
- **Format**: Semantic Versioning (`vMAJOR.MINOR.PATCH`).
- **Initial Tag**: `v0.1.0` pointing to the exact commit closing out Phase 12.

## Branch Strategy
- **`main`**: The highly stable, optimized production source of truth. Direct commits are restricted.
- **`feature/*`**: Used for developing future functionalities (e.g., Phase 13 plugin interfaces).
- **`bugfix/*`**: Used for patching the Phase 11 baseline.
- **Pull Requests**: Must pass the `.github/PULL_REQUEST_TEMPLATE.md` checklist and provide explicit startup benchmark validations.

## Package Publish Strategy
The package is prepared with a clean `.npmignore` to exclude CI artifacts, tests, and baselines from the distributed tarball.
The publish sequence requires passing the test suite and checking the tarball footprint:
```bash
npm ci
npm pack --dry-run
npm publish --access public
```

## Future Release Workflow
With the GitHub CI pipeline established, future releases will automatically block PRs that cause regressions. Code changes must respect the official Phase 11 baseline:
- Warm start: 3770 ms
- Cold start: 19138 ms
- Worker spawn: 567.3 ms
- Worker ready: 2652.3 ms
If these metrics degrade, the patch will be flagged as a historical regression and prevented from entering `main` unless properly addressed.
