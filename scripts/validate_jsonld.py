#!/usr/bin/env python3
"""
Validate JSON-LD files for Schema.org Dataset compliance.

This script validates:
1. JSON syntax
2. Schema.org structure
3. Required fields
4. Bounding box format
5. Data types
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional


def validate_json_syntax(file_path: Path) -> tuple[bool, Optional[str]]:
    """Validate JSON syntax."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return True, None
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    except Exception as e:
        return False, f"Error reading file: {e}"


def validate_schema_structure(data: Dict) -> List[str]:
    """Validate Schema.org Dataset structure."""
    errors = []
    warnings = []
    
    # Check required fields
    required_fields = ['@context', '@type', '@id', 'name']
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    
    # Check @type
    if '@type' in data and data['@type'] != 'Dataset':
        warnings.append(f"@type is '{data['@type']}', expected 'Dataset'")
    
    # Check @context
    if '@context' in data:
        context = data['@context']
        if isinstance(context, str):
            if not context.startswith('https://schema.org'):
                warnings.append(f"@context should point to schema.org: {context}")
        elif isinstance(context, dict):
            if '@vocab' in context:
                vocab = context['@vocab']
                if not vocab.startswith('https://schema.org'):
                    warnings.append(f"@vocab should point to schema.org: {vocab}")
    
    # Check spatialCoverage format
    if 'spatialCoverage' in data:
        spatial = data['spatialCoverage']
        if isinstance(spatial, dict):
            if 'geo' in spatial:
                geo = spatial['geo']
                if isinstance(geo, dict) and 'box' in geo:
                    box = geo['box']
                    if isinstance(box, str):
                        # Validate box format: "west,south east,north"
                        parts = box.split()
                        if len(parts) != 2:
                            errors.append(f"Invalid box format: '{box}'. Expected 'west,south east,north'")
                        else:
                            try:
                                west_south = parts[0].split(',')
                                east_north = parts[1].split(',')
                                if len(west_south) != 2 or len(east_north) != 2:
                                    errors.append(f"Invalid box format: '{box}'. Coordinates must be comma-separated pairs")
                                else:
                                    west, south = float(west_south[0]), float(west_south[1])
                                    east, north = float(east_north[0]), float(east_north[1])
                                    
                                    # Validate ranges
                                    if not (-180 <= west <= 180):
                                        errors.append(f"Invalid west longitude: {west} (must be -180 to 180)")
                                    if not (-180 <= east <= 180):
                                        errors.append(f"Invalid east longitude: {east} (must be -180 to 180)")
                                    if not (-90 <= south <= 90):
                                        errors.append(f"Invalid south latitude: {south} (must be -90 to 90)")
                                    if not (-90 <= north <= 90):
                                        errors.append(f"Invalid north latitude: {north} (must be -90 to 90)")
                                    if west >= east:
                                        errors.append(f"West ({west}) must be less than East ({east})")
                                    if south >= north:
                                        errors.append(f"South ({south}) must be less than North ({north})")
                            except ValueError as e:
                                errors.append(f"Invalid box format: '{box}'. {e}")
    
    # Check distribution format
    if 'distribution' in data:
        dist = data['distribution']
        if isinstance(dist, list):
            for i, item in enumerate(dist):
                if not isinstance(item, dict):
                    errors.append(f"Distribution[{i}] must be an object")
                elif '@type' not in item:
                    warnings.append(f"Distribution[{i}] missing @type (should be 'DataDownload')")
        elif isinstance(dist, dict):
            if '@type' not in dist:
                warnings.append("Distribution missing @type (should be 'DataDownload')")
    
    return errors, warnings


def validate_data_types(data: Dict) -> List[str]:
    """Validate data types for common fields."""
    warnings = []
    
    # Check datePublished format
    if 'datePublished' in data:
        date = data['datePublished']
        if isinstance(date, str):
            # Should be ISO 8601 format (YYYY-MM-DD)
            if len(date) < 10 or date[4] != '-' or date[7] != '-':
                warnings.append(f"datePublished format may be incorrect: '{date}' (expected YYYY-MM-DD)")
    
    # Check version
    if 'version' in data:
        version = data['version']
        if not isinstance(version, str):
            warnings.append(f"version should be a string, got {type(version)}")
    
    # Check license
    if 'license' in data:
        license_val = data['license']
        if isinstance(license_val, str):
            if not license_val.startswith('http'):
                warnings.append(f"license should be a URL: '{license_val}'")
        elif isinstance(license_val, list):
            for i, lic in enumerate(license_val):
                if isinstance(lic, str) and not lic.startswith('http'):
                    warnings.append(f"license[{i}] should be a URL: '{lic}'")
                elif isinstance(lic, dict) and 'url' in lic:
                    url = lic['url']
                    if not url.startswith('http'):
                        warnings.append(f"license[{i}].url should be a URL: '{url}'")
    
    return warnings


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_jsonld.py <jsonld_file>")
        sys.exit(1)
    
    file_path = Path(sys.argv[1])
    
    if not file_path.exists():
        print(f"[ERROR] File not found: {file_path}")
        sys.exit(1)
    
    print(f"Validating: {file_path}")
    print("=" * 60)
    
    # Validate JSON syntax
    is_valid, error = validate_json_syntax(file_path)
    if not is_valid:
        print(f"[ERROR] JSON Syntax Error: {error}")
        sys.exit(1)
    
    print("[OK] Valid JSON syntax")
    
    # Load data
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Validate Schema.org structure
    errors, warnings = validate_schema_structure(data)
    
    # Validate data types
    type_warnings = validate_data_types(data)
    warnings.extend(type_warnings)
    
    # Print results
    if errors:
        print("\n[ERROR] Errors found:")
        for error in errors:
            print(f"  - {error}")
    
    if warnings:
        print("\n[WARNING] Warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    
    if not errors and not warnings:
        print("\n[SUCCESS] All validations passed!")
        print("\nSummary:")
        print(f"  - Type: {data.get('@type', 'N/A')}")
        print(f"  - Name: {data.get('name', 'N/A')[:60]}...")
        if 'spatialCoverage' in data:
            spatial = data['spatialCoverage']
            if isinstance(spatial, dict) and 'geo' in spatial:
                geo = spatial['geo']
                if isinstance(geo, dict) and 'box' in geo:
                    print(f"  - Bounding Box: {geo['box']}")
        if 'distribution' in data:
            dist = data['distribution']
            count = len(dist) if isinstance(dist, list) else 1
            print(f"  - Distribution entries: {count}")
        sys.exit(0)
    elif errors:
        print(f"\n[FAILED] Validation failed with {len(errors)} error(s)")
        sys.exit(1)
    else:
        print(f"\n[PASSED] Validation passed with {len(warnings)} warning(s)")
        sys.exit(0)


if __name__ == '__main__':
    main()
