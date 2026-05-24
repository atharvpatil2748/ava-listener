# -*- coding: utf-8 -*-
"""
AVAListener — Watchdog Idle Listening Test
===========================================
Verifies that the RuntimeWatchdog does not trigger resets during idle listening
(when no speech is being processed), even over a simulated 60 seconds duration.
"""

from __future__ import annotations

import sys
import os
import time
from unittest.mock import MagicMock, patch

# Force UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Path bootstrap
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _ROOT)

from runtime.watchdog import RuntimeWatchdog

class MockThread:
    def is_alive(self) -> bool:
        return True

def test_watchdog_idle_listening_simulated():
    """
    Verify that 60 seconds of idle listening results in zero resets
    and zero watchdog resets using simulated/mocked state.
    """
    # 1. Create a mocked streamer to simulate the ASR streamer state
    mock_streamer = MagicMock()
    mock_thread = MockThread()
    mock_streamer._worker_thread = mock_thread
    
    # Initially set the heartbeat to time.monotonic() and idle listening (processing_active = False)
    mock_streamer._worker_heartbeat = time.monotonic()
    mock_streamer._processing_active = False
    mock_streamer._audio_queue.qsize.return_value = 0
    mock_streamer._vad = None  # skips VAD check
    
    # Track resets
    reset_reasons = []
    def fake_reset_stream(reason="manual"):
        reset_reasons.append(reason)
    mock_streamer._reset_stream.side_effect = fake_reset_stream

    # 2. Instantiate watchdog
    # Default: interval_s = 5.0, worker_timeout_s = 4.0
    watchdog = RuntimeWatchdog(mock_streamer, interval_s=5.0, worker_timeout_s=4.0)

    # 3. Simulate 60 seconds of time passing (12 checks of 5 seconds each)
    # The heartbeat is updated periodically in idle state.
    start_time = time.monotonic()
    
    for step in range(1, 13):  # 12 steps * 5s = 60s
        simulated_now = start_time + (step * 5.0)
        
        # In idle state: update heartbeat periodically in the worker
        # (This mimics the ASR worker updating its heartbeat on queue read timeouts)
        mock_streamer._worker_heartbeat = simulated_now
        
        with patch('time.monotonic', return_value=simulated_now):
            watchdog._check_worker()
            watchdog._check_queue()
            watchdog._check_vad()

    # 4. Assert no resets occurred
    assert len(reset_reasons) == 0, f"Expected 0 resets, got {len(reset_reasons)}: {reset_reasons}"
    assert watchdog.watchdog_metrics["resets_total"] == 0
    print("  [PASS] Simulated 60 seconds idle listening: 0 resets")

def test_watchdog_idle_no_heartbeat_updates():
    """
    Verify that even if the heartbeat is NOT updated in idle state,
    the watchdog does not trigger a hang reset because processing_active is False.
    """
    mock_streamer = MagicMock()
    mock_thread = MockThread()
    mock_streamer._worker_thread = mock_thread
    
    # Fixed start heartbeat
    start_time = 1000.0
    mock_streamer._worker_heartbeat = start_time
    mock_streamer._processing_active = False
    mock_streamer._audio_queue.qsize.return_value = 0
    mock_streamer._vad = None
    
    reset_reasons = []
    def fake_reset_stream(reason="manual"):
        reset_reasons.append(reason)
    mock_streamer._reset_stream.side_effect = fake_reset_stream

    watchdog = RuntimeWatchdog(mock_streamer, interval_s=5.0, worker_timeout_s=4.0)

    # Simulate 60 seconds later, heartbeat is still at 1000.0 (stale by 60s)
    simulated_now = start_time + 60.0
    with patch('time.monotonic', return_value=simulated_now):
        watchdog._check_worker()

    assert len(reset_reasons) == 0, f"watchdog triggered reset for idle worker with stale heartbeat: {reset_reasons}"
    assert watchdog.watchdog_metrics["resets_total"] == 0
    print("  [PASS] Simulated stale heartbeat during idle listening: 0 resets")

def test_watchdog_hang_triggered_during_processing():
    """
    Verify that if processing_active is True and heartbeat becomes stale,
    the watchdog correctly triggers a worker_hang reset.
    """
    mock_streamer = MagicMock()
    mock_thread = MockThread()
    mock_streamer._worker_thread = mock_thread
    
    start_time = 1000.0
    mock_streamer._worker_heartbeat = start_time
    mock_streamer._processing_active = True
    mock_streamer._audio_queue.qsize.return_value = 0
    mock_streamer._vad = None
    
    reset_reasons = []
    def fake_reset_stream(reason="manual"):
        reset_reasons.append(reason)
    mock_streamer._reset_stream.side_effect = fake_reset_stream

    watchdog = RuntimeWatchdog(mock_streamer, interval_s=5.0, worker_timeout_s=4.0)

    # Simulate heartbeat stale (age = 5.0s > worker_timeout = 4.0s)
    simulated_now = start_time + 5.0
    with patch('time.monotonic', return_value=simulated_now):
        watchdog._check_worker()

    assert len(reset_reasons) == 1
    assert reset_reasons[0] == "worker_hang"
    assert watchdog.watchdog_metrics["resets_total"] == 1
    assert watchdog.watchdog_metrics["resets_by_reason"]["worker_hang"] == 1
    print("  [PASS] Simulated stale heartbeat during active processing: watchdog reset triggered correctly")

if __name__ == "__main__":
    print("\n========================================================")
    print("  watchdog idle and processing tests")
    print("========================================================")
    test_watchdog_idle_listening_simulated()
    test_watchdog_idle_no_heartbeat_updates()
    test_watchdog_hang_triggered_during_processing()
    print("========================================================")
    print("  Results: 3/3 passed")
    print("========================================================\n")
