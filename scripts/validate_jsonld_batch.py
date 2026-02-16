#!/usr/bin/env python3
"""
Validate JSON-LD files under a directory (e.g. data/objects/summoned/generated).
Checks: valid JSON, @context, @type, name; spatialCoverage box format; distribution encodingFormat as array.
WebPage and DataCatalog are accepted with a warning (expected Dataset for dataset files).
Exits 0 if all pass, 1 if any file fails.
"""
import json
import sys
from pathlib import Path


def get_box_string(data):
    """Extract spatialCoverage box string if present."""
    sc = data.get("spatialCoverage")
    if not isinstance(sc, dict):
        return None
    geo = sc.get("geo")
    if not isinstance(geo, dict):
        return None
    box = geo.get("box")
    if isinstance(box, str):
        return box.strip()
    return None


def validate_box(box_str):
    """Validate Schema.org box format: 'west,south east,north'. Returns (True, None) or (False, error_msg)."""
    if not box_str:
        return True, None
    parts = box_str.split()
    if len(parts) == 2:
        try:
            ws = parts[0].split(",")
            en = parts[1].split(",")
            if len(ws) == 2 and len(en) == 2:
                west, south = float(ws[0]), float(ws[1])
                east, north = float(en[0]), float(en[1])
                if -90 <= south <= 90 and -90 <= north <= 90 and -180 <= west <= 180 and -180 <= east <= 180:
                    return True, None
                return False, "box out of range"
        except ValueError:
            return False, "invalid box format"
    elif len(parts) == 4:
        try:
            a, b, c, d = float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])
            if -90 <= b <= 90 and -90 <= d <= 90:
                west, south, east, north = a, b, c, d
            else:
                south, west, north, east = a, b, c, d
            if -90 <= south <= 90 and -90 <= north <= 90 and -180 <= west <= 180 and -180 <= east <= 180:
                return True, None
            return False, "box out of range"
        except ValueError:
            return False, "invalid box numbers"
    return False, "box expected 2 or 4 numbers"


def check_distribution_encoding_format(data):
    """Check that each distribution has encodingFormat as array. Returns list of error strings (empty if ok)."""
    errs = []
    dist = data.get("distribution")
    if not isinstance(dist, list):
        return errs
    for i, item in enumerate(dist):
        if not isinstance(item, dict):
            continue
        ef = item.get("encodingFormat")
        if ef is None:
            continue
        if isinstance(ef, str):
            errs.append(f"distribution[{i}].encodingFormat must be array, got string")
        elif not isinstance(ef, list):
            errs.append(f"distribution[{i}].encodingFormat must be array, got {type(ef).__name__}")
    return errs


def validate_file(path: Path) -> tuple[bool, list]:
    """
    Validate one JSON-LD file. Returns (success: bool, list of warning/error messages).
    success=False means hard failure (invalid JSON or missing required fields).
    """
    errors = []
    warnings = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"JSON Syntax Error: Invalid JSON: {e}"]
    except Exception as e:
        return False, [str(e)]

    # Required keys
    for key in ["@context", "@type", "name"]:
        if key not in data:
            errors.append(f"missing '{key}'")
    if errors:
        return False, errors

    # @type: Dataset expected; WebPage and DataCatalog allowed with warning
    dtype = data.get("@type", "")
    if dtype not in ("Dataset", "DataCatalog", "WebPage"):
        if dtype:
            warnings.append(f"@type is '{dtype}', expected 'Dataset'")
    elif dtype in ("WebPage", "DataCatalog"):
        warnings.append(f"@type is '{dtype}', expected 'Dataset'")

    # spatialCoverage box
    box_str = get_box_string(data)
    if box_str:
        ok, msg = validate_box(box_str)
        if not ok:
            errors.append(f"spatialCoverage box: {msg}")

    # distribution encodingFormat must be array
    ef_errs = check_distribution_encoding_format(data)
    errors.extend(ef_errs)

    all_msgs = errors + warnings
    return len(errors) == 0, all_msgs


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_jsonld_batch.py <directory>", file=sys.stderr)
        sys.exit(2)
    root = Path(sys.argv[1])
    if not root.is_dir():
        print(f"Error: not a directory: {root}", file=sys.stderr)
        sys.exit(2)

    files = sorted(root.rglob("*.jsonld"))
    print(f"Found {len(files)} JSON-LD file(s) to validate")
    print("=" * 60)

    failed = []
    for path in files:
        rel = path.as_posix()
        print(f"\nValidating: {rel}")
        print("=" * 60)
        success, messages = validate_file(path)
        if not success:
            for m in messages:
                print(f"Error:  {m}")
            failed.append(rel)
            continue
        print("[OK] Valid JSON syntax")
        if messages:
            print("Warning:  Warnings:")
            for m in messages:
                print(f"  - {m}")
            print("[PASSED] Validation passed with warning(s)")
        else:
            print("[SUCCESS] All validations passed!")
        # Summary
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = data.get("name", "")
            if len(name) > 50:
                name = name[:47] + "..."
            print("Summary:")
            print(f"  - Type: {data.get('@type', '')}")
            print(f"  - Name: {name}...")
            box_str = get_box_string(data)
            if box_str:
                print(f"  - Bounding Box: {box_str}")
            dist = data.get("distribution")
            if isinstance(dist, list):
                print(f"  - Distribution entries: {len(dist)}")
        except Exception:
            pass
    print("\n" + "=" * 60)
    if failed:
        print("Some files failed validation")
        sys.exit(1)
    print("All validations passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
