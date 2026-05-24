"""
AVAListener — Phase 5 Observability Tests (revised for all P5-BLOCK fixes)
===========================================================================
Run:
    python tests/runtime/test_observability.py
"""
from __future__ import annotations
import sys, os, time, json, warnings

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from runtime.timing.clock import now_ns, now_s, monotonic, uptime_s
from runtime.timing.latency import LatencyTracker, RollingLatency, PIPELINE_STAGES, STAGE_INTERVALS
from runtime.logging.context import LogContext
from runtime.logging.formatters import StructuredFormatter
from runtime.logging.sinks import ConsoleSink, NullSink
from runtime.health.signals import HealthSignals, compute_signals, HEALTH_SIGNAL_MAP
from runtime.health.scorer import compute_health_score, score_from_metrics, SIGNAL_WEIGHTS
from runtime.telemetry.metrics import MetricsCollector

_passed = _failed = 0

def _assert(cond: bool, name: str, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        print(f"  PASS  {name}")
        _passed += 1
    else:
        print(f"  FAIL  {name}{': '+detail if detail else ''}")
        _failed += 1


# ── P5-BLOCK-001: Logging module ownership ─────────────────────────────────────

def test_logging_module_ownership():
    print("\nP5-BLOCK-001: Logging module ownership")
    # context.py: only LogContext, no StructuredFormatter
    import runtime.logging.context as ctx_mod
    _assert(hasattr(ctx_mod, "LogContext"), "context.py has LogContext")
    _assert(not hasattr(ctx_mod, "StructuredFormatter"), "context.py does NOT have StructuredFormatter")

    # formatters.py: only StructuredFormatter defined here
    import runtime.logging.formatters as fmt_mod
    _assert(hasattr(fmt_mod, "StructuredFormatter"), "formatters.py has StructuredFormatter")
    # LogContext may be imported but must not be *defined* in formatters.py
    fmt_lc = getattr(fmt_mod, "LogContext", None)
    _assert(
        fmt_lc is None or getattr(fmt_lc, "__module__", "") == "runtime.logging.context",
        "LogContext is not *defined* in formatters.py (only imported if present)",
    )

    # sinks.py: ConsoleSink, FileSink, NullSink
    import runtime.logging.sinks as sink_mod
    _assert(hasattr(sink_mod, "ConsoleSink"), "sinks.py has ConsoleSink")
    _assert(hasattr(sink_mod, "FileSink"), "sinks.py has FileSink")
    _assert(hasattr(sink_mod, "NullSink"), "sinks.py has NullSink")

    # logger.py: configure_runtime_logging, get_runtime_logger
    import runtime.logging.logger as log_mod
    _assert(hasattr(log_mod, "configure_runtime_logging"), "logger.py has configure_runtime_logging")
    _assert(hasattr(log_mod, "get_runtime_logger"), "logger.py has get_runtime_logger")


# ── P5-BLOCK-003: Explicit latency stages ─────────────────────────────────────

def test_explicit_pipeline_stages():
    print("\nP5-BLOCK-003: Explicit pipeline stages")
    required = {"capture_to_queue", "vad", "asr", "matcher", "wake_total"}
    _assert(required.issubset(set(PIPELINE_STAGES)), "All required stages present in PIPELINE_STAGES")

    # Correct stage usage
    lt = LatencyTracker("corr-stage-test")
    lt.mark("capture_to_queue")
    time.sleep(0.005)
    lt.mark("vad")
    time.sleep(0.003)
    lt.mark("asr")
    time.sleep(0.002)
    lt.mark("matcher")
    time.sleep(0.001)
    lt.mark("wake_total")

    result = lt.to_dict()
    _assert("capture_to_vad_ms" in result, "to_dict has capture_to_vad_ms")
    _assert("vad_to_asr_ms" in result, "to_dict has vad_to_asr_ms")
    _assert("asr_to_matcher_ms" in result, "to_dict has asr_to_matcher_ms")
    _assert("matcher_to_wake_ms" in result, "to_dict has matcher_to_wake_ms")
    _assert("end_to_end_ms" in result, "to_dict has end_to_end_ms")

    e2e = lt.end_to_end_ms
    _assert(e2e is not None and e2e >= 10.0, "end_to_end_ms >= 10ms", str(e2e))

    # Unknown stage warns but does not crash
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        lt.mark("unknown_stage")
        _assert(len(w) == 1, "Unknown stage emits exactly 1 warning")
        _assert("unknown_stage" in str(w[0].message), "Warning mentions stage name")


# ── P5-BLOCK-005: Explicit HEALTH_SIGNAL_MAP ──────────────────────────────────

def test_health_signal_map():
    print("\nP5-BLOCK-005: Explicit HEALTH_SIGNAL_MAP")
    required_signals = {"queue_overruns", "vad_lag", "memory_pressure",
                        "restart_frequency", "transport_latency", "dropped_wake_candidates"}
    _assert(required_signals.issubset(set(HEALTH_SIGNAL_MAP.keys())),
            "All required signals present in HEALTH_SIGNAL_MAP")

    for name, sig in HEALTH_SIGNAL_MAP.items():
        _assert(sig.metric_key is not None, f"{name}: has metric_key")
        _assert(callable(sig.normalizer), f"{name}: normalizer is callable")
        _assert(sig.description != "", f"{name}: has description")
        # Normalizer must clamp to [0, 1]
        _assert(0.0 <= sig.normalizer(0.0) <= 1.0, f"{name}: normalizer(0) in [0,1]")
        _assert(0.0 <= sig.normalizer(1e9) <= 1.0, f"{name}: normalizer(1e9) clamped")

    _assert(required_signals.issubset(set(SIGNAL_WEIGHTS.keys())),
            "SIGNAL_WEIGHTS covers all signals")
    total = sum(SIGNAL_WEIGHTS.values())
    _assert(abs(total - 1.0) < 1e-9, f"SIGNAL_WEIGHTS sum to 1.0 (got {total:.6f})")


# ── RuntimeClock ───────────────────────────────────────────────────────────────

def test_runtime_clock():
    print("\nRuntimeClock")
    t0 = now_s()
    _assert(isinstance(now_ns(), int) and now_ns() > 0, "now_ns() returns positive int")
    _assert(isinstance(now_s(), float) and now_s() >= t0, "now_s() returns float >= t0")
    _assert(isinstance(monotonic(), float), "monotonic() returns float")
    _assert(uptime_s() >= 0.0, "uptime_s() >= 0")


# ── RollingLatency ─────────────────────────────────────────────────────────────

def test_rolling_latency():
    print("\nRollingLatency")
    rl = RollingLatency("end_to_end_ms", window=5)
    for ms in [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]:
        rl.record(ms)
    # window=5, so 10.0 evicted
    _assert(abs(rl.avg_ms - 40.0) < 1.0, "avg_ms after window eviction", str(rl.avg_ms))
    _assert(rl.max_ms == 60.0, "max_ms correct")
    d = rl.to_dict()
    _assert("label" in d and "avg_ms" in d and "p99_ms" in d, "to_dict has required fields")


# ── LogContext + StructuredFormatter ──────────────────────────────────────────

def test_log_context():
    print("\nLogContext")
    sid = LogContext.new_session()
    _assert(sid.startswith("sess_"), "Session ID starts with 'sess_'")
    LogContext.set_correlation("corr-block-001")
    LogContext.set_subsystem("TestSubsystem")
    ctx = LogContext.get()
    _assert(ctx["session_id"] == sid, "session_id stored")
    _assert(ctx["correlation_id"] == "corr-block-001", "correlation_id stored")
    _assert(ctx["subsystem"] == "TestSubsystem", "subsystem stored")

def test_structured_formatter_json():
    print("\nStructuredFormatter JSON mode")
    import logging
    fmt = StructuredFormatter(json_mode=True)
    record = logging.LogRecord("test", logging.INFO, "", 0, "hello world", (), None)
    output = fmt.format(record)
    parsed = json.loads(output)
    _assert(parsed.get("schema_version") == 1, "JSON has schema_version=1")
    _assert(parsed.get("level") == "INFO", "JSON has level=INFO")
    _assert(parsed.get("message") == "hello world", "JSON has correct message")
    _assert("session_id" in parsed, "JSON has session_id")
    _assert("correlation_id" in parsed, "JSON has correlation_id")


# ── Health Scorer ─────────────────────────────────────────────────────────────

def test_health_score():
    print("\nHealth Scorer")
    healthy = HealthSignals()
    score = compute_health_score(healthy)
    _assert(score == 1.0, "All-zero signals -> score = 1.0", str(score))

    degraded = HealthSignals(restart_frequency=1.0, queue_overruns=1.0)
    score2 = compute_health_score(degraded)
    _assert(score2 < 0.7, "High pressure -> score < 0.7", str(score2))
    _assert(score2 >= 0.0, "Score >= 0.0")

    metrics = {"queue_depth": 0, "reset_count": 0, "restart_count": 5,
               "audio_drop_count": 0, "telemetry_drop_count": 0, "memory_usage_mb": None,
               "transport_latency_ms": 0}
    score3 = score_from_metrics(metrics)
    _assert(0.0 <= score3 <= 1.0, "score_from_metrics bounded [0,1]", str(score3))


# ── MetricsCollector ──────────────────────────────────────────────────────────

def test_metrics_collector():
    print("\nMetricsCollector")
    mc = MetricsCollector()
    mc.record_wake(42.0)
    mc.record_wake(58.0)
    mc.record_reset()
    mc.record_restart()
    mc.record_audio_drop()
    mc.set_queue_depth(7)
    _assert(mc.wake_count == 2, "wake_count == 2")
    _assert(abs(mc.avg_latency_ms - 50.0) < 0.1, "avg_latency_ms == 50.0")
    _assert(mc.reset_count == 1, "reset_count == 1")
    _assert(mc.restart_count == 1, "restart_count == 1")
    _assert(mc.queue_depth == 7, "queue_depth == 7")
    all_m = mc.get_all_metrics()
    for key in ["wake_count", "avg_latency_ms", "queue_depth", "telemetry_drop_count"]:
        _assert(key in all_m, f"get_all_metrics has '{key}'")


# ── Main runner ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  AVAListener -- Phase 5 Observability Tests (P5-BLOCK fixes)")
    print("=" * 60)

    test_logging_module_ownership()
    test_explicit_pipeline_stages()
    test_health_signal_map()
    test_runtime_clock()
    test_rolling_latency()
    test_log_context()
    test_structured_formatter_json()
    test_health_score()
    test_metrics_collector()

    print()
    print("=" * 60)
    print(f"  Results: {_passed}/{_passed+_failed} passed  |  {_failed} failed")
    print("=" * 60)
    sys.exit(0 if _failed == 0 else 1)
