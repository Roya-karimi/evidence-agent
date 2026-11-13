"""Build data/poe_published/records.csv from the extracted Table 1 of Hofmeister et al. (2025).

Source: Hofmeister RJ et al. Parent-of-origin effects on complex traits in up to 236,781
individuals. Nature (2025). doi:10.1038/s41586-025-09357-5. Licence: CC BY 4.0.
Changes: Table 1 values re-arranged into one row per variant-trait; the published
POE pattern label is kept out of the records so the agent must reason from the estimates.

Run:  python scripts/build_poe_published.py
"""

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "poe_published" / "source" / "hofmeister2025_table1_extracted.csv"
OUT = ROOT / "data" / "poe_published" / "records.csv"

COLUMNS = ["locus_id", "rsid", "locus", "trait", "effect_allele", "other_allele",
           "beta_maternal", "se_maternal", "p_maternal",
           "beta_paternal", "se_paternal", "p_paternal",
           "p_difference", "cov_maternal_paternal", "trait_scale", "source"]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def clean_locus(text: str) -> str:
    return re.sub(r"\s*\(printed.*?\)", "", text).strip()   # Table 1 typo 'KFL14' -> KLF14


def scale(trait: str) -> str:
    if trait == "T2D":
        return "log-odds (binary trait)"
    return "SD of inverse-normal transformed trait"


def main():
    with open(SRC, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    seen = set()
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            record_id = f"{r['variant_rsid']}_{slug(r['trait'])}"
            if record_id in seen:
                raise ValueError(f"Duplicate record {record_id}")
            seen.add(record_id)
            w.writerow({
                "locus_id": record_id,
                "rsid": r["variant_rsid"],
                "locus": clean_locus(r["nearest_gene_locus"]),
                "trait": r["trait"],
                "effect_allele": r["effect_allele"],
                "other_allele": r["other_allele"],
                "beta_maternal": r["beta_maternal"], "se_maternal": r["se_maternal"], "p_maternal": r["p_maternal"],
                "beta_paternal": r["beta_paternal"], "se_paternal": r["se_paternal"], "p_paternal": r["p_paternal"],
                "p_difference": r["p_diff"],
                "cov_maternal_paternal": "",
                "trait_scale": scale(r["trait"]),
                "source": f"Hofmeister et al. 2025, Nature, Table 1 row {r['source_row']}",
            })
    print(f"Wrote {len(seen)} records to {OUT}")


if __name__ == "__main__":
    main()
