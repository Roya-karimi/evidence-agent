"""Review a list of draft statements against one results table.

The researcher supplies a CSV of estimates and a text file with one statement per
line. Each statement goes through the agent loop. The output is a table with the
statement, the finding, a short explanation, the source rows and values that were
used, and a suggested action.

The model reads the sentence and chooses the checks. Python looks up the values,
does the calculations, fills in the source column from the table itself, and
chooses the action from a fixed list.
"""

import csv
from pathlib import Path

from .agent import run_agent
from .data import load_records
from .domains import DATA
from .tools import poe_tools

REQUIRED_COLUMNS = ["locus_id", "trait", "beta_maternal", "se_maternal", "beta_paternal", "se_paternal"]
RULES_PATH = DATA / "review" / "rules.md"

FINDINGS = {"supported": "Supported", "contradicted": "Contradicted",
            "insufficient_evidence": "Insufficient evidence", None: "Not checked"}

ACTIONS = {
    ("contradicted", "quoted_number"): "Correct the number. The source value is in the Source column.",
    ("contradicted", "effect_direction"): "Check the direction of the effect and which allele it refers to.",
    ("contradicted", "significance"): "Revise the significance wording. The reported p-value does not meet the stated threshold.",
    ("contradicted", "parental_difference"): "Revise the parent-of-origin wording. The source shows a different pattern.",
    ("insufficient_evidence", "quoted_number"): "The value could not be confirmed. Check it against the source table.",
    ("insufficient_evidence", "effect_direction"): "Check the allele and the wording. The effect is not significant, "
                                                   "or the source does not record the allele named.",
    ("insufficient_evidence", "significance"): "Check the significance wording. The table cannot confirm it.",
    ("insufficient_evidence", "parental_difference"): "Soften the parent-of-origin wording. The table does not establish it.",
    ("insufficient_evidence", "interpretation"): "The interpretation goes beyond the table. Keep it for human review.",
}
NO_ACTION = "No change needed."
NO_SOURCE_ROW = "No matching row was found. Check the variant ID and the trait name."
REVIEW_BY_HAND = "Review the statement against the source by hand."
CHECK_FAILED = "The checker did not reach a verdict. Check this statement by hand."


def load_review_domain(records_path: Path) -> dict:
    """A domain built from the researcher's own table, using the review rules and system v2."""
    records_path = Path(records_path)
    with open(records_path, newline="", encoding="utf-8-sig") as f:
        header = next(csv.reader(f), [])
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise ValueError(f"{records_path} is missing required column(s): {missing}. "
                         "See data/poe_published/records.csv for the expected layout.")
    records = load_records(records_path, "locus_id")
    rules = RULES_PATH.read_text(encoding="utf-8")
    return {"name": "review", "system": "v2", "review": True, "records": records,
            "tools": poe_tools(records, "v2"), "rules": rules,
            "rules_path": RULES_PATH, "records_path": records_path}


def read_statements(path: Path) -> list:
    """One statement per line. Blank lines and lines starting with # are skipped."""
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def _number(value) -> str:
    return f"{value:g}" if isinstance(value, float) else str(value)


def source_text(evidence_ids: list, records: dict) -> str:
    """The cited rows and their values, read from the table (not from the model's text)."""
    parts = []
    for rid in evidence_ids:
        r = records.get(rid)
        if r is None:
            continue
        bits = []
        for parent in ("maternal", "paternal"):
            if r.get(f"beta_{parent}") is None:
                bits.append(f"{parent} estimate missing")
                continue
            p = f", P {_number(r[f'p_{parent}'])}" if r.get(f"p_{parent}") is not None else ""
            bits.append(f"{parent} {_number(r[f'beta_{parent}'])} (SE {_number(r[f'se_{parent}'])}{p})")
        if r.get("p_difference") is not None:
            bits.append(f"difference P {_number(r['p_difference'])}")
        allele = f", effect allele {r['effect_allele']}" if r.get("effect_allele") else ""
        parts.append(f"{rid} ({r.get('trait')}{allele}): " + "; ".join(bits))
    return " / ".join(parts) or "No source row used."


def action_for(result: dict, records: dict) -> str:
    """A suggested next step, chosen from a fixed list."""
    verdict, check_type = result.get("verdict"), result.get("check_type")
    if result.get("status") != "ok":
        return CHECK_FAILED
    if verdict == "supported":
        return NO_ACTION
    if verdict == "insufficient_evidence" and check_type != "interpretation" \
            and not any(i in records for i in result.get("evidence_ids", [])):
        return NO_SOURCE_ROW
    return ACTIONS.get((verdict, check_type), REVIEW_BY_HAND)


def review_statements(statements: list, domain: dict, llm) -> list:
    rows = []
    for number, statement in enumerate(statements, start=1):
        result = run_agent(statement, domain, llm, mode="agent")
        rows.append({"number": number, "statement": statement,
                     "finding": FINDINGS.get(result["verdict"], "Not checked"),
                     "explanation": result["explanation"] or (result.get("error") or ""),
                     "source": source_text(result["evidence_ids"], domain["records"]),
                     "action": action_for(result, domain["records"]),
                     "result": result})
    return rows


COLUMNS = [("number", "#"), ("statement", "Statement"), ("finding", "Finding"), ("explanation", "Why"),
           ("source", "Source rows and values"), ("action", "What to do")]


def _cell(value) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def to_markdown(rows: list, title: str = "Statement review") -> str:
    flagged = sum(r["finding"] != "Supported" for r in rows)
    lines = [f"# {title}", "",
             f"{len(rows)} statement(s) checked, {flagged} flagged for attention.", "",
             "| " + " | ".join(label for _, label in COLUMNS) + " |",
             "|" + " --- |" * len(COLUMNS)]
    lines += ["| " + " | ".join(_cell(r[key]) for key, _ in COLUMNS) + " |" for r in rows]
    lines += ["", "The findings follow written decision rules and are a prompt for review, not a judgement on "
                  "the science. Statements about mechanism or interpretation are left for the researcher."]
    return "\n".join(lines) + "\n"


def write_csv(rows: list, path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["number", "statement", "verdict", "check_type", "explanation", "evidence_ids",
                         "source", "action", "status", "seconds"])
        for r in rows:
            res = r["result"]
            writer.writerow([r["number"], r["statement"], res["verdict"] or "", res.get("check_type") or "",
                             r["explanation"], ";".join(res["evidence_ids"]), r["source"], r["action"],
                             res["status"], res["seconds"]])
