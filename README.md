# Catalog Feed Validators

These scripts validate **custom catalog feeds** to ensure required fields exist and contain valid values.

They support:

- XML product feeds
- JSON product feeds
- full catalog validation
- single product validation for debugging

Both scripts use the same configuration model so validation rules remain consistent.

---

# Scripts

| Script | Purpose |
|------|------|
| `validate_catalog_xml.py` | Validate XML catalog feeds |
| `validate_catalog_json.py` | Validate JSON catalog feeds |

Both scripts validate products using:

- **FIELD_MAP** → maps customer feed fields to canonical validator fields  
- **FIELD_RULES** → validation rules for those canonical fields

---

# What the Validators Check

Each product is validated against canonical fields:

- `id`
- `title`
- `description`
- `link`
- `image_link`

For each field the validator:

1. looks for matching feed fields using `FIELD_MAP`
2. validates the value using `FIELD_RULES`

### Example validation checks

- required field exists
- field value is not blank
- field meets minimum length

---

# Required Setup Before Running

Before using the scripts you must review these configuration sections.

| Setting | Required | Description |
|------|------|------|
| file path | ✅ | location of feed file |
| FIELD_MAP | ✅ | maps customer field names |
| PRODUCT_TAG (XML only) | sometimes | defines product element |
| FIELD_RULES | optional | validation constraints |
| TARGET_PRODUCT_REFERENCE | optional | validate a single product |

---

# 1. Set the Feed File Path

## XML Validator

Update:

```python
xml_path = Path.home() / "Downloads" / "feed.xml"
```

Example:

```python
xml_path = Path.home() / "Downloads" / "customer_catalog.xml"
```

Or use a full path:

```python
xml_path = Path("/Users/username/Desktop/catalog.xml")
```

---

## JSON Validator

Update:

```python
json_path = Path.home() / "Downloads" / "feed.json"
```

Example:

```python
json_path = Path.home() / "Downloads" / "customer_catalog.json"
```

---

# 2. Configure the Field Mapping

`FIELD_MAP` maps **customer field names → canonical validator fields**.

Example default mapping:

```python
FIELD_MAP = {
    "id": {"id", "$id"},
    "title": {"title", "$title"},
    "description": {"description", "$description"},
    "link": {"url", "link", "$link"},
    "image_link": {"image_url", "image_link", "$image_link"},
}
```

This means the validator will accept **any of those aliases**.

---

## Example Customer Feed

Example XML or JSON product:

```json
{
  "product_id": "123",
  "name": "Gold Ring",
  "desc": "14k gold ring",
  "product_url": "https://example.com/ring",
  "main_image": "https://example.com/ring.jpg"
}
```

Update `FIELD_MAP` like this:

```python
FIELD_MAP = {
    "id": {"product_id"},
    "title": {"name"},
    "description": {"desc"},
    "link": {"product_url"},
    "image_link": {"main_image"},
}
```

---

## Multiple Accepted Aliases

You can include multiple field names:

```python
FIELD_MAP = {
    "id": {"id", "product_id", "SKU"},
    "title": {"title", "name", "ProductName"},
    "description": {"description", "desc"},
    "link": {"link", "url", "ProductLink"},
    "image_link": {"image_link", "ImageUrl", "main_image"},
}
```

---

# 3. Configure Validation Rules

Validation rules are defined in:

```python
FIELD_RULES
```

Example:

```python
FIELD_RULES = {
    "id": {"required": True, "min_len": 1},
    "title": {"required": True, "min_len": 1},
    "description": {"required": True, "min_len": 1},
    "link": {"required": True, "min_len": 1},
    "image_link": {"required": True, "min_len": 1},
}
```

### Supported Rules

| Rule | Description |
|-----|-------------|
|required| field must exist |
|min_len| minimum character length |

Example stricter rule:

```python
"title": {"required": True, "min_len": 5}
```

---

# 4. Validate a Single Product (Optional)

You can validate **one product instead of the full feed**.

Update:

```python
TARGET_PRODUCT_REFERENCE = None
```

### Validate entire feed

```python
TARGET_PRODUCT_REFERENCE = None
```

### Validate one product

```python
TARGET_PRODUCT_REFERENCE = "12345"
```

or

```python
TARGET_PRODUCT_REFERENCE = "ABC-123"
```

The validator will attempt to match this value against:

- canonical `id`
- `sku`
- `SKU`
- `product_id`
- `item_id`
- `item_group_id`

---

# 5. XML Only: Set Product Tag

XML feeds may use different element names for products.

Update:

```python
PRODUCT_TAG = "Product"
```

Examples:

```
<Product>
<product>
<item>
<entry>
```

Example configuration:

```python
PRODUCT_TAG = "item"
```

If this is incorrect, the script may report **zero products found**.

---

# 6. Expected Feed Formats

## XML Feed

Example structure:

```xml
<products>
  <Product>
    <id>123</id>
    <title>Example Product</title>
  </Product>
</products>
```

Or:

```xml
<feed>
  <item>
    ...
  </item>
</feed>
```

---

## JSON Feed

JSON must contain a **list of products at the root**.

Example:

```json
[
  {
    "id": "123",
    "title": "Example Product"
  },
  {
    "id": "456",
    "title": "Another Product"
  }
]
```

If your file looks like:

```json
{
  "products": [...]
}
```

Update the script to use:

```python
data = data["products"]
```

---

# 7. Running the Validators

## XML

```bash
python validate_catalog_xml.py
```

## JSON

```bash
python validate_catalog_json.py
```

---

# Example Output

## Full Feed Validation

```
Validating: /Users/you/Downloads/feed.xml
Mode: full catalog validation

Root tag: 'products', found 1200 <Product> elements

good rows: 1185
bad rows: 15
total products: 1200
```

---

## Single Product Validation

```
Mode: single-product validation for reference='ABC-123'

Matched row #42 (SKU='ABC-123') is valid.

checked rows: 1
good rows: 1
bad rows: 0
```

---

## Example Validation Failure

```
Row #12 (element <Product>, sku='ABC-123') failed validation:

- title [min_len]
- image_link [missing_required]

Present keys: ['sku','name','desc','product_url']
```

JSON version looks similar:

```
Row #12 (SKU='ABC-123') failed validation:
- title [min_len]
```

---

# Troubleshooting

## No products detected (XML)

Check:

- `PRODUCT_TAG`
- XML structure
- feed path

---

## Required fields missing

Check:

- `FIELD_MAP`
- fields exist in feed
- values are not blank

---

## JSON validator error: root is not list

If feed looks like:

```json
{"products": [...]}
```

Add:

```python
data = data["products"]
```

---

# Typical Workflow

1. Download catalog feed
2. Set the correct file path
3. Inspect one product
4. Update `FIELD_MAP`
5. For XML feeds confirm `PRODUCT_TAG`
6. Run validator
7. Use `TARGET_PRODUCT_REFERENCE` to debug specific products

---

# Future Enhancements

These validators are structured so new rules can be added easily, such as:

- duplicate product ID detection
- URL validation
- inventory policy validation
- price validation
- image availability checks
- CSV/JSON validation reports

Because both scripts share the same `FIELD_MAP` and `FIELD_RULES` structure, new validations can be added consistently across XML and JSON.