"""Domain settings: where the evidence lives, which tools apply, which rules decide.

To add a domain: add a folder under data/ with records.csv, rules.md and
claims.csv, write its tools in tools.py, and register it here.
"""

from pathlib import Path

from .data import load_records
from .tools import energy_tools, poe_tools

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

DOMAINS = {
    "poe": {"id_column": "locus_id", "tools": poe_tools},
    "poe_published": {"id_column": "locus_id", "tools": poe_tools},
    "poe_published_v2": {"id_column": "locus_id", "tools": poe_tools, "records_from": "poe_published"},
    "energy": {"id_column": "record_id", "tools": energy_tools},
}


def load_domain(name: str, system: str = "v1") -> dict:
    if name not in DOMAINS:
        raise ValueError(f"Unknown domain '{name}'. Options: {sorted(DOMAINS)}")
    cfg = DOMAINS[name]
    if system not in ("v1", "v2"):
        raise ValueError("system must be 'v1' or 'v2'")
    folder = DATA / name
    records = load_records(DATA / cfg.get("records_from", name) / "records.csv", cfg["id_column"])
    tools = cfg["tools"](records, system) if cfg["tools"] is poe_tools else cfg["tools"](records)
    return {
        "name": name,
        "system": system,
        "records": records,
        "tools": tools,
        "rules": (folder / "rules.md").read_text(encoding="utf-8"),
        "claims_path": folder / "claims.csv",
    }
