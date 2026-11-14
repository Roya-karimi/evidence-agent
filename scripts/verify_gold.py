"""Check every gold verdict with a deterministic implementation of the decision rules.

The model never sees this script. It reads the structured columns of claims.csv
(claim_type, record_ids, parent, allele, direction, value, alpha), computes the
verdict with the same statistical tools the agent uses, and reports any claim
whose gold label disagrees.

The parent-specific rules (B2, C2) and the magnitude rule (H) are the corrected
version 2.1 rules. Types B and C are the version 1 rules exactly as given to the
model in Run 2. Types S, B3 and C3 belong to the review rules (data/review/rules.md).

Run:  python scripts/verify_gold.py poe_published_v2_1
      python scripts/verify_gold.py poe_published pilot/expected.csv
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evidence_agent.domains import load_domain  # noqa: E402

S, C, I = "supported", "contradicted", "insufficient_evidence"

# As-run labels that a later rule correction replaced. They stay in the as-run claim
# file, because that is what the saved runs were scored against.
SUPERSEDED = {"poe_published_v2": {"V05": "relabelled in poe_published_v2_1 (magnitude claim, opposite signs)"}}


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
    if t == "S":                        # a stated significance level (review rules v3)
        target = d if not claim["parent"] else d[claim["parent"]]
        significant = target["difference_significant"] if not claim["parent"] else target["significant"]
        return S if significant else C
    if t in ("B3", "C3"):              # parent-specific wording is never supported (review rules v3)
        other = p if t == "B3" else m
        return C if diff_sig and other["significant"] else I
    if t in ("B2", "C2"):              # strict parent-specific (rules v2.1)
        own, other = (m, p) if t == "B2" else (p, m)
        if diff_sig and own["significant"] and not other["significant"]:
            return S
        if diff_sig and other["significant"]:
            return C
        return I
    if t == "H":                        # larger effect in the named parent (rules v2.1)
        own, other = (m, p) if claim["parent"] == "maternal" else (p, m)
        if d["effect_signs"] == "opposite":     # the difference test does not compare magnitudes
            return I
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


def main(domain_name: str, claims_path=None) -> int:
    """Check the claims of a domain, or of another claim file that uses the domain's records and rules."""
    domain = load_domain(domain_name)
    tools = {t.name: t.function for t in domain["tools"]}
    with open(claims_path or domain["claims_path"], newline="", encoding="utf-8") as f:
        claims = list(csv.DictReader(f))
    superseded = SUPERSEDED.get(domain_name, {})
    mismatches = old = 0
    for c in claims:
        v = verdict(c, tools, domain["records"])
        ok = v == c["gold_verdict"]
        if not ok and c["claim_id"] in superseded:
            old += 1
            print(f"[old] {c['claim_id']} gold={c['gold_verdict']:<22} rules={v}  ({superseded[c['claim_id']]})")
            continue
        mismatches += not ok
        print(f"[{'ok ' if ok else 'BAD'}] {c['claim_id']} gold={c['gold_verdict']:<22} rules={v}")
    print(f"\n{len(claims) - mismatches - old}/{len(claims)} gold verdicts reproduced by the rule implementation.")
    if old:
        print(f"{old} as-run label(s) superseded by a later rule correction (marked [old]).")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "poe_published", sys.argv[2] if len(sys.argv) > 2 else None))
