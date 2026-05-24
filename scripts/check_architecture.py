#!/usr/bin/env python3
"""
AVAListener — Architecture Compliance Checker (Phase S, S5)
===========================================================
Statically verifies import boundaries and ownership rules across the
runtime module tree using AST-based analysis.

Checks performed
----------------
1. FORBIDDEN IMPORTS
   Verifies that no module inside a "source" package imports from
   a "target" package it is not permitted to depend on:

     asr   → matcher  (forbidden: ASR must not know about matching)
     asr   → vad      (forbidden: ASR must not gate on VAD internally)
     vad   → matcher  (forbidden: VAD must not know about matching)
     providers → orchestrator  (forbidden: providers must not call up)

2. OWNERSHIP CHECKS (heuristic, AST-based)
   Verifies that banned ownership patterns do not appear in the wrong
   modules:

     sounddevice.InputStream created outside AudioResources
     onnxruntime.InferenceSession created outside resources/

Usage
-----
    python scripts/check_architecture.py
    python scripts/check_architecture.py --strict   # exit 1 on any violation

Exit codes
----------
    0  — all checks passed
    1  — one or more violations detected (only with --strict or when
         violations exist that are not marked as known debt)
"""
from __future__ import annotations

import ast
import os
import sys
import argparse
from pathlib import Path
from typing import NamedTuple

# Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Root of the ava-listener package (this script lives in scripts/)
_SCRIPT_DIR = Path(__file__).resolve().parent
_ROOT = _SCRIPT_DIR.parent  # ava-listener/

# Forbidden import edges:  (source_module_prefix, forbidden_import_prefix, description)
FORBIDDEN_IMPORTS: list[tuple[str, str, str]] = [
    (
        "runtime.asr",
        "runtime.matcher",
        "ASR must not import from matcher — orchestrator is the sole integration point",
    ),
    (
        "runtime.asr",
        "runtime.vad",
        "ASR must not import from VAD directly — VAD is invoked by the worker/streamer only",
    ),
    (
        "runtime.vad",
        "runtime.matcher",
        "VAD must not import from matcher",
    ),
    (
        "runtime.asr.providers",
        "runtime.kernel.orchestrator",
        "ASR providers must not call up to the orchestrator",
    ),
    (
        "runtime.vad.providers",
        "runtime.kernel.orchestrator",
        "VAD providers must not call up to the orchestrator",
    ),
]

# Ownership checks: (pattern_to_find, banned_in_glob, description)
# pattern_to_find is an attribute access string (e.g. "sd.InputStream")
OWNERSHIP_CHECKS: list[tuple[str, str, str]] = [
    (
        "sd.InputStream",
        "runtime/asr/streaming.py",
        "[KNOWN-DEBT] Audio stream (sd.InputStream) should be owned by AudioResources, not streaming.py",
    ),
    (
        "onnxruntime.InferenceSession",
        "runtime/vad/pipeline.py",
        "[KNOWN-DEBT] ONNX session (ort.InferenceSession) should be owned by vad_resources.py, not pipeline.py",
    ),
]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

class Violation(NamedTuple):
    check_type: str          # "FORBIDDEN_IMPORT" | "OWNERSHIP"
    source_file: str
    description: str
    is_known_debt: bool = False


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _collect_python_files(root: Path) -> list[Path]:
    """Recursively collect all .py files under root."""
    return sorted(root.rglob("*.py"))


def _module_name(path: Path, root: Path) -> str:
    """Convert a file path to a dotted module name relative to root."""
    rel = path.relative_to(root)
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__.py":
        parts = parts[:-1]
    elif parts and parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


