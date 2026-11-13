"""Load source records (the 'evidence') from CSV files."""

import csv
from pathlib import Path


def _to_number(value: str):
    """Convert a CSV cell to float if possible; empty cells become None (missing)."""
    if value is None or value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return value.strip()


def load_records(path: Path, id_column: str) -> dict:
    """Return {record_id: {field: value}}. Fails loudly on duplicate IDs."""
    records = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            record_id = row[id_column].strip()
            if record_id in records:
                raise ValueError(f"Duplicate id '{record_id}' in {path}")
            records[record_id] = {k: _to_number(v) for k, v in row.items() if k != id_column}
    return records
