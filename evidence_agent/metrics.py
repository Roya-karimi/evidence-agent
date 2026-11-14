"""Evaluation metrics: accuracy with a bootstrap CI, per-class recall, confusion matrix."""

import math
import random
from collections import Counter, defaultdict

from .tools import VERDICTS

NO_VERDICT = "no_verdict"


def accuracy(gold: list, pred: list) -> float:
    return sum(g == p for g, p in zip(gold, pred)) / len(gold) if gold else float("nan")


def bootstrap_ci(gold: list, pred: list, n_boot: int = 2000, level: float = 0.95, seed: int = 1,
                 clusters: list | None = None) -> tuple:
    """Percentile bootstrap of accuracy.

    By default claims are resampled with replacement. If `clusters` gives a cluster
    label per claim (for example the variant a claim is about), whole clusters are
    resampled instead, which allows for claims that share source records.
    """
    rng = random.Random(seed)
    n = len(gold)
    if clusters is None:
        groups = [[i] for i in range(n)]
    else:
        by_cluster = defaultdict(list)
        for i, c in enumerate(clusters):
            by_cluster[c].append(i)
        groups = list(by_cluster.values())
    stats = []
    for _ in range(n_boot):
        idx = [i for _ in range(len(groups)) for i in groups[rng.randrange(len(groups))]]
        stats.append(accuracy([gold[i] for i in idx], [pred[i] for i in idx]))
    stats.sort()
    lo = stats[int((1 - level) / 2 * n_boot)]
    hi = stats[int((1 + level) / 2 * n_boot) - 1]
    return lo, hi


def confusion(gold: list, pred: list) -> dict:
    """{gold_label: {predicted_label: count}}"""
    table = defaultdict(Counter)
    for g, p in zip(gold, pred):
        table[g][p or NO_VERDICT] += 1
    return table


def recall_by_class(gold: list, pred: list) -> dict:
    out = {}
    for label in VERDICTS:
        idx = [i for i, g in enumerate(gold) if g == label]
        if idx:
            out[label] = (sum(pred[i] == label for i in idx), len(idx))
    return out


def by_group(rows: list, key: str) -> dict:
    """Accuracy within subgroups, e.g. by trap type."""
    groups = defaultdict(list)
    for r in rows:
        groups[r.get(key) or "none"].append(r["gold"] == r["verdict"])
    return {k: (sum(v), len(v)) for k, v in sorted(groups.items())}


_CONCLUSION_PATTERNS = [   # checked in this order on the explanation's final sentence
    ("insufficient_evidence", r"insufficient evidence|not enough evidence|cannot be (?:established|determined|evaluated|assessed)"
                              r"|no records? (?:were |was )?found|do(?:es)? not support|not (?:fully )?supported"),
    ("contradicted", r"contradict"),
    ("supported", r"\bsupport"),
]


def explanation_conclusion(text: str):
    """Heuristic: the verdict stated in the explanation's final sentence.

    Used only to flag runs for review, never to score them. Phrases such as
    "insufficient evidence to support" or "not supported" count as insufficient_evidence.
    Returns None if the final sentence names no verdict.
    """
    import re
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if s]
    if not sentences:
        return None
    last = sentences[-1].lower()
    for label, pattern in _CONCLUSION_PATTERNS:
        if re.search(pattern, last):
            return label
    return None


def verdict_explanation_mismatches(rows: list) -> list:
    return [r["claim_id"] for r in rows
            if r.get("verdict") and explanation_conclusion(r.get("explanation", "")) not in (None, r["verdict"])]


