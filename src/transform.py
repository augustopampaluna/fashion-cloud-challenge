from __future__ import annotations
import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


FieldsTuple = Tuple[str, ...]
MappingIndex = Dict[FieldsTuple, Dict[str, Tuple[str, str]]]
NUMERIC_FIELDS = {"price_buy_net", "price_buy_gross", "price_sell", "discount_rate"}


@dataclass(frozen=True)
class CliArgs:
    pricat: str
    mappings: str
    output: str


# Read CSV.
def read_csv_rows(path: str, delimiter: str = ";") -> Iterable[Dict[str, str]]:
    """
    Read the CSV and return a dict-iterator.
    """
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)

        if reader.fieldnames is None:
            raise ValueError(f"No headers: {path}")  # Validation: columns exist.

        for row in reader:
            yield {k: (v if v is not None else "") for k, v in row.items()}  # yield to return iterator.


# Mapping index.
def load_mappings_index(mappings_csv_path: str) -> MappingIndex:
    idx: MappingIndex = defaultdict(dict)

    for r in read_csv_rows(mappings_csv_path, delimiter=";"):
        source_type_raw = r.get("source_type", "").strip()
        source = r.get("source", "").strip()
        dest_type = r.get("destination_type", "").strip()
        dest_value = r.get("destination", "").strip()

        if not source_type_raw or not dest_type:  # Validation.
            raise ValueError(f"Mapping row invalid (source_type/destination_type empty): {r}")

        fields: FieldsTuple = tuple(part.strip() for part in source_type_raw.split("|") if part.strip())
        if not fields:
            raise ValueError(f"Mapping row invalid (empty fields): {r}")  # Validation.

        idx[fields][source] = (dest_type, dest_value)

    return idx


# Transformer: pricat row to variation.
def row_to_variation(row: Dict[str, str], mappings_idx: MappingIndex) -> Dict[str, str]:
    """
    - applies all mapping rules (including combined-field mappings).
    - copies the remaining fields "as is" (except for brand).
    - avoids copying fields that were "consumed" by combined mappings.
    - converts known numeric fields to float.

    Returns a dict representing one variation.
    """

    variation: Dict[str, str] = {}  # Base.
    consumed_input_fields = set()  # Save used inputs to avoid duplications.

    # Apply mappings:
    for fields_tuple, table in mappings_idx.items():
        # Get values for each field from the row (if missing, then "")
        values = [row.get(field_name, "") for field_name in fields_tuple]
        joined = "|".join(values)

        # Exact lookup against source.
        hit = table.get(joined)
        if hit is None:
            continue

        dest_type, dest_value = hit

        # If multiple rules write the same destination_type, the last one would win.
        variation[dest_type] = dest_value  # Write the output field.

        # Mark input fields as consumed.
        for f in fields_tuple:
            consumed_input_fields.add(f)

    # Copy the rest of the fields.
    for k, v in row.items():
        if k == "brand":  # brand belongs to catalog level, not variation.
            continue
        if k in consumed_input_fields:  # don't copy inputs that were already used by mappings.
            continue
        if v == "" or v is None:  # skip empties.
            continue

        # Convert numeric fields (prices, discount) to float when possible.
        if k in NUMERIC_FIELDS:
            try:
                variation[k] = float(v)
            except ValueError:
                variation[k] = v
            continue

        variation[k] = v  # Copy the raw field.

    return variation


# Generate catalog by articles.
def build_catalog_from_pricat(pricat_csv_path: str, mappings_idx: MappingIndex) -> Tuple[Dict, int]:
    """
    Generate final JSON + return total of processed rows.
    """
    articles_by_number: Dict[str, Dict] = {}
    catalog_brand: Optional[str] = None
    rows_processed = 0

    for row in read_csv_rows(pricat_csv_path, delimiter=";"):
        rows_processed += 1
        row_brand = row.get("brand", "")

        if catalog_brand is None:
            catalog_brand = row_brand
        else:
            # It assumes the brand is the same for all rows.
            if row_brand != catalog_brand:
                raise ValueError(
                    f"Inconsistent brand in pricat: catalog_brand='{catalog_brand}' vs row_brand='{row_brand}'"
                )  # Validation.

        # Group by article_number.
        article_number = row.get("article_number", "")
        if not article_number:
            raise ValueError(f"pricat row without article_number: {row}")  # Validation.

        # Row -> variation.
        variation = row_to_variation(row, mappings_idx)

        # Create article if it doesn't exist.
        if article_number not in articles_by_number:
            articles_by_number[article_number] = {
                "article_number": article_number,
                "variations": [],
            }

        # Add variations.
        articles_by_number[article_number]["variations"].append(variation)

    # If the CSV is empty, catalog_brand is None.
    if catalog_brand is None:
        catalog_brand = ""

    articles_list = list(articles_by_number.values())  # article dict to list.

    # Final structure.
    result = {
        "catalog": {
            "brand": catalog_brand,
            "articles": articles_list,
        }
    }

    return result, rows_processed


# Validations.
def basic_validations(result: Dict, rows_processed: int) -> None:
    """
    - All rows were processed.
    - JSON structure.
    """

    # Structure.
    if "catalog" not in result:
        raise AssertionError("JSON has no 'catalog' key")
    if "articles" not in result["catalog"]:
        raise AssertionError("JSON has no 'catalog.articles'")
    if not isinstance(result["catalog"]["articles"], list):
        raise AssertionError("'catalog.articles' is not a list.")

    # Variations counting.
    total_variations = 0
    for article in result["catalog"]["articles"]:
        vars_list = article.get("variations", [])
        if not isinstance(vars_list, list):
            raise AssertionError("Some 'article.variations' are not a list.")
        total_variations += len(vars_list)

    if total_variations != rows_processed:
        raise AssertionError(
            f"Mismatch rows vs variations: rows_processed={rows_processed}, total_variations={total_variations}"
        )


# CLI.
def parse_args(argv: Optional[List[str]] = None) -> CliArgs:
    """
    Parser.
    """
    parser = argparse.ArgumentParser(
        prog="python -m src.transform",
        description="Transform pricat.csv + mappings.csv in a JSON grouped by article..",
    )
    parser.add_argument("--pricat", required=True, help="pricat.csv path (delimiter ';')")
    parser.add_argument("--mappings", required=True, help="mappings.csv path (delimiter ';')")
    parser.add_argument("--output", required=True, help="JSON output path.")

    ns = parser.parse_args(argv)
    return CliArgs(pricat=ns.pricat, mappings=ns.mappings, output=ns.output)


# Main.
def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    # Paths validation.
    if not Path(args.pricat).exists():
        print(f"ERROR: It doesn't exist, --pricat: {args.pricat}", file=sys.stderr)
        return 2
    if not Path(args.mappings).exists():
        print(f"ERROR: It doesn't exist, --mappings: {args.mappings}", file=sys.stderr)
        return 2

    # 1) Load mappings.
    mappings_idx = load_mappings_index(args.mappings)

    # 2) Build catalog.
    result, rows_processed = build_catalog_from_pricat(args.pricat, mappings_idx)

    # 3) Basic validations.
    basic_validations(result, rows_processed)

    # 4) Generate JSON output.
    out_path = Path(args.output)

    if out_path.parent and not out_path.parent.exists():
        out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())