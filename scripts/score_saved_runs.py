"""Re-score the saved runs without calling the model.

For every folder in results/ this script
  1. recounts the correct verdicts under the labels the run was scored against;
  2. gives a claim-level and a variant-clustered bootstrap CI (claims about the same
     variant share source records, so they are not independent);
  3. checks each saved submission against the acceptance rules in agent.py
     (evidence looked up first, cited IDs returned by a tool, explanation present).
For the version 2 runs (Run 3) it also re-scores under the corrected version 2.1 labels,
and repeats the paired comparisons.

Run:  python scripts/score_saved_runs.py
"""

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from evidence_agent.agent import _ids_in  # noqa: E402
from evidence_agent.metrics import accuracy, bootstrap_ci, mcnemar_exact  # noqa: E402

ASSERTING = ("supported", "contradicted")


def read_runs(folder: Path) -> list:
    with open(folder / "runs.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def read_claims(domain: str) -> dict:
    with open(ROOT / "data" / domain / "claims.csv", newline="", encoding="utf-8") as f:
        return {c["claim_id"]: c for c in csv.DictReader(f)}


def variant_clusters(claims: dict) -> dict:
    """Cluster label per claim: the variant(s) it is about. Claims that share a variant share a cluster."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    keys = {}
    for cid, c in claims.items():
        variants = {rid.split("_")[0] for rid in c["record_ids"].split(";") if rid}
        variants |= set(re.findall(r"rs\d+", c["claim"]))
        variants = sorted(variants) or [f"claim:{cid}"]          # no variant named: its own cluster
        for v in variants[1:]:
            parent[find(v)] = find(variants[0])
        keys[cid] = variants[0]
    return {cid: find(v) for cid, v in keys.items()}


def structural_problems(row: dict) -> list:
    """Would this saved submission pass the acceptance rules now in agent.py?"""
    problems, seen, opened, evidence_calls, by_step = [], set(), set(), 0, {}
    for t in row["trace"]:
        if "tool" in t:
            by_step.setdefault(t["step"], []).append(t["tool"])
        if isinstance(t.get("result"), dict):
            evidence_calls += 1
            s, o = _ids_in(t["result"])
            seen |= s
            opened |= o
    ids = row.get("evidence_ids") or []
    if not (row.get("explanation") or "").strip():
        problems.append("empty explanation")
    if any("submit_verdict" in tools and len(tools) > 1 for tools in by_step.values()):
        problems.append("verdict submitted together with other calls")
    if row["mode"] == "agent":
        if evidence_calls == 0:
            problems.append("no evidence lookup")
        if not set(ids) <= seen:
            problems.append("cites an ID no tool returned")
        if row["verdict"] in ASSERTING and not set(ids) & opened:
            problems.append("asserts without citing a retrieved record")
    elif row["verdict"] in ASSERTING and not ids:
        problems.append("asserts without citing a record")
    return problems


def score(rows: list, gold: dict, clusters: dict, exclude=()) -> str:
    rows = [r for r in rows if r["claim_id"] not in exclude]
    g = [gold[r["claim_id"]] for r in rows]
    p = [r["verdict"] for r in rows]
    lo, hi = bootstrap_ci(g, p)
    clo, chi = bootstrap_ci(g, p, clusters=[clusters[r["claim_id"]] for r in rows])
    correct = sum(a == b for a, b in zip(g, p))
    return f"{correct} / {len(rows)} | {accuracy(g, p):.2f} | {lo:.2f}–{hi:.2f} | {clo:.2f}–{chi:.2f}"


def main() -> int:
    folders = sorted(p.parent for p in (ROOT / "results").glob("*/runs.jsonl"))
    runs = {f.name: read_runs(f) for f in folders}
    failures = 0

    print("## Saved runs, scored against the labels they were run with\n")
    print("| Run | Correct | Accuracy | 95% CI, claims | 95% CI, variant clusters | Variants | Submissions passing the acceptance rules |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for name, rows in runs.items():
        domain = "poe_published_v2" if "_v2_" in name else "poe_published"
        claims = read_claims(domain)
        for r in rows:           # the saved rows must match the committed claim file
            c = claims[r["claim_id"]]
            if (r["claim"], r["gold"]) != (c["claim"], c["gold_verdict"]):
                failures += 1
                print(f"MISMATCH between {name} and data/{domain}/claims.csv: {r['claim_id']}")
        clusters = variant_clusters(claims)
        passing = sum(not structural_problems(r) for r in rows)
        failures += passing != len(rows)
        gold = {cid: c["gold_verdict"] for cid, c in claims.items()}
        print(f"| {name} | {score(rows, gold, clusters)} | {len(set(clusters.values()))} | {passing} / {len(rows)} |")

    as_run, revised = read_claims("poe_published_v2"), read_claims("poe_published_v2_1")
    changed = sorted(cid for cid in as_run if as_run[cid]["gold_verdict"] != revised[cid]["gold_verdict"])
    gold = {cid: c["gold_verdict"] for cid, c in revised.items()}
    clusters = variant_clusters(revised)
    v2 = {name: rows for name, rows in runs.items() if "_v2_" in name}

    print(f"\n## Run 3 under the corrected version 2.1 labels\n\nRelabelled: {', '.join(changed)}\n")
    for cid in changed:
        answers = {name.split("poe_published_v2_")[1].rsplit("_", 1)[0]: next(r["verdict"] for r in rows if r["claim_id"] == cid)
                   for name, rows in v2.items()}
        print(f"- {cid}: {as_run[cid]['gold_verdict']} -> {revised[cid]['gold_verdict']}. Saved answers: {answers}")
    for title, exclude in (("relabelled claims excluded", changed), ("relabelled claims counted against the new label", ())):
        print(f"\n**{title}**\n")
        print("| Run | Correct | Accuracy | 95% CI, claims | 95% CI, variant clusters |")
        print("| --- | --- | --- | --- | --- |")
        for name, rows in v2.items():
            print(f"| {name} | {score(rows, gold, clusters, exclude)} |")

    print("\n**Paired comparisons (version 2.1 labels, relabelled claims excluded)**\n")
    pairs = [("agent_v1", "agent_v2"), ("no_tools_v1", "no_tools_v2"), ("agent_v1", "no_tools_v1"), ("agent_v2", "no_tools_v2")]
    short = {name.split("poe_published_v2_")[1].rsplit("_", 1)[0]: rows for name, rows in v2.items()}
    for a, b in pairs:
        ok_a = {r["claim_id"]: r["verdict"] == gold[r["claim_id"]] for r in short[a] if r["claim_id"] not in changed}
        ok_b = {r["claim_id"]: r["verdict"] == gold[r["claim_id"]] for r in short[b] if r["claim_id"] not in changed}
        only_a = sorted(c for c in ok_a if ok_a[c] and not ok_b[c])
        only_b = sorted(c for c in ok_a if ok_b[c] and not ok_a[c])
        print(f"- {a} vs {b}: only {a} correct {len(only_a)} ({', '.join(only_a) or 'none'}); "
              f"only {b} correct {len(only_b)} ({', '.join(only_b) or 'none'}); "
              f"exact McNemar p = {mcnemar_exact(len(only_a), len(only_b)):.3f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
