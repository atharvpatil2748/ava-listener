import json
import os
import copy
from typing import List, Set

from .profile_migrations import apply_migrations

class CircularProfileError(Exception):
    pass

class MissingParentProfileError(Exception):
    pass

def load_profile(path: str, debug_overlay: bool = False) -> dict:
    """Top-level entry point for loading any profile."""
    abs_path = os.path.abspath(path)
    base_dir = os.path.dirname(abs_path)
    
    with open(abs_path, 'r') as f:
        root_profile = json.load(f)
        
    root_profile = apply_migrations(root_profile)
    
    # Resolve inheritance chain
    chain = resolve_inheritance(root_profile, base_dir, {abs_path})
    # chain[0] is rootmost parent, chain[-1] is the child we started with
    
    if debug_overlay:
        chain.append({
           "transcription": {
              "enableDebug": True
           },
           "diagnostics": {
              "enableInternalTrace": True
           }
        })
    
    merged = merge_profiles(chain)
    return merged

def detect_cycle(path: str, visited: Set[str]) -> None:
    abs_path = os.path.abspath(path)
    if abs_path in visited:
        raise CircularProfileError(f"Circular inheritance detected: {abs_path} already in {visited}")
    visited.add(abs_path)

def resolve_inheritance(profile: dict, base_dir: str, visited: Set[str] = None) -> List[dict]:
    """Walks the extends chain, returns profiles from root ancestor -> child."""
    if visited is None:
        visited = set()
        
    chain = [profile]
    
    current_profile = profile
    current_dir = base_dir
    
    while "extends" in current_profile:
        parent_rel_path = current_profile["extends"]
        parent_abs_path = os.path.abspath(os.path.join(current_dir, parent_rel_path))
        
        detect_cycle(parent_abs_path, visited)
        
        if not os.path.exists(parent_abs_path):
            raise MissingParentProfileError(f"Missing parent profile: {parent_abs_path}")
            
        with open(parent_abs_path, 'r') as f:
            parent_profile = json.load(f)
            
        parent_profile = apply_migrations(parent_profile)
        chain.insert(0, parent_profile)
        
        current_profile = parent_profile
        current_dir = os.path.dirname(parent_abs_path)
        
    return chain

def merge_profiles(profiles: List[dict]) -> dict:
    """Deep merge from root to child."""
    if not profiles:
        return {}
        
    merged = copy.deepcopy(profiles[0])
    
    for profile in profiles[1:]:
        _deep_merge(merged, profile)
        
    return merged

def _deep_merge(dict1: dict, dict2: dict):
    for key, value in dict2.items():
        if key == "wakePhrases":
            # wakePhrases arrays: child replaces parent entirely
            dict1[key] = copy.deepcopy(value)
        elif isinstance(value, dict) and isinstance(dict1.get(key), dict):
            _deep_merge(dict1[key], value)
        else:
            dict1[key] = copy.deepcopy(value)
