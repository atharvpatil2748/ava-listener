# AVA-Listener Roadmap

## Current Phase
**Phase 12: Repository Hardening and Release Preparation**
- Freeze runtime benchmark performance
- Clean repository structure and remove internal debug artifacts
- Generate robust documentation
- Setup GitHub Actions CI/CD pipelines
- Release `v0.1.0`

## Upcoming Phases
**Phase 13: Dynamic Configuration Registry and Plugin API**
- Fully decouple assistant logic into a dynamic configuration profile.
- Replace hardcoded wakeword settings with dynamic, programmable configurations.
- Abstract the runtime to support generic Wake Word and ASR parameters.
- Provide a standard SDK plugin interface for developers.

**Phase 14: End-to-End Multimodal Extensibility**
- Expand event payload formats.
- Add support for multiple backends and custom acoustic models.
- Abstract input streams (e.g., streaming audio from network sources rather than local mic).
