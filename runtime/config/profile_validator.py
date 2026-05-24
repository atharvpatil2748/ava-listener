import os
import sys
from dataclasses import dataclass
from typing import List
from .profile_loader import resolve_inheritance, detect_cycle, CircularProfileError, MissingParentProfileError
from .profile_migrations import apply_migrations, UnsupportedProfileVersionError

@dataclass
class ValidationResult:
    valid: bool
    warnings: List[str]
    errors: List[str]

def validate_profile(path: str) -> ValidationResult:
    warnings = []
    errors = []
    
    try:
        import json
        with open(path, 'r') as f:
            root_profile = json.load(f)
    except Exception as e:
        return ValidationResult(False, warnings, [f"Failed to parse JSON: {e}"])
        
    try:
        root_profile = apply_migrations(root_profile)
    except UnsupportedProfileVersionError as e:
        errors.append(str(e))
        return ValidationResult(False, warnings, errors)
        
    try:
        abs_path = os.path.abspath(path)
        base_dir = os.path.dirname(abs_path)
        chain = resolve_inheritance(root_profile, base_dir, {abs_path})
    except CircularProfileError as e:
        errors.append(str(e))
        return ValidationResult(False, warnings, errors)
    except MissingParentProfileError as e:
        errors.append(str(e))
        return ValidationResult(False, warnings, errors)
    except Exception as e:
        errors.append(f"Inheritance error: {e}")
        return ValidationResult(False, warnings, errors)
        
    # Check for duplicate phraseId
    seen_phrase_ids = set()
    for profile in chain:
        for phrase in profile.get("wakePhrases", []):
            phrase_id = phrase.get("phraseId", phrase.get("phrase", ""))
            if phrase_id in seen_phrase_ids:
                errors.append(f"Duplicate phraseId detected: {phrase_id}")
            seen_phrase_ids.add(phrase_id)
            
            # Check threshold
            threshold = phrase.get("threshold", 0.5)
            if threshold < 0.4:
                warnings.append(f"Very low threshold ({threshold}) for phrase '{phrase_id}'")
                
    # Unknown top-level fields
    known_fields = {"extends", "profileVersion", "name", "description", "wakePhrases", "vad", "asr", "audio", "confidence", "transcription"}
    for k in root_profile.keys():
        if k not in known_fields:
            warnings.append(f"Unknown field '{k}' in profile")

    valid = len(errors) == 0
    return ValidationResult(valid, warnings, errors)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m runtime.config.profile_validator <path>")
        sys.exit(1)
    
    res = validate_profile(sys.argv[1])
    print(f"Valid: {res.valid}")
    for e in res.errors:
        print(f"ERROR: {e}")
    for w in res.warnings:
        print(f"WARN: {w}")
    sys.exit(0 if res.valid else 1)
