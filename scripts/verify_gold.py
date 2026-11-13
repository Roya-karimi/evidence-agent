"""Check every gold verdict with a deterministic implementation of the decision rules.

The model never sees this script. It reads the structured columns of claims.csv
(claim_type, record_ids, parent, allele, direction, value, alpha), computes the
verdict with the same statistical tools the agent uses, and reports any claim
whose gold label disagrees.

Run:  python scripts/verify_gold.py poe_published
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evidence_agent.domains import load_domain  # noqa: E402

S, C, I = "supported", "contradicted", "insufficient_evidence"


def verdict_for_record(rec_id, claim, tools, records):
    if rec_id not in records:
        return I
    t = claim["claim_type"]
    alpha = float(claim["alpha"] or 0.05)
    d = tools["test_parental_difference"](rec_id, alpha=alpha)
    if "error" in d:
        return I
    m, p = d["maternal"], d["paternal"]
    diff_sig = d["difference_significant"]

    if t == "A":
        return S if diff_sig else I
    if t in ("B2", "C2"):              # strict parent-specific (rules v2)
        own, other = (m, p) if t == "B2" else (p, m)
        if diff_sig and own["significant"] and not other["significant"]:
            return S
        if diff_sig and (other["significant"] or abs(other["beta"]) > abs(own["beta"])):
            return C
        return I
    if t == "H":                        # larger effect in the named parent
        own, other = (m, p) if claim["parent"] == "maternal" else (p, m)
        if diff_sig and abs(own["beta"]) > abs(other["beta"]):
            return S
        if diff_sig and abs(other["beta"]) > abs(own["beta"]):
            return C
        return I
    if t in ("B", "C"):
        own, other = (m, p) if t == "B" else (p, m)
        if diff_sig and own["significant"] and abs(own["beta"]) > abs(other["beta"]):
            return S
        if diff_sig and abs(other["beta"]) > abs(own["beta"]):
            return C
        return I
    if t == "D":
        r = records[rec_id]
        effect = m if claim["parent"] == "maternal" else p
        if not claim["allele"] or claim["allele"] == r.get("effect_allele"):
            beta = effect["beta"]
        elif claim["allele"] and claim["allele"] == r.get("other_allele"):
            beta = -effect["beta"]
        else:
            return I
        if not effect["significant"]:
            return I
        claimed_positive = claim["direction"] == "+"
        return S if (beta > 0) == claimed_positive else C
    if t == "E":
        return C if diff_sig else I
    if t == "F":
        if m["significant"] and p["significant"]:
            return S if (m["beta"] > 0) != (p["beta"] > 0) else C
        return I
    if t == "G":
        stored = records[rec_id][f"beta_{claim['parent']}"]
        decimals = len(claim["value"].split(".")[1]) if "." in claim["value"] else 0
        return S if round(stored, decimals) == round(float(claim["value"]), decimals) else C
    if t == "X":            # mechanism / causation
        return I
    raise ValueError(f"Unknown claim type {t}")


def verdict(claim, tools, records):
    ids = [x for x in claim["record_ids"].split(";") if x]
    if not ids:
        return I
    verdicts = [verdict_for_record(i, claim, tools, records) for i in ids]
    if len(verdicts) == 1:
        return verdicts[0]
    if S in verdicts:                       # gene-level: at least one record supports
        return S
    return C if all(v == C for v in verdicts) else I


def main(domain_name: str) -> int:
    domain = load_domain(domain_name)
    tools = {t.name: t.function for t in domain["tools"]}
    with open(domain["claims_path"], newline="", encoding="utf-8") as f:
        claims = list(csv.DictReader(f))
    mismatches = 0
    for c in claims:
        v = verdict(c, tools, domain["records"])
        ok = v == c["gold_verdict"]
        mismatches += not ok
        print(f"[{'ok ' if ok else 'BAD'}] {c['claim_id']} gold={c['gold_verdict']:<22} rules={v}")
    print(f"\n{len(claims) - mismatches}/{len(claims)} gold verdicts reproduced by the rule implementation.")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "poe_published"))