def mcnemar_exact(b: int, c: int) -> float:
    """Exact two-sided McNemar test on the discordant pairs.

    b = claims only condition 1 got right, c = claims only condition 2 got right.
    Under H0 (equal accuracy) b ~ Binomial(b + c, 0.5).
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def _check_pairable(rows_1: list, rows_2: list, allow_subset: bool) -> list:
    """Make sure two runs can be compared claim by claim; return the shared claim IDs.

    Refuses duplicate claim IDs, different claim sets (unless allow_subset), and claims
    whose text, gold verdict or domain differ between the runs.
    """
    for name, rows in (("first", rows_1), ("second", rows_2)):
        ids = [r["claim_id"] for r in rows]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            raise ValueError(f"Duplicate claim IDs in the {name} run: {dup}")
    by_1, by_2 = {r["claim_id"]: r for r in rows_1}, {r["claim_id"]: r for r in rows_2}
    shared = [cid for cid in by_1 if cid in by_2]
    if not shared:
        raise ValueError("The two runs share no claim IDs.")
    only = sorted(set(by_1) ^ set(by_2))
    if only and not allow_subset:
        raise ValueError(f"The runs cover different claims (in one run only: {only}). "
                         "Pass allow_subset=True to compare the shared claims.")
    for cid in shared:
        for key in ("claim", "gold", "domain"):
            a, b = by_1[cid].get(key), by_2[cid].get(key)
            if a is not None and b is not None and a != b:
                raise ValueError(f"Claim {cid} differs between the runs in '{key}': {a!r} vs {b!r}")
    return shared


def paired_comparison(rows_1: list, rows_2: list, label_1: str, label_2: str, allow_subset: bool = False) -> str:
    """Compare two runs on the same claims (paired by claim_id)."""
    shared = _check_pairable(rows_1, rows_2, allow_subset)
    by_1, by_2 = {r["claim_id"]: r for r in rows_1}, {r["claim_id"]: r for r in rows_2}
    ok_1 = {cid: by_1[cid]["verdict"] == by_1[cid]["gold"] for cid in shared}
    ok_2 = {cid: by_2[cid]["verdict"] == by_2[cid]["gold"] for cid in shared}
    only_1 = sorted(cid for cid in shared if ok_1[cid] and not ok_2[cid])
    only_2 = sorted(cid for cid in shared if ok_2[cid] and not ok_1[cid])
    n = len(shared)
    omitted = sorted(set(by_1) ^ set(by_2))
    lines = [f"# Paired comparison: {label_1} vs {label_2}", "",
             f"Claims compared: {n}" + (f" (not in both runs, left out: {', '.join(omitted)})" if omitted else ""), "",
             "| Condition | Correct / total | Accuracy |", "| --- | --- | --- |",
             f"| {label_1} | {sum(ok_1.values())} / {n} | {sum(ok_1.values()) / n:.2f} |",
             f"| {label_2} | {sum(ok_2.values())} / {n} | {sum(ok_2.values()) / n:.2f} |", "",
             f"Correct only with {label_1}: {len(only_1)} ({', '.join(only_1) or 'none'})  ",
             f"Correct only with {label_2}: {len(only_2)} ({', '.join(only_2) or 'none'})  ",
             f"Exact McNemar test: p = {mcnemar_exact(len(only_1), len(only_2)):.3f}"]
    return "\n".join(lines) + "\n"


def run_status(row: dict) -> str:
    """ok / no_valid_verdict / operational_error (runs saved before `status` existed are inferred)."""
    return row.get("status") or ("ok" if row.get("verdict") else "no_valid_verdict")


def summary_markdown(rows: list, title: str, not_attempted: int = 0) -> str:
    if not rows:
        return f"# {title}\n\n**INCOMPLETE RUN.** No claim was completed.\n"
    gold = [r["gold"] for r in rows]
    pred = [r["verdict"] for r in rows]
    acc = accuracy(gold, pred)
    lo, hi = bootstrap_ci(gold, pred)
    n_failed = sum(run_status(r) == "operational_error" for r in rows)
    lines = [f"# {title}", ""]
    if n_failed or not_attempted:
        lines += [f"**INCOMPLETE RUN.** {n_failed} claim(s) failed operationally and {not_attempted} "
                  "were not attempted. Do not report these numbers as a result; run again.", ""]
    lines += [f"Claims: {len(rows)}  ",
             f"Accuracy: {acc:.2f} (95% bootstrap CI {lo:.2f}–{hi:.2f})  ",
             f"No valid verdict from the model: {sum(run_status(r) == 'no_valid_verdict' for r in rows)}  ",
             f"Operational failures (model call failed; counted as incorrect): {n_failed}  ",
             f"Verdict/explanation mismatches (heuristic flag): {', '.join(verdict_explanation_mismatches(rows)) or 'none'}  ",
             f"Mean tool calls: {sum(r['tool_calls'] for r in rows) / len(rows):.1f}  ",
             f"Tokens (prompt / completion): {sum(r['usage'].get('prompt_tokens', 0) for r in rows)} / "
             f"{sum(r['usage'].get('completion_tokens', 0) for r in rows)}", "",
             "## Recall by true verdict", "", "| True verdict | Correct / total |", "| --- | --- |"]
    for label, (c, n) in recall_by_class(gold, pred).items():
        lines.append(f"| {label} | {c} / {n} |")

    cols = VERDICTS + [NO_VERDICT]
    lines += ["", "## Confusion matrix (rows = true, columns = predicted)", "",
              "| | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
    table = confusion(gold, pred)
    for g in VERDICTS:
        if g in table:
            lines.append(f"| {g} | " + " | ".join(str(table[g].get(c, 0)) for c in cols) + " |")

    if any(r.get("split") for r in rows):
        lines += ["", "## Accuracy by split", "", "| Split | Correct / total |", "| --- | --- |"]
        for k, (c, n) in by_group(rows, "split").items():
            lines.append(f"| {k} | {c} / {n} |")

    lines += ["", "## Accuracy by trap type", "", "| Trap type | Correct / total |", "| --- | --- |"]
    for k, (c, n) in by_group(rows, "trap_type").items():
        lines.append(f"| {k} | {c} / {n} |")

    wrong = [r for r in rows if r["gold"] != r["verdict"]]
    lines += ["", "## Errors", ""]
    lines += [f"- **{r['claim_id']}** (true: {r['gold']}, predicted: {r['verdict']}): {r['claim']}"
              for r in wrong] or ["None."]
    return "\n".join(lines) + "\n"
