"""Command line.

  python -m evidence_agent check --domain poe "LOCUS_B has a maternal-specific effect on BMI."
  python -m evidence_agent evaluate --domain poe --mode agent
  python -m evidence_agent evaluate --domain poe --mode no_tools
  python -m evidence_agent compare results/<run_1> results/<run_2>
"""

import argparse
import csv
import json
import os
from datetime import datetime
from pathlib import Path

from .agent import run_agent
from .domains import ROOT, load_domain
from .metrics import paired_comparison, summary_markdown


def load_env(path: Path = ROOT / ".env") -> None:
    """Minimal .env reader: KEY=value lines; existing environment variables win."""
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"'))


def make_llm():
    from .llm import OpenAIChat
    return OpenAIChat()


def cmd_check(args):
    domain = load_domain(args.domain, getattr(args, "system", "v1"))
    result = run_agent(args.claim, domain, make_llm(), mode=args.mode)
    print(json.dumps({k: v for k, v in result.items() if k != "trace"}, indent=2))
    if args.trace:
        print(json.dumps(result["trace"], indent=2))


def cmd_evaluate(args, llm=None):
    system = getattr(args, "system", "v1") or "v1"
    domain = load_domain(args.domain, system)
    llm = llm or make_llm()
    with open(domain["claims_path"], newline="", encoding="utf-8") as f:
        claims = list(csv.DictReader(f))
    if getattr(args, "split", None):
        claims = [c for c in claims if c.get("split") == args.split]
    if args.limit:
        claims = claims[: args.limit]

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = Path(getattr(args, "out_root", None) or ROOT / "results")
    out_dir = base / f"{args.domain}_{args.mode}_{system}_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    model = getattr(llm, "model", "scripted")

    rows = []
    with open(out_dir / "runs.jsonl", "w", encoding="utf-8") as log:
        for c in claims:
            result = run_agent(c["claim"], domain, llm, mode=args.mode)
            row = {"claim_id": c["claim_id"], "claim": c["claim"], "gold": c["gold_verdict"],
                   "trap_type": c.get("trap_type", ""), "split": c.get("split", ""),
                   "model": model, "mode": args.mode, "system": system, **result}
            rows.append(row)
            log.write(json.dumps(row) + "\n")
            mark = "ok " if row["verdict"] == row["gold"] else "ERR"
            print(f"[{mark}] {c['claim_id']}: gold={row['gold']} pred={row['verdict']}")

    title = f"{args.domain} — {args.mode} — {model} — {stamp}"
    summary = summary_markdown(rows, title)
    (out_dir / "summary.md").write_text(summary, encoding="utf-8")
    print("\n" + summary)
    print(f"Saved to {out_dir}")
    return rows


def _read_runs(folder: str) -> list:
    path = Path(folder) / "runs.jsonl"
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def cmd_compare(args):
    rows_1, rows_2 = _read_runs(args.run_1), _read_runs(args.run_2)
    def label(rows, folder):
        r = rows[0]
        return f"{r.get('mode', '?')}/{r.get('system', 'v1')}" if "mode" in r else Path(folder).name
    label_1, label_2 = label(rows_1, args.run_1), label(rows_2, args.run_2)
    print(paired_comparison(rows_1, rows_2, label_1, label_2))


def main():
    load_env()
    p = argparse.ArgumentParser(prog="evidence_agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="Check one claim")
    c.add_argument("claim")
    c.add_argument("--domain", required=True)
    c.add_argument("--mode", default="agent", choices=["agent", "no_tools"])
    c.add_argument("--system", default="v1", choices=["v1", "v2"], help="v1 = original; v2 = rsID-first search + explanation-first verdict")
    c.add_argument("--trace", action="store_true", help="Print every tool call")
    c.set_defaults(func=cmd_check)

    e = sub.add_parser("evaluate", help="Run labelled claims and score them")
    e.add_argument("--domain", required=True)
    e.add_argument("--mode", default="agent", choices=["agent", "no_tools"])
    e.add_argument("--system", default="v1", choices=["v1", "v2"], help="v1 = original; v2 = rsID-first search + explanation-first verdict")
    e.add_argument("--split", help="Only claims from this split (e.g. dev, heldout)")
    e.add_argument("--limit", type=int, help="Only the first N claims")
    e.set_defaults(func=cmd_evaluate)

    k = sub.add_parser("compare", help="Paired comparison of two evaluation runs")
    k.add_argument("run_1", help="Results folder of the first run")
    k.add_argument("run_2", help="Results folder of the second run")
    k.set_defaults(func=cmd_compare)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
