"""
Count inventory policy values in an XML product feed.

Expects an XML root containing a list of product elements
(e.g. <products><Product>...</Product></products>).
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter

# --- set your local file path here ---
xml_path = Path.home() / "Downloads" / "klaviyo_shaneco.xml"


def strip_namespace(tag: str) -> str:
    """Return tag without namespace, e.g. '{http://...}Product' -> 'Product'."""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def element_to_row(element: ET.Element) -> dict:
    """
    Convert an XML element to a flat dict: child tag name (no namespace) -> text content.
    Uses first direct child only for repeated tags; strips whitespace from text.
    Also includes element attributes as keys.
    """
    row = {}
    for child in element:
        key = strip_namespace(child.tag)
        text = (child.text or "").strip()
        if not text and len(child):
            text = " ".join(child.itertext()).strip()
        if key:
            row[key] = text

    for name, value in element.attrib.items():
        row[strip_namespace(name)] = (value or "").strip()

    return row


def load_xml(path: Path) -> ET.Element:
    if not path.exists():
        raise FileNotFoundError(f"XML file not found: {path}")
    with path.open("rb") as f:
        tree = ET.parse(f)
    return tree.getroot()


# --- Config: name of the repeating product element ---
PRODUCT_TAG = "Product"  # change if needed


def get_product_elements(root: ET.Element) -> list[ET.Element]:
    """
    Get list of product elements. Handles:
    - Root is a container: <products><Product>...</Product></products>
    - Root is itself a single product
    - Root has direct product children
    """
    root_tag = strip_namespace(root.tag)

    if root_tag in ("products", "items", "feed", "channel", "catalog", "root"):
        return [el for el in root if strip_namespace(el.tag) == PRODUCT_TAG]

    if root_tag == PRODUCT_TAG:
        return [root]

    return [el for el in root if strip_namespace(el.tag) == PRODUCT_TAG]


# --- Possible field names for inventory policy ---
INVENTORY_POLICY_ALIASES = {
    "inventory_policy",
    "inventoryPolicy",
    "InventoryPolicy",
    "inventory-policy",
    "$inventory_policy",
}


def get_inventory_policy(row: dict) -> str | None:
    """Return the inventory policy value if present, otherwise None."""
    for alias in INVENTORY_POLICY_ALIASES:
        if alias in row and row[alias] != "":
            return row[alias].strip()
    return None


def main():
    print(f"Checking inventory policy counts in: {xml_path}", flush=True)

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

    policy_counts = Counter()
    missing_policy = 0

    for el in product_elements:
        row = element_to_row(el)
        policy = get_inventory_policy(row)

        if policy is None:
            missing_policy += 1
            continue

        policy_counts[policy] += 1

    print("\nInventory policy counts:", flush=True)
    print(f"policy 1: {policy_counts.get('1', 0)}", flush=True)
    print(f"policy 2: {policy_counts.get('2', 0)}", flush=True)
    print(f"missing inventory policy: {missing_policy}", flush=True)
    print(f"total products: {len(product_elements)}", flush=True)

    other_values = {
        k: v for k, v in policy_counts.items() if k not in {"1", "2"}
    }
    if other_values:
        print("\nOther inventory policy values found:", flush=True)
        for value, count in sorted(other_values.items()):
            print(f"  {value}: {count}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        raise