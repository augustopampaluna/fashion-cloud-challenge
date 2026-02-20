from __future__ import annotations
import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

FieldsTuple = Tuple[str, ...]
MappingIndex = Dict[FieldsTuple, Dict[str, Tuple[str, str]]]


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


# CLI.
def parse_args(argv: Optional[List[str]] = None) -> CliArgs:
    """
    CLI Parser.
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

    # 1) Load mappings.
    mappings_idx = load_mappings_index(args.mappings)

    print(mappings_idx)

    # 2) Build catalog,
    # 3) Tests and validations.
    # 4) Generate JSON output.

    return 0


# Execute main.
if __name__ == "__main__":
    raise SystemExit(main())