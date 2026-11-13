# Changelog

## 2026-11-13: Run 3, version 2 test

- Tools: v1 20/26 → v2 22/26. Searches returning nothing 17 → 1; existing records never opened 3 → 0. H1 is supported for its mechanism.
- No tools: v1 19/26 → v2 24/26 (McNemar p = 0.13). Verdict–explanation mismatches 3 → 0. H2 is supported in direction.
- Open issues: allele orientation (V14), mechanism claims with no allele named (V22), and threshold failures recorded as `contradicted` (V03). Candidate next step: a tool that checks allele compatibility. Details in [RESULTS.md](RESULTS.md).

## 2026-11-13: version 2 (pre-registered before any v2 run)

- **`--system v2`.**
    - rsID-first search, with normalised trait words.
    - `submit_verdict` asks for the explanation before the verdict.
    - The prompt says to choose the verdict that follows from the explanation.
    - `--system v1` keeps the original behaviour.
- **Rules v2 (`data/poe_published_v2/rules.md`).**
    - Strict parent-specific claims (types B/C).
    - New type H, "larger when inherited from" a named parent.
- **New test set `poe_published_v2`.** 26 new claims on the same 30 records. Every gold verdict is reproduced by `verify_gold.py`.
- **Automatic verdict–explanation mismatch flag** in every summary. On Run 2 it reproduced the clear mismatches found by reading the traces: R09, R15, R18 and R23 without tools, and R18 with tools.
- **Planned runs** (the analysis plan is in METHODS §7): agent/v1, agent/v2, no_tools/v1 and no_tools/v2 on `poe_published_v2`, then paired comparisons agent v1 vs v2 (H1) and no_tools v1 vs v2 (H2).

## 2026-11-13: Run 2, published benchmark

- Ran with gpt-4.1-mini: agent 26/32, no_tools 23/32. Paired exact McNemar p = 0.55. Details in [RESULTS.md](RESULTS.md).
- **Candidates for the next version.** These were identified from the Run 2 traces. They have not been applied to this benchmark, and each needs new claims to evaluate it:
    1. **Retrieval.** When the query contains an rsID, `find_records` should return every record for that rsID, so different spellings of a trait name ("type 2 diabetes" vs "T2D") no longer hide a record.
    2. **Reasoning before committing.** In the `submit_verdict` schema, put `explanation` before `verdict`, so the model writes its reasoning before the label. This tests the hypothesis behind the verdict–explanation mismatches.
    3. **Parent-specific claims.** Decide explicitly whether "maternal-/paternal-specific" excludes a significant effect in the other parent (the strict reading), or adopt the paper's own categories (maternal, maternal asymmetric, bipolar).
    4. **Automatic consistency check.** Flag runs where the verdict disagrees with the conclusion in the explanation.

## 2026-11-13: published parent-of-origin benchmark

- **New domain `poe_published`.** It holds the 30 parent-of-origin effects from Table 1 of Hofmeister et al. (2025, *Nature*, CC BY 4.0). `scripts/build_poe_published.py` builds the records from the extracted table.
- **Published p-values take priority.** When a record includes published p-values, the tools use them for every significance decision. Values recomputed from rounded estimates are still returned, but only for reference.
- **New `find_records` tool.** It searches by rsID, locus or trait words.
- **Decision rules for published data.** They cover stated thresholds, allele orientation (a non-effect allele that is not recorded gives `insufficient_evidence`), variant–trait matching, and gene-level claims. The rules were fixed before any model run on this domain.
- **32 test claims.** Their verdicts are 15 supported, 7 contradicted and 10 insufficient evidence.
- **New `scripts/verify_gold.py`.** It reproduces every gold verdict with a deterministic implementation of the rules, and the test suite runs it. The synthetic parent-of-origin claims also have structured columns now, and all 20 of their verdicts are reproduced.
- **Audit before the published run:**
    - 16/16 offline tests pass.
    - The verdict check passes on 32/32 published and 20/20 synthetic claims.
    - `records.csv` rebuilds identically from the source table, and 240/240 values match a second, independent reading of Table 1.
    - A full scripted dry run of both conditions and the paired comparison completed.
    - No broken document links, and every count quoted in the documents matches the data files.

## 2026-11-13: rules v2

**Motivation:** Run 1, claim P15.

- **Parent-of-origin rules restructured into claim types A–G.** Rule 1 previously grouped general, maternal-specific and paternal-specific claims together. In Run 1 the model applied the maternal-specific condition to a general parent-of-origin claim (P15), and returned `contradicted` instead of `supported`. Each claim is now classified into exactly one type, and only that type's rule applies.
- **Five held-out claims added (P16–P20).** These cover general parent-of-origin and paternal-specific claims. They were written after the rule change, to check that the change generalises beyond P15.
- **`split` column added to claim files** (`dev` / `heldout`). Summaries now report accuracy by split.
- **The `test_parental_difference` tool description now says it includes both single-parent tests.** This is meant to reduce redundant tool calls; it does not affect verdicts.
- **New `compare` command.** It gives a paired comparison of two runs with an exact McNemar test.

## 2026-11-13: Run 1 (rules v1)

- Development benchmark on synthetic records with gpt-4.1-mini.
- Parent-of-origin: agent 14/15, no_tools 11/15.
- Energy: agent 8/8, no_tools 7/8.
- Details: [RESULTS.md](RESULTS.md).
