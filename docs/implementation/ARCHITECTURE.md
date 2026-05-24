# Architecture

## Goals

- Provide a zero-setup runtime packaging path for AVAListener.
- Preserve existing runtime behavior exactly.
- Keep worker, supervisor, ASR, VAD, wake engine, and runtime logic unchanged.
- Wrap the existing runtime with a bootstrapper, runtime manager, and model manager.

## High-level components

- `node/` — Node SDK and bootstrap orchestration.
- `runtime/` — existing Python runtime, supervisor, and worker logic.
- `models/` — model metadata and manifest definitions.
- `profiles/` — consumer profile definitions.
- `docs/implementation/` — versioned architecture and rollout documentation.

## New architecture elements

- `node/runtime_manager.js` — user cache discovery, runtime verification, installation, repair.
- `node/model_manager.js` — model manifest loading, verification, download, retry, checksum validation.
- `node/bootstrap.js` — CLI entrypoint for package layout validation and startup orchestration.
- `bootstrap.lock` — startup bootstrap lock file to prevent concurrent installs.

## Cache layout

User cache root per platform:

- Windows: `%LOCALAPPDATA%/AVAListener/`
- Linux: `~/.local/share/avalistener/`
- macOS: `~/Library/Application Support/AVAListener/`

Cache root structure:

```
AVAListener/
├── runtime/
├── models/
├── manifests/
├── logs/
├── temp/
└── metadata/
```

Metadata files:

- `metadata/runtime_state.json`
- `metadata/installed_models.json`
- `metadata/checksums.json`
- `metadata/bootstrap_state.json`

`runtime_state.json` fields:

- `runtimeVersion`
- `minimumSDKVersion`
- `maximumSDKVersion`
- `installedAt`
- `health`

`installed_models.json` fields:

- `id`
- `installedVersion`
- `latestVersion`
- `status`

`bootstrap_state.json` fields:

- `phase`
- `status`
- `lastCompletedStep`
- `timestamp`

Template examples are available in `docs/implementation/metadata_templates/`.

## Runtime install sources

RuntimeManager will support configuration-driven runtime sources.
Priority order:

1. GitHub release artifact
2. Mirror URL
3. Local fallback

Runtime sources are declared in `node/runtime_sources.json`.
Model manifest schema is defined in `models/manifests/manifest.schema.json`.
