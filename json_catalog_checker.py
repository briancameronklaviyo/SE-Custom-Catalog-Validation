import json
from pathlib import Path

# --- set your local file path here ---
json_path = Path.home() / "Downloads" / "klaviyo_rvtest.json"

# --- optional: set to a specific ID / SKU / product reference to validate only one product ---
TARGET_PRODUCT_REFERENCE = None
# Examples:
# TARGET_PRODUCT_REFERENCE = "12345"
# TARGET_PRODUCT_REFERENCE = "ABC-123"


def normalize_value(value) -> str:
    """Normalize values for validation/logging/filtering."""
    if value is None:
        return ""
    return str(value).strip()


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    # utf-8-sig handles BOM if present
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


# --- FIELD MAP: canonical field -> allowed customer aliases in the feed ---
FIELD_MAP = {
    "id": {"$id", "id", "SKU"},
    "title": {"$title", "title", "ProductName"},
    "description": {"$description", "description"},
    "link": {"$link", "link", "ProductLink"},
    "image_link": {"$image_link", "image_link", "ImageUrl"},
}

# --- FIELD RULES: canonical field -> validation rules ---
FIELD_RULES = {
    "id": {"required": True, "min_len": 1},
    "title": {"required": True, "min_len": 1},
    "description": {"required": True, "min_len": 1},
    "link": {"required": True, "min_len": 1},
    "image_link": {"required": True, "min_len": 1},
}

# --- Optional fallback aliases for logging/debugging row identity ---
REFERENCE_ID_ALIASES = [
    "sku",
    "SKU",
    "product_id",
    "productid",
    "item_group_id",
    "item_id",
]


def resolve_field_value(row: dict, canonical_field: str) -> tuple[str | None, str]:
    """
    Resolve a canonical field to the first matching alias in the row.

    Returns:
        (matched_alias, normalized_value)

    If no alias is found:
        (None, "")
    """
    aliases = FIELD_MAP.get(canonical_field, set())

    for alias in aliases:
        if alias in row:
            return alias, normalize_value(row.get(alias))

    return None, ""


def get_reference_id(row: dict) -> tuple[str, str]:
    """
    Try to find a useful row identifier for logging.

    Priority:
    1. Resolved canonical 'id' via FIELD_MAP
    2. Common fallback fields like sku/product_id
    3. '<unknown>'

    Returns:
        (label, value)
    """
    found_alias, value = resolve_field_value(row, "id")
    if found_alias is not None and value:
        return found_alias, value

    for alias in REFERENCE_ID_ALIASES:
        if alias in row:
            fallback_value = normalize_value(row.get(alias))
            if fallback_value:
                return alias, fallback_value

    return "reference", "<unknown>"


def row_matches_target(row: dict, target_reference: str | None) -> bool:
    """
    Return True if this row should be validated.

    If target_reference is None, all rows match.
    Otherwise match against:
    1. canonical id value
    2. fallback reference aliases (sku, product_id, etc.)
    """
    if target_reference is None:
        return True

    target_reference = normalize_value(target_reference)

    _, id_value = resolve_field_value(row, "id")
    if id_value == target_reference:
        return True

    for alias in REFERENCE_ID_ALIASES:
        if normalize_value(row.get(alias)) == target_reference:
            return True

    return False


def validate_row(row: dict) -> dict:
    """
    Validate a row using FIELD_MAP + FIELD_RULES.

    Returns:
        {
            "is_valid": bool,
            "errors": [
                {
                    "field": canonical field,
                    "type": "missing_required" | "min_len",
                    "message": str,
                    "aliases": list[str],
                    "found_alias": str | None,
                    "value": str,
                }
            ]
        }
    """
    errors = []

    for canonical_field, rules in FIELD_RULES.items():
        required = rules.get("required", False)
        min_len = rules.get("min_len")
        aliases = sorted(FIELD_MAP.get(canonical_field, set()))

        found_alias, value = resolve_field_value(row, canonical_field)

        if found_alias is None:
            if required:
                errors.append({
                    "field": canonical_field,
                    "type": "missing_required",
                    "message": f"Missing required field '{canonical_field}'",
                    "aliases": aliases,
                    "found_alias": None,
                    "value": "",
                })
            continue

        if min_len is not None and len(value) < min_len:
            errors.append({
                "field": canonical_field,
                "type": "min_len",
                "message": (
                    f"Field '{canonical_field}' was found as '{found_alias}' "
                    f"but value length {len(value)} is less than min_len={min_len}"
                ),
                "aliases": aliases,
                "found_alias": found_alias,
                "value": value,
            })

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
    }


