import os
import sys
import json

_base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _base)

from runtime.config.profile_loader import (
    load_profile, resolve_inheritance, detect_cycle, 
    CircularProfileError, MissingParentProfileError
)
from runtime.config.mutability import check_mutability, RestartRequiredError
from runtime.config.profile_migrations import apply_migrations, UnsupportedProfileVersionError
from runtime.config.profile_validator import validate_profile

def create_temp_profile(path, content):
    with open(path, 'w') as f:
        json.dump(content, f)

def run_tests():
    print("Testing inheritance resolution...")
    create_temp_profile("p_base.json", {"profileVersion": 2, "asr": {"provider": "base"}})
    create_temp_profile("p_child.json", {"profileVersion": 2, "extends": "p_base.json", "asr": {"numThreads": 4}})
    
    merged = load_profile("p_child.json")
    assert merged["asr"]["provider"] == "base"
    assert merged["asr"]["numThreads"] == 4
    print("  PASS")

    print("Testing circular inheritance...")
    create_temp_profile("p_a.json", {"profileVersion": 2, "extends": "p_b.json"})
    create_temp_profile("p_b.json", {"profileVersion": 2, "extends": "p_a.json"})
    try:
        load_profile("p_a.json")
        assert False, "Should have raised CircularProfileError"
    except CircularProfileError:
        pass
    print("  PASS")

    print("Testing missing parent...")
    create_temp_profile("p_c.json", {"profileVersion": 2, "extends": "missing.json"})
    try:
        load_profile("p_c.json")
        assert False, "Should have raised MissingParentProfileError"
    except MissingParentProfileError:
        pass
    print("  PASS")

    print("Testing migration v1 -> v2...")
    v1_prof = {
        "profileVersion": 1,
        "wakePhrases": [
            {"phrase": "hello"}
        ]
    }
    migrated = apply_migrations(v1_prof)
    assert migrated["profileVersion"] == 2
    assert migrated["wakePhrases"][0]["weight"] == 1.0
    print("  PASS")

    print("Testing mutability enforcement...")
    # hot reload field
    check_mutability("vad.sileroThreshold", True)
    # restart required field
    try:
        check_mutability("asr.provider", True)
        assert False, "Should have raised RestartRequiredError"
    except RestartRequiredError:
        pass
    # when inactive
    check_mutability("asr.provider", False)
    print("  PASS")
    
    print("Testing profile validation...")
    create_temp_profile("p_valid.json", {
        "profileVersion": 2,
        "wakePhrases": [{"phraseId": "p1", "threshold": 0.5}]
    })
    res = validate_profile("p_valid.json")
    assert res.valid
    
    create_temp_profile("p_invalid.json", {
        "profileVersion": 2,
        "wakePhrases": [
            {"phraseId": "p1", "threshold": 0.3},
            {"phraseId": "p1", "threshold": 0.5}
        ],
        "unknownField": 1
    })
    res2 = validate_profile("p_invalid.json")
    assert not res2.valid or len(res2.warnings) > 0
    assert any("Duplicate phraseId" in e for e in res2.errors)
    assert any("Very low threshold" in w for w in res2.warnings)
    assert any("Unknown field" in w for w in res2.warnings)
    print("  PASS")

    # cleanup
    for f in ["p_base.json", "p_child.json", "p_a.json", "p_b.json", "p_c.json", "p_valid.json", "p_invalid.json"]:
        if os.path.exists(f):
            os.remove(f)

if __name__ == "__main__":
    run_tests()
    print("All tests passed.")
