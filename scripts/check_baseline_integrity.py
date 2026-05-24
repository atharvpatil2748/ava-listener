import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from tests.replay.test_replay import PHASE_0_FIXTURES

def main():
    print("--- BASELINE INTEGRITY CHECK ---")
    
    # 1. Check fixture count
    expected_count = 23
    actual_count = len(PHASE_0_FIXTURES)
    if actual_count != expected_count:
        print(f"FAILED: Fixture count is {actual_count}, expected {expected_count}")
        sys.exit(1)
        
    print(f"PASS: Fixture count matches ({expected_count})")
    
    # 2. Check specific fixtures existence and properties
    expected_fixtures = {
        "bare arvsal": (True, "arvsal"),
        "hey arvsal": (True, "hey arvsal"),
        "wake up arvsal": (True, "wake up arvsal"),
        "listen arvsal": (True, "listen arvsal"),
        "listen alone": (True, "listen"),
        "wake alone": (False, ""),
        "listen arv candidate only": (True, "listen"),
        "listen arvsal full": (True, "listen arvsal"),
        "empty window": (False, ""),
        "random everyday speech": (False, ""),
        "context only - no anchor": (False, ""),
        "hey alone": (False, ""),
    }
    
    for name, (expected_trigger, expected_phrase) in expected_fixtures.items():
        found = False
        for fix_name, _, trigger, phrase in PHASE_0_FIXTURES:
            if fix_name == name:
                found = True
                if trigger != expected_trigger:
                    print(f"FAILED: Fixture '{name}' trigger changed. Expected {expected_trigger}, got {trigger}")
                    sys.exit(1)
                expected_phr_val = expected_phrase if expected_phrase else None
                if phrase != expected_phr_val:
                    print(f"FAILED: Fixture '{name}' phrase changed. Expected {expected_phr_val}, got {phrase}")
                    sys.exit(1)
                break
        if not found:
            print(f"FAILED: Fixture '{name}' missing from baseline.")
            sys.exit(1)
            
    print("PASS: Baseline fixture properties match.")
    print("\nBaseline integrity verified.")
    sys.exit(0)

if __name__ == "__main__":
    main()
