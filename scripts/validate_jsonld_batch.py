#!/usr/bin/env python3
"""
Batch validate JSON-LD files in a directory.

Usage:
    python scripts/validate_jsonld_batch.py <directory> [--exclude <pattern>]
"""

import sys
import subprocess
from pathlib import Path

# Resolve path to validate_jsonld.py (same directory as this script)
SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATE_SCRIPT = SCRIPT_DIR / "validate_jsonld.py"


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/validate_jsonld_batch.py <directory> [--exclude <pattern>]")
        sys.exit(1)
    
    directory = Path(sys.argv[1])
    exclude_pattern = None
    if len(sys.argv) >= 4 and sys.argv[2] == "--exclude":
        exclude_pattern = sys.argv[3]
    
    if not directory.exists():
        print(f"Directory {directory} does not exist. Skipping validation.")
        sys.exit(0)
    
    if not directory.is_dir():
        print(f"{directory} is not a directory.")
        sys.exit(1)
    
    # Find all JSON-LD files
    jsonld_files = list(directory.rglob("*.jsonld"))
    
    # Filter out excluded paths
    if exclude_pattern:
        jsonld_files = [f for f in jsonld_files if exclude_pattern not in str(f)]
    
    if not jsonld_files:
        print(f"No JSON-LD files found in {directory}")
        sys.exit(0)
    
    print(f"Found {len(jsonld_files)} JSON-LD file(s) to validate")
    print("=" * 60)
    
    failed = False
    for file_path in sorted(jsonld_files):
        print(f"\nValidating: {file_path}")
        result = subprocess.run(
            [sys.executable, str(VALIDATE_SCRIPT), str(file_path)],
            capture_output=False,
            cwd=SCRIPT_DIR.parent  # run from repo root so paths resolve
        )
        if result.returncode != 0:
            failed = True
    
    print("\n" + "=" * 60)
    if failed:
        print("Some files failed validation")
        sys.exit(1)
    else:
        print(f"All {len(jsonld_files)} file(s) validated successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
