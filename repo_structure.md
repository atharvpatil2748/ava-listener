# Repository Structure Audit

**Category A (Required for public repository)**
- `README.md`, `LICENSE`, `CHANGELOG.md`, `ROADMAP.md`, `CONTRIBUTING.md`, `RELEASE_NOTES_v0.1.0.md`
- `.github/` workflows and issue templates
- `node/` core JavaScript SDK and lifecycle managers
- `runtime/` (or `asr/`, `audio/`, `config/`, `core/`, `decision/`, `detection/`, `engine.py`) core Python inference logic
- `package.json`, `requirements.txt`
- Core documentation under `docs/`

**Category B (Required for package publishing)**
- `node/` core code
- Python core source code (`engine.py` and folders)
- `package.json`
- `requirements.txt`
- `README.md`
- `LICENSE`

**Category C (Required only for development/testing)**
- `tests/` Python test suite
- `node/tests/` Node benchmark and isolation test suite
- `benchmarks/` official baselines and regression tracking `.json` files (`history.json`, `manifest.json`, `final_phase11_report.json`, etc.)

**Category D (Generated artifacts - Excluded)**
- `.tgz` npm pack outputs (`ava-listener-0.1.0.tgz`)
- `.log` telemetry outputs
- `verification_outputs/` stream captures

**Category E (Local machine/cache/runtime files - Excluded)**
- `node_modules/`
- `.venv/`
- `__pycache__` and `*.pyc`
- `cache/` and `.ava_cache/`
- Downloaded `models/*.onnx`

**Category F (OS/IDE specific - Excluded)**
- `.DS_Store`
