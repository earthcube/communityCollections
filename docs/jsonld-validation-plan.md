# JSON-LD Metadata Validation Plan

## Summary

Validate generated JSON-LD against the authoritative dataset webpage, linked download targets, cited papers, and repository or data-release pages. Corrections should be conservative: revise only fields supported by visible source evidence, and leave an inspectable Git diff.

## Manual Checks Added

- Expand source-listed variables into one `variableMeasured` entry per variable. Use the physical variable label as `name` and put short codes such as `bio01`, `tas`, or `lossyear` in `alternateName`.
- Include all citations shown by the source page. When a page has both `Model Citation` and `Data Citation`, represent both as separate structured citation objects.
- Use the exact URL behind a source page's Download button or direct data/API endpoint for `distribution[].contentUrl`; do not use a generic portal root when a more specific target is available.
- Include variables listed in expandable menus, layer lists, and property tables, not only variables visible in the initial page text.
- For each `variableMeasured`, include `temporalCoverage`. Use the source-supported variable or dataset temporal range when available; otherwise use `Static`.
- For each `variableMeasured`, include `spatialCoverage`. Use variable-specific spatial coverage when available; otherwise use `not detected`.

## Generation Safeguards

- The generation prompt requires separate variable rows, structured citation arrays, exact download targets, and variable-level temporal and spatial coverage fields.
- `generate_jsonld.py` extracts source-page download links, citation text, and variable rows and passes them into the generation prompt.
- `generate_jsonld.py` emits review warnings when generated JSON-LD still contains lumped variable names, omits source-listed variables, lacks variable-level temporal or spatial coverage, contains plain-string citations, or distributions omit exact source-page download links.

## Validation

- Run `python3 scripts/validate_jsonld_batch.py data/objects/summoned/earthface` (and/or `.../generated` when that folder exists).
- Run `git diff --check`.
- Review `git diff` for metadata-only changes and confirm no unrelated files are modified.