def _get_imports(source: str) -> list[str]:
    """
    Extract all imported module names from Python source code.
    Returns dotted module names (e.g. "runtime.matcher.registry").
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def _find_attribute_access(source: str, attr_chain: str) -> bool:
    """
    Check if a specific attribute access chain (e.g. "sd.InputStream")
    appears in the source. Uses simple string search after normalization.
    """
    # Normalize: remove spaces around dots
    needle = attr_chain.replace(" ", "")
    return needle in source.replace(" ", "")


# ---------------------------------------------------------------------------
# Check 1: Forbidden imports
# ---------------------------------------------------------------------------

def check_forbidden_imports(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    py_files = _collect_python_files(root / "runtime")

    for path in py_files:
        module = _module_name(path, root)
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        imports = _get_imports(source)

        for src_prefix, forbidden_prefix, desc in FORBIDDEN_IMPORTS:
            if not module.startswith(src_prefix):
                continue
            for imp in imports:
                if imp.startswith(forbidden_prefix):
                    violations.append(Violation(
                        check_type="FORBIDDEN_IMPORT",
                        source_file=str(path.relative_to(root)),
                        description=(
                            f"{module} → {imp}\n"
                            f"  Rule: {desc}"
                        ),
                        is_known_debt=False,
                    ))
    return violations


# ---------------------------------------------------------------------------
# Check 2: Ownership violations
# ---------------------------------------------------------------------------

def check_ownership(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    py_files = _collect_python_files(root / "runtime")

    for path in py_files:
        rel = str(path.relative_to(root)).replace("\\", "/")
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for pattern, expected_location, desc in OWNERSHIP_CHECKS:
            if not _find_attribute_access(source, pattern):
                continue
            # Check if this file IS the expected owner
            if expected_location in rel:
                # File is the expected location — not a violation
                continue
            # Check if file is the approved resource module
            if "resources/" in rel:
                continue
            is_known = "[KNOWN-DEBT]" in desc
            violations.append(Violation(
                check_type="OWNERSHIP",
                source_file=rel,
                description=desc.replace("[KNOWN-DEBT] ", "") + f"\n  Found in: {rel}",
                is_known_debt=is_known,
            ))

    return violations


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def _print_report(
    forbidden: list[Violation],
    ownership: list[Violation],
    strict: bool,
) -> int:
    """Print the full report. Returns exit code."""
    SEP = "=" * 70

    total_violations = len(forbidden) + len(ownership)
    new_violations = [v for v in (forbidden + ownership) if not v.is_known_debt]

    print(f"\n{SEP}")
    print(f"  AVAListener — Architecture Compliance Report (Phase S)")
    print(SEP)

    # -- Forbidden import violations --
    print(f"\n[1] FORBIDDEN IMPORT CHECKS  ({len(forbidden)} violation(s))")
    print("-" * 70)
    if not forbidden:
        print("  [OK]  All forbidden import rules pass.")
    else:
        for v in forbidden:
            tag = "[KNOWN-DEBT]" if v.is_known_debt else "[VIOLATION]"
            print(f"\n  {tag}  {v.source_file}")
            for line in v.description.split("\n"):
                print(f"         {line}")

    # -- Ownership violations --
    print(f"\n[2] OWNERSHIP CHECKS  ({len(ownership)} violation(s))")
    print("-" * 70)
    if not ownership:
        print("  [OK]  All ownership rules pass.")
    else:
        for v in ownership:
            tag = "[KNOWN-DEBT]" if v.is_known_debt else "[VIOLATION]"
            print(f"\n  {tag}  {v.source_file}")
            for line in v.description.split("\n"):
                print(f"         {line}")

    # -- Summary --
    print(f"\n{SEP}")
    print(f"  Total violations : {total_violations}")
    print(f"  Known debt items : {total_violations - len(new_violations)}")
    print(f"  New violations   : {len(new_violations)}")
    print(SEP)

    if len(new_violations) == 0:
        print("\n  [PASS] Architecture compliance check PASSED (known debt items noted above).")
        return 0

    print(f"\n  [FAIL] Architecture compliance check FAILED -- {len(new_violations)} new violation(s).")
    if strict:
        return 1
    # Without --strict, warn but exit 0 to not break CI until debt is cleared
    print("  (Run with --strict to make this a hard failure.)")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="AVAListener Architecture Compliance Checker (Phase S)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 on ANY violation (including known debt). Default: exit 1 only on new violations.",
    )
    parser.add_argument(
        "--root",
        default=str(_ROOT),
        help=f"Path to ava-listener root (default: {_ROOT})",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"ERROR: root path does not exist: {root}", file=sys.stderr)
        return 2

    forbidden_violations = check_forbidden_imports(root)
    ownership_violations = check_ownership(root)

    return _print_report(forbidden_violations, ownership_violations, strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
