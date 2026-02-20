from __future__ import annotations
import csv
from typing import Dict, Iterable


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
