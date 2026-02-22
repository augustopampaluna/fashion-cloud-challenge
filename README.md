# Fashion Cloud Coding Challenge

Transforms a `pricat.csv` file into a JSON catalog using `mappings.csv` rules (including combined-field mappings).

## Project structure

```
.
├─ data/
│  ├─ pricat.csv
│  └─ mappings.csv
├─ src/
│  ├─ __init__.py
│  └─ transform.py
└─ tests/
   ├─ __init__.py
   └─ test_transform_unittest.py
```

## Requirements

- Python 3.10+ (no external dependencies)

## Run the transformer

From the project root:

```bash
python -m src.transform --pricat data/pricat.csv --mappings data/mappings.csv --output output.json
```

### Bonus: combine fields

Create a new field by combining existing fields:

```bash
python -m src.transform \
  --pricat data/pricat.csv \
  --mappings data/mappings.csv \
  --output output.json \
  --combine price_buy_net,currency:price_buy_net_currency:" "
```

You can pass `--combine` multiple times.

Format:

```text
--combine field1,field2:new_field:separator
```

Notes:
- `separator` may require quotes in your shell (e.g. `" "`).
- Supports `\t` and `\n` escapes.

## Output format (high level)

```json
{
  "catalog": {
    "brand": "...",
    "articles": [
      {
        "article_number": "...",
        "variations": [
          { "season": "...", "size": "...", "...": "..." }
        ]
      }
    ]
  }
}
```

## Tests

Run all tests:

```bash
python -m unittest -v
```

## Help

```bash
python -m src.transform --help
```

## Implementation notes

- `brand` is stored at catalog level and excluded from each variation.
- Mapping rules from `mappings.csv` are applied first; fields used by combined mappings are not copied as raw fields.
- Known numeric fields (e.g. prices/discount) are converted to `float` when parseable.
