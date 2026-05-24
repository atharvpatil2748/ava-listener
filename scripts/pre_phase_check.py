import subprocess
import sys
import os

def run_command(cmd, expected_output=None):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)) + "/..")
    output = result.stdout + result.stderr
    print(output)
    
    if result.returncode != 0:
        print(f"FAILED: Command exited with code {result.returncode}")
        sys.exit(1)
        
    if expected_output and expected_output not in output:
        print(f"FAILED: Expected output '{expected_output}' not found.")
        sys.exit(1)
    
    print("PASS\n")

def main():
    print("--- PRE-PHASE GATE CHECK ---")
    
    # 1. Smoke tests
    run_command(f'"{sys.executable}" tests/smoke/test_smoke.py', expected_output="79/79 passed")
    
    # 2. Replay tests
    run_command(f'"{sys.executable}" tests/replay/test_replay.py', expected_output="23/23 passed")
    
    # 3. Verify startup
    run_command(f'"{sys.executable}" scripts/verify_startup.py', expected_output="RESTORED AND VERIFIED")
    
    # 4. Check identity
    run_command(f'"{sys.executable}" scripts/check_identity.py', expected_output="zero assistant name violations")
    
    print("Automated checks passed!")
    print("Now, please run:")
    print("  python main.py --profile profiles/arvsal.json")
    print("And manually verify:")
    print("  - mic opens")
    print("  - speech events appear")
    print("  - wake triggers")
    print("\nIf successful, you may proceed to Phase 2.")

if __name__ == "__main__":
    main()
