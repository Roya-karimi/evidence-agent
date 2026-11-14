"""Score a review of the pilot statements against the expected findings.

A statement "has a problem" when its expected finding is not `supported`.
A statement is "flagged" when the review does not return `supported` for it
(including when the checker reaches no verdict).

  caught        problem statements that were flagged
  missed        problem statements returned as supported
  false alarms  sound statements that were flagged
  same finding  the review gives exactly the expected finding
  source right  the cited rows include the expected row and no row of another variant

Run:  python scripts/score_pilot.py review_output/pilot/review.csv
"""

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
def read(path) -> list:
    """Read a CSV. Excel in some locales saves with semicolons, so the delimiter is detected."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        header = f.readline()
        f.seek(0)
        return list(csv.DictReader(f, delimiter=";" if header.count(";") > header.count(",") else ","))


def source_right(expected: dict, cited: list) -> bool:
    variant = set(re.findall(r"rs\d+", expected["claim"]))
    if any(rid.split("_")[0] not in variant for rid in cited):
        return False                                   # a row of some other variant was used
    wanted = [r for r in expected["record_ids"].split(";") if r]
    if not wanted or expected["claim_type"] == "X":    # no row in the table, or a mechanism claim
        return True
    return any(r in cited for r in wanted)


def tally(expected: list, verdicts: dict) -> dict:
    problem = [e for e in expected if e["gold_verdict"] != "supported"]
    sound = [e for e in expected if e["gold_verdict"] == "supported"]
    flagged = lambda e: verdicts.get(e["claim"]) != "supported"          # noqa: E731
    return {"caught": sum(flagged(e) for e in problem), "missed": sum(not flagged(e) for e in problem),
            "false_alarms": sum(flagged(e) for e in sound),
            "same_finding": sum(verdicts.get(e["claim"]) == e["gold_verdict"] for e in expected),
            "n_problem": len(problem), "n_sound": len(sound), "n": len(expected)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("review_csv")
    parser.add_argument("--expected", default=str(ROOT / "pilot" / "expected.csv"))
    args = parser.parse_args()

    expected, review = read(args.expected), read(args.review_csv)
    by_statement = {r["statement"]: r for r in review}
    unknown = [e["claim_id"] for e in expected if e["claim"] not in by_statement]
    if unknown:
        print(f"These statements are not in {args.review_csv}: {unknown}")
        return 1

    checker = tally(expected, {s: r["verdict"] or None for s, r in by_statement.items()})
    sources = sum(source_right(e, [i for i in by_statement[e["claim"]]["evidence_ids"].split(";") if i]) for e in expected)
    seconds = sum(float(r["seconds"] or 0) for r in review)
    n = checker
    print(f"Statements: {n['n']} ({n['n_problem']} with a problem, {n['n_sound']} sound)\n")
    print("| Measure | Checker |\n| --- | --- |")
    print(f"| Problems caught | {n['caught']} / {n['n_problem']} |")
    print(f"| Problems missed | {n['missed']} / {n['n_problem']} |")
    print(f"| False alarms | {n['false_alarms']} / {n['n_sound']} |")
    print(f"| Same finding as expected | {n['same_finding']} / {n['n']} |")
    print(f"| Source row right | {sources} / {n['n']} |")
    print(f"| Time in model calls | {seconds:.0f} s |")

    print("\nPer statement:\n")
    for e in expected:
        r = by_statement[e["claim"]]
        mark = "ok " if r["verdict"] == e["gold_verdict"] else "DIFF"
        print(f"[{mark}] {e['claim_id']} expected={e['gold_verdict']:<22} checker={r['verdict'] or 'no verdict'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
