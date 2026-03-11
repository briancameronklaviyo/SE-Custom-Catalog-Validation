"""
Validate XML product feeds using:
1. FIELD_MAP for customer-specific field aliases
2. FIELD_RULES for canonical validation requirements

Supports:
- full catalog validation
- optional single-product validation by ID/SKU/reference

Expects an XML root containing a list of product elements
(e.g. <products><product>...</product></products>).
"""

import xml.etree.ElementTree as ET
from pathlib import Path

# --- set your local file path here ---
xml_path = Path.home() / "Downloads" / "klaviyo_shaneco.xml"

# --- optional: set to a specific ID / SKU / product reference to validate only one product ---
TARGET_PRODUCT_REFERENCE = "41083539"
# Examples:
# TARGET_PRODUCT_REFERENCE = "12345"
# TARGET_PRODUCT_REFERENCE = "ABC-123"


def strip_namespace(tag: str) -> str:
    """Return tag without namespace, e.g. '{http://...}product' -> 'product'."""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def normalize_value(value) -> str:
    """Normalize values for validation/logging/filtering."""
    if value is None:
        return ""
    return str(value).strip()


def element_to_row(element: ET.Element) -> dict:
    """
    Convert an XML element to a flat dict: child tag name (no namespace) -> text content.
    Uses first direct child only for repeated tags; strips whitespace from text.
    Also includes attributes as keys.
    """
    row = {}

    for child in element:
        key = strip_namespace(child.tag)
        text = normalize_value(child.text)

        # Prefer direct text; for elements with nested structure, join all text
        if not text and len(child):
            text = normalize_value(" ".join(child.itertext()))

        if key:
            row[key] = text

    # Include attributes too (e.g. id="123")
    for name, value in element.attrib.items():
        row[strip_namespace(name)] = normalize_value(value)

    return row


def load_xml(path: Path) -> ET.Element:
    if not path.exists():
        raise FileNotFoundError(f"XML file not found: {path}")
    with path.open("rb") as f:
        tree = ET.parse(f)
    return tree.getroot()


# --- FIELD MAP: canonical field -> allowed customer aliases in the feed ---
FIELD_MAP = {
    "id": {"id", "$id"},
    "title": {"title", "$title"},
    "description": {"description", "$description"},
    "link": {"url", "link", "$link"},
    "image_link": {"image_url", "image_link", "$image_link"},
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

# --- Config: name of the repeating product element ---
PRODUCT_TAG = "Product"  # or "item", "entry", etc.


def get_product_elements(root: ET.Element) -> list[ET.Element]:
    """
    Get list of product elements. Handles:
    - Root is already the list container: <products><product>...</product></products>
    - Root is the container itself with product children
    - Root is a single product
    """
    root_tag = strip_namespace(root.tag)

    if root_tag in ("products", "items", "feed", "channel", "catalog", "root"):
        return [el for el in root if strip_namespace(el.tag) == PRODUCT_TAG]

    if root_tag == PRODUCT_TAG:
        return [root]

    return [el for el in root if strip_namespace(el.tag) == PRODUCT_TAG]


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

    # Check canonical id first
    _, id_value = resolve_field_value(row, "id")
    if id_value == target_reference:
        return True

    # Check common fallback aliases
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
    print(f"Validating: {xml_path}", flush=True)

    if TARGET_PRODUCT_REFERENCE is not None:
        print(f"Mode: single-product validation for reference={TARGET_PRODUCT_REFERENCE!r}", flush=True)
    else:
        print("Mode: full catalog validation", flush=True)

    if not xml_path.exists():
        print(f"ERROR: File not found: {xml_path}", flush=True)
        return

    root = load_xml(xml_path)
    product_elements = get_product_elements(root)

    print(
        f"Root tag: '{strip_namespace(root.tag)}', "
        f"found {len(product_elements)} <{PRODUCT_TAG}> element(s)",
        flush=True,
    )

    if not product_elements:
        print(
            f"ERROR: No <{PRODUCT_TAG}> elements found. "
            f"Root has {len(root)} children (tags: {[strip_namespace(c.tag) for c in list(root)[:10]]}). "
            f"If your product tag is different, set PRODUCT_TAG at the top of the script.",
            flush=True,
        )
        return

    good_count = 0
    bad_count = 0
    checked_count = 0
    matched_target_count = 0
    bad_examples_printed = 0
    MAX_BAD_EXAMPLES = 5
    issue_summary = {}

    for i, el in enumerate(product_elements, start=1):
        row = element_to_row(el)

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
                    f"\nMatched row #{i} (element <{strip_namespace(el.tag)}>, "
                    f"{ref_label}={ref_value!r}) is valid."
                )
        else:
            bad_count += 1

            for err in result["errors"]:
                key = (err["field"], err["type"])
                issue_summary[key] = issue_summary.get(key, 0) + 1

            if bad_examples_printed < MAX_BAD_EXAMPLES:
                ref_label, ref_value = get_reference_id(row)

                print(
                    f"\nRow #{i} (element <{strip_namespace(el.tag)}>, "
                    f"{ref_label}={ref_value!r}) failed validation:"
                )

                for err in result["errors"]:
                    print(f"  - {err['field']} [{err['type']}]: {err['message']}")
                    print(f"    accepted aliases: {err['aliases']}")
                    if err["found_alias"] is not None:
                        print(f"    matched alias: {err['found_alias']!r}")
                        print(f"    value: {err['value']!r}")

                print(
                    f"  Present keys: {sorted(row.keys())[:30]}"
                    f"{'...' if len(row) > 30 else ''}"
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
    print(f"total products in feed: {len(product_elements)}", flush=True)

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