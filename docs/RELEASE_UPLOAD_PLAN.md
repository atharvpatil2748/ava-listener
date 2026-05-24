# AVA-Listener Release Upload Architecture

This document defines the final architecture for releasing `ava-listener` as both an open-source GitHub repository and a distributed npm package.

## 1. Payload Separation Architecture

A core principle of this release is that **GitHub and npm serve different purposes**. The GitHub repository must support active development, testing, and documentation, while the npm package must be as lightweight as possible, containing *only* what is necessary for runtime execution.

### A) GitHub Repository Payload
The following directories and files are to be tracked in Git and pushed to GitHub:

* **Runtime Code:** `node/`, `runtime/`, `asr/`, `audio/`, `confidence/`, `config/`, `core/`, `decision/`, `detection/`, `integration/`, `telemetry/`, `utils/`, `profiles/`
* **Development & QA:** `tests/`, `benchmarks/`, `scripts/`, `examples/`
* **Documentation & Community:** `docs/`, `README.md`, `CHANGELOG.md`, `CODE_OF_CONDUCT.md` (recommended), `SECURITY.md` (recommended)
* **Configuration:** `.github/`, `.gitignore`, `.npmignore`, `package.json`, `package-lock.json`, `requirements.txt`, `LICENSE`
* **SDK:** `sdk/` (Included in GitHub mono-repo for development)

### B) npm Package Payload
The following files are strictly required for the package to execute when installed via `npm install ava-listener`. All other files will be ignored to save space and reduce install time.

* **Node Wrapper:** `node/`
* **Python Engine:** `runtime/`, `asr/`, `audio/`, `confidence/`, `config/`, `core/`, `decision/`, `detection/`, `integration/`, `telemetry/`, `utils/`
* **Configurations:** `profiles/`
* **Root Metadata:** `package.json`, `package-lock.json`, `requirements.txt`, `README.md`, `LICENSE`, `CHANGELOG.md`

*(Note: `tests/`, `benchmarks/`, `.github/`, `examples/`, `docs/`, `scripts/`, and `sdk/` are omitted from the npm tarball).*

## 2. SDK Handling & Justification

**Classification:** Independent Package Candidate (Category C)

**Justification:** 
By inspecting `sdk/package.json` and tracing imports:
*   **Imported by runtime?** No. The Python runtime engine does not import or depend on the SDK.
*   **Imported by node entry points?** No. The core server (`node/index.js`, `node/supervisor.js`) does not import the SDK. The SDK is only used in tests.
*   **Required by users?** No. End-users installing `ava-listener` simply run the daemon. Developers building applications *on top* of the daemon will use the SDK.
*   **Future monorepo candidate?** Yes. The `sdk/` folder should be kept in the GitHub repository as part of a monorepo setup (e.g., using NPM Workspaces), but it should be excluded from the `ava-listener` npm package payload and published independently (e.g., `@ava-listener/client`).

## 3. Package Size Estimates

Calculations based on current tree size, strictly excluding large AI models, temporary caches (`__pycache__`, `node_modules`, `venv`), and generated test artifacts.

*   **GitHub Repository Size:** ~2.60 MB
    *(Includes the entire suite of 100+ tests, historical benchmark JSONs, documentation diagrams, and development scripts).*
*   **npm Package Size:** ~0.48 MB
    *(A highly optimized tarball containing only the pure Node.js and Python source scripts).*

## 4. Professional Repository Recommendations

During the audit, standard community health files were found to be missing. To present a professional open-source front, the following files must be created before public launch:

*   **`CODE_OF_CONDUCT.md`:** Essential for defining community standards for contributors. Recommend using the Contributor Covenant standard.
*   **`SECURITY.md`:** Essential for providing instructions on how to privately report vulnerabilities instead of opening public GitHub issues.

## 5. Final Upload & Exclusion Table

| Path / Folder | GitHub | npm | Exclude | Reason |
| :--- | :--- | :--- | :--- | :--- |
| `node/`, `runtime/`, `asr/` etc. | Yes | Yes | No | Core execution logic. |
| `profiles/` | Yes | Yes | No | Required default profiles (`jarvis.json`, etc.). |
| `tests/`, `benchmarks/`, `scripts/`| Yes | No | Yes | Irrelevant for end-user runtime execution. |
| `docs/`, `examples/` | Yes | No | Yes | Consumes space; users can view on GitHub. |
| `.github/` | Yes | No | Yes | CI/CD actions are useless to npm consumers. |
| `sdk/` | Yes | No | Yes | Separate client; not an engine dependency. |
| `models/`, `*.onnx` | No | No | Yes | ~73MB binary files; handle via setup CLI. |
| `node_modules/`, `venv/` | No | No | Yes | Environment-specific dependencies. |
| `__pycache__`, `temp/`, `*.log` | No | No | Yes | Runtime caching and execution side-effects. |
| `*_REPORT.md`, `PHASE_*.md` | No | No | Yes | Internal dev scratching/audits. Clutter. |

## 6. Final Repository Structure Preview

```text
AVA-Listener/
├── node/
├── runtime/
├── docs/
├── .github/
├── README.md
├── LICENSE
├── CHANGELOG.md
├── CONTRIBUTING.md
├── ROADMAP.md
├── SECURITY.md
├── CODE_OF_CONDUCT.md
└── package.json
```

