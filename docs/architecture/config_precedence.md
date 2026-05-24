# Configuration Precedence Contract

The AVAListener configuration system uses a layered architecture. When the runtime evaluates a configuration value, it resolves through multiple levels of precedence.

## Layers (Lowest to Highest Precedence)

1. **Defaults (`defaults.py`)**: Hardcoded safe baselines.
2. **Profile JSON**: The loaded profile after applying inheritance and migrations.
3. **Constructor Arguments**: Overrides passed during runtime initialization (`Supervisor` / `Worker`).
4. **`updateConfig()` Handler**: Updates sent by the Node SDK after boot.
5. **Runtime Overrides**: High-priority internal logic overrides (e.g., fallback actions).

## Mutability

Fields are either **Hot Reloadable** or **Restart Required**. 
Attempting to modify a Restart Required field while the runtime is active via `updateConfig` will throw a `RestartRequiredError`.

## Effective Config API

The effective config resolves all layers and tracks the origin of each field for diagnostic visibility.
Calling `listener.getEffectiveConfig()` returns an object showing the value and the layer that provided it.
