# JSON-LD Metadata Validation Plan

## Summary

Validate generated JSON-LD against the authoritative dataset webpage, linked download targets, cited papers, and repository or data-release pages. Corrections should be conservative: revise only fields supported by visible source evidence, and leave an inspectable Git diff.

## Manual Checks Added

- Expand source-listed variables into one `variableMeasured` entry per variable. Use the physical variable label as `name` and put short codes such as `bio01`, `tas`, or `lossyear` in `alternateName`.
- Include all citations shown by the source page. When a page has both `Model Citation` and `Data Citation`, represent both as separate structured citation objects.
- Use the exact URL behind a source page's Download button or direct data/API endpoint for `distribution[].contentUrl`; do not use a generic portal root when a more specific target is available.

## Generation Safeguards

- The generation prompt requires separate variable rows, structured citation arrays, and exact download targets.
- `generate_jsonld.py` extracts source-page download links, citation text, and variable rows and passes them into the generation prompt.
- `generate_jsonld.py` emits review warnings when generated JSON-LD still contains lumped variable names, plain-string citations, or distributions that omit exact source-page download links.

## Validation

- Run `python3 scripts/validate_jsonld_batch.py data/objects/summoned/generated`.
- Run `git diff --check`.
- Review `git diff` for metadata-only changes and confirm no unrelated files are modified.