def main():
    print(f"Validating: {json_path}", flush=True)

    if TARGET_PRODUCT_REFERENCE is not None:
        print(f"Mode: single-product validation for reference={TARGET_PRODUCT_REFERENCE!r}", flush=True)
    else:
        print("Mode: full catalog validation", flush=True)

    data = load_json(json_path)

    # Expect root JSON to be a list of product dicts
    if not isinstance(data, list):
        raise TypeError(
            f"Expected the JSON root to be a list of products, but got: {type(data).__name__}.\n"
            "If your file is shaped like {'products': [...]}, update the script to use data['products']."
        )

    good_count = 0
    bad_count = 0
    checked_count = 0
    matched_target_count = 0
    bad_examples_printed = 0
    MAX_BAD_EXAMPLES = 5
    issue_summary = {}

    for i, row in enumerate(data, start=1):
        if not isinstance(row, dict):
            if TARGET_PRODUCT_REFERENCE is None:
                bad_count += 1
                checked_count += 1
                if bad_examples_printed < MAX_BAD_EXAMPLES:
                    print(
                        f"\nRow #{i} is not an object/dict "
                        f"(type={type(row).__name__}). Value: {row!r}"
                    )
                    bad_examples_printed += 1
            continue

        if not row_matches_target(row, TARGET_PRODUCT_REFERENCE):
            continue

        matched_target_count += 1
        checked_count += 1

        result = validate_row(row)

        if result["is_valid"]:
            good_count += 1

            if TARGET_PRODUCT_REFERENCE is not None:
                ref_label, ref_value = get_reference_id(row)
                print(
                    f"\nMatched row #{i} ({ref_label}={ref_value!r}) is valid.",
                    flush=True,
                )
        else:
            bad_count += 1

            for err in result["errors"]:
                key = (err["field"], err["type"])
                issue_summary[key] = issue_summary.get(key, 0) + 1

            if bad_examples_printed < MAX_BAD_EXAMPLES:
                ref_label, ref_value = get_reference_id(row)

                print(f"\nRow #{i} ({ref_label}={ref_value!r}) failed validation:")

                for err in result["errors"]:
                    print(f"  - {err['field']} [{err['type']}]: {err['message']}")
                    print(f"    accepted aliases: {err['aliases']}")
                    if err["found_alias"] is not None:
                        print(f"    matched alias: {err['found_alias']!r}")
                        print(f"    value: {err['value']!r}")

                print(
                    f"  Present keys: {sorted(row.keys())[:30]}"
                    f"{'...' if len(row.keys()) > 30 else ''}"
                )
                bad_examples_printed += 1

    if TARGET_PRODUCT_REFERENCE is not None and matched_target_count == 0:
        print(
            f"\nNo product matched TARGET_PRODUCT_REFERENCE={TARGET_PRODUCT_REFERENCE!r}.",
            flush=True,
        )

    print(f"\nchecked rows: {checked_count}", flush=True)
    print(f"good rows: {good_count}", flush=True)
    print(f"bad rows: {bad_count}", flush=True)
    print(f"total products in feed: {len(data)}", flush=True)

    if issue_summary:
        print("\nIssue summary:", flush=True)
        for (field, error_type), count in sorted(issue_summary.items()):
            print(f"  - {field} [{error_type}]: {count}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        raise