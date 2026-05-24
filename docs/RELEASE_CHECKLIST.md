# Release Readiness Checklist

This checklist must be fully validated prior to publishing a new release to GitHub or npm to ensure distribution hygiene.

## 1. Distribution Integrity
- [ ] **`npm pack` Verification:** Running `npm pack` completes successfully without bundling errors.
- [ ] **Package Size Verification:** Inspect the resulting `.tgz` archive. The unpacked size should be under `1.0 MB` (currently ~0.48 MB expected).
- [ ] **Clean Sandbox Install:** Running `npm install ./ava-listener-<version>.tgz` inside an empty temporary directory works without throwing layout errors.

## 2. Exclusion & Hygiene Verification
- [ ] **Model Exclusion:** Verify that `models/` and any `.onnx` files are excluded from the `.tgz` and from Git.
- [ ] **No Hardcoded Absolute Paths:** Run a global search to ensure `c:/Users/...` paths (like those previously found in `models_manifest.json`) are completely removed from configuration and manifest files.
- [ ] **No Caches Included:** Verify `__pycache__`, `node_modules`, `venv`, and `temp/` are absent from the `.tgz`.
- [ ] **No Temporary Scripts:** Ensure `test.js`, `test.json`, `test_runtime_logging.py`, `verification_outputs/`, and all local `*proposal.txt` files are absent from both GitHub and npm.

## 3. Workflow & Documentation Validation
- [ ] **Benchmark Validation:** The current baseline metrics in `benchmarks/BASELINE.md` accurately reflect the performance of the code being released.
- [ ] **Setup Command Validation:** `npx ava-listener setup` is documented as the sole method for acquiring AI models, and triggers successfully in the clean sandbox install.
- [ ] **Community Files:** Ensure `README.md`, `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, and `SECURITY.md` are up to date and present in the GitHub repository.
