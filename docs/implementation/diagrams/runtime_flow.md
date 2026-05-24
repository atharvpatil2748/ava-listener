```mermaid
flowchart TD
    A[AVAListener.start()] --> S[Read bootstrap_state.json]
    S --> B[RuntimeManager.verify_runtime()]
    B --> C{runtime available?}
    C -- yes --> D[ModelManager.verify_models()]
    C -- no --> E[RuntimeManager.install_runtime()]
    E --> D
    D --> F{models valid?}
    F -- yes --> G[spawn supervisor]
    F -- no --> H[ModelManager.download_model()]
    H --> G
    G --> I[handshake]
    I --> J[runtime-ready]
```