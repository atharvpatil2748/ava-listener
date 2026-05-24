import logging
from typing import Callable, Dict, Tuple

log = logging.getLogger("profile_migrations")

class UnsupportedProfileVersionError(Exception):
    pass

def migrate_v1_to_v2(profile: dict) -> dict:
    """Adds weight: 1.0 to any phrase missing it."""
    wake_phrases = profile.get("wakePhrases", [])
    for phrase in wake_phrases:
        if "weight" not in phrase:
            phrase["weight"] = 1.0
    profile["profileVersion"] = 2
    return profile

PROFILE_MIGRATIONS: Dict[Tuple[int, int], Callable] = {
    (1, 2): migrate_v1_to_v2
}

CURRENT_PROFILE_VERSION = 2

def apply_migrations(profile: dict) -> dict:
    version = profile.get("profileVersion", 1)
    
    if version > CURRENT_PROFILE_VERSION:
        raise UnsupportedProfileVersionError(f"Profile version {version} is higher than supported {CURRENT_PROFILE_VERSION}")
        
    while version < CURRENT_PROFILE_VERSION:
        next_version = version + 1
        migration_fn = PROFILE_MIGRATIONS.get((version, next_version))
        if not migration_fn:
            raise UnsupportedProfileVersionError(f"No migration path from version {version} to {next_version}")
            
        log.info(f"Migrating profile from v{version} to v{next_version}")
        profile = migration_fn(profile)
        version = next_version
        
    return profile
