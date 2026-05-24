import os
import shutil
import glob
from pathlib import Path

# Mapping of old path -> new path (relative to ava-listener root)
MAPPING = {
    "utils/logger.py": "runtime/logging/logger.py",
    "audio/mic.py": "runtime/audio/stream.py",
    "audio/buffer.py": "runtime/audio/realtime/ring_buffer.py",
    "audio/vad.py": "runtime/vad/pipeline.py",
    "asr/sherpa_stream.py": "runtime/asr/streaming.py",
    "confidence/scorer.py": "runtime/matcher/scorers/phonetic.py",
    "detection/matcher.py": "runtime/matcher/evaluator.py",
    "detection/variants.py": "runtime/matcher/variants.py",
    "decision/cooldown.py": "runtime/matcher/cooldown.py",
    "core/engine.py": "runtime/kernel/orchestrator.py",
    "config/settings.py": "runtime/config/defaults.py",
    "config/schema.py": "runtime/config/schema.py",
    "config/validation.py": "runtime/config/validation.py",
    "telemetry/collector.py": "runtime/telemetry/collector.py",
    "integration/stdout_bridge.py": "runtime/transport/stream/handler.py",
    "runtime/state_machine.py": "runtime/kernel/lifecycle.py",
    "runtime/watchdog.py": "runtime/supervisor/watchdog.py",
}

STUBS = [
    "runtime/supervisor/supervisor.py",
    "runtime/supervisor/restart_policy.py",
    "runtime/supervisor/health_monitor.py",
    "runtime/supervisor/heartbeat.py",
    "runtime/kernel/dispatcher.py",
    "runtime/kernel/runtime_state.py",
    "runtime/kernel/startup.py",
    "runtime/kernel/shutdown.py",
    "runtime/pipeline/linear.py",
    "runtime/session/manager.py",
    "runtime/session/context.py",
    "runtime/events/bus.py",
    "runtime/events/emitter.py",
    "runtime/events/priority.py",
    "runtime/events/types.py",
    "runtime/transport/websocket_server.py",
    "runtime/transport/control/handler.py",
    "runtime/transport/control/messages.py",
    "runtime/transport/stream/messages.py",
    "runtime/audio/backends/portaudio.py",
    "runtime/audio/backends/base.py",
    "runtime/vad/providers/base.py",
    "runtime/vad/providers/silero.py",
    "runtime/vad/providers/webrtc.py",
    "runtime/asr/providers/base.py",
    "runtime/asr/providers/sherpa.py",
    "runtime/matcher/engine.py",
    "runtime/matcher/ema.py",
    "runtime/matcher/scorers/base.py",
    "runtime/matcher/scorers/fuzzy.py",
    "runtime/models/registry.py",
    "runtime/models/verifier.py",
    "runtime/models/cache.py",
    "runtime/config/loader.py",
    "runtime/config/versioning.py",
    "runtime/resources/pools.py",
    "runtime/resources/budget.py",
    "runtime/resources/cleanup.py",
    "runtime/security/enforcer.py",
    "runtime/security/tokens.py",
    "runtime/security/validator.py",
    "runtime/security/limits.py",
    "runtime/health/scorer.py",
    "runtime/health/signals.py",
    "runtime/health/reporter.py",
    "runtime/manifest/manifest.py",
    "runtime/logging/context.py",
    "runtime/logging/formatters.py",
    "runtime/logging/sinks.py",
    "runtime/timing/clock.py",
    "runtime/timing/latency.py",
    "runtime/debug/crash_snapshot.py",
]

def ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    init_file = os.path.join(os.path.dirname(path), "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, "w") as f:
            f.write("")

def modularize(base_dir):
    print("Moving files to new runtime structure...")
    for old_rel, new_rel in MAPPING.items():
        old_path = os.path.join(base_dir, old_rel)
        new_path = os.path.join(base_dir, new_rel)
        
        if not os.path.exists(old_path):
            print(f"Skipping {old_path}, not found.")
            continue
            
        ensure_dir(new_path)
        shutil.move(old_path, new_path)
        print(f"Moved {old_rel} -> {new_rel}")
        
        # Create compatibility wrapper in the old location
        module_path = new_rel.replace("/", ".").replace(".py", "")
        with open(old_path, "w", encoding="utf-8") as f:
            f.write(f"# Compatibility wrapper (Phase 1 Modularization)\n")
            f.write(f"from {module_path} import *\n")
            
    print("\nCreating stubs for Tier 1 and Tier 2 components...")
    for stub_rel in STUBS:
        stub_path = os.path.join(base_dir, stub_rel)
        if not os.path.exists(stub_path):
            ensure_dir(stub_path)
            with open(stub_path, "w", encoding="utf-8") as f:
                f.write('"""Stub file created during Phase 1 Modularization."""\n')

if __name__ == "__main__":
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    modularize(base)
    print("\nModularization complete.")
