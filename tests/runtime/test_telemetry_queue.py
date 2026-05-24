import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from runtime.telemetry.events import start_telemetry_worker, stop_telemetry_worker, emit_structured_event, get_telemetry_drop_count, _dispatcher

def test_telemetry_stress():
    print("Starting telemetry stress test...")
    start_telemetry_worker()
    
    initial_drops = get_telemetry_drop_count()
    
    start_time = time.perf_counter()
    
    # Emit 10000 events rapidly
    # Since queue maxsize is 1000, and we emit 10000 instantly without sleeping much,
    # the queue will fill up and drops will happen, but it must NOT block.
    for i in range(10000):
        emit_structured_event(
            correlation_id=f"stress-{i}",
            subsystem="Test",
            event_type="stress_test",
            payload={"index": i}
        )
        
    duration = time.perf_counter() - start_time
    
    # Assert runtime did not block (10000 emits should take very little time, <0.5s)
    assert duration < 1.0, f"Emitting 10000 events took too long: {duration:.2f}s"
    print(f"Emitted 10000 events in {duration:.3f}s (non-blocking validation PASS)")
    
    # Check queue bounds and drops
    assert _dispatcher._queue.qsize() <= 1000, "Queue exceeded max bounds"
    
    drops = get_telemetry_drop_count() - initial_drops
    print(f"Queue size after rapid emit: {_dispatcher._queue.qsize()}")
    print(f"Total dropped events: {drops}")
    
    # Because worker is draining while we emit, drops might be < 9000, but they should be > 0
    assert drops > 0, "No events were dropped despite massive rapid emit (queue bound failure?)"
    
    # Give the worker a little time to drain
    time.sleep(1.0)
    
    stop_telemetry_worker()
    print("Telemetry worker stopped.")
    
    # After stopping, queue might not be fully drained if we didn't wait long enough, 
    # but that's fine. We just want to ensure it cleans up.
    print("All telemetry stress test assertions PASS")

if __name__ == "__main__":
    test_telemetry_stress()
