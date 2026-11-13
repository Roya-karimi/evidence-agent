# Results

## Run 3: version 2 test, pre-registered (26 new claims)

**Run settings**

- Date: 13 November 2026
- Model: gpt-4.1-mini, temperature 0
- Domain: `poe_published_v2`, rules v2
- Design: system v1 or v2, crossed with tools or no tools, on the same 26 claims
- Analysis plan: [METHODS §7](METHODS.md), fixed before the run
- Traces: `results/poe_published_v2_*_20261113-run3/`

| Condition | Correct | Accuracy (95% CI) | Asserted errors* | Verdict–explanation mismatches† |
| --- | --- | --- | --- | --- |
| tools, system v1 | 20 / 26 | 0.77 (0.62–0.92) | 4 | 0 |
| tools, system v2 | 22 / 26 | 0.85 (0.69–0.96) | 4 | 1 (V03) |
| no tools, system v1 | 19 / 26 | 0.73 (0.54–0.88) | 7 | 3 (V09, V24, V26) |
| no tools, system v2 | **24 / 26** | **0.92 (0.81–1.00)** | **2** | **0** |
| always "supported" | 12 / 26 | 0.46 | 14 | – |

\*Errors where the verdict was `supported` or `contradicted` and the correct verdict was different.
†From reading the traces. The automatic flag found V03, V24 and V26. It missed V09, where the explanation ends "supported, not contradicted": negation is a known limit of the keyword check.

### H1: rsID-first search (tools, v1 vs v2)

**Supported for retrieval; no change in accuracy on the trait-synonym claims.**

| | v1 | v2 |
| --- | --- | --- |
| Searches returning no records | 17 | 1 |
| Claims where an existing record was never opened | 3 (V04, V12, V13) | 0 |
| Trait-synonym claims correct (V01, V02, V03, V08, V12) | 4 / 5 | 4 / 5 |

In v2 the record was retrieved for all five trait-synonym claims. v2 fixed V12 but got V03 wrong for a different reason: it labelled a failed threshold `contradicted` (see below).

V13 had been answered correctly in v1 without its record ever being opened, so it was right for the wrong reason.

On accuracy, 3 claims were correct only with v2 (V11, V12, V23) and 1 only with v1 (V03). Exact McNemar p = 0.63.

### H2: explanation before verdict (no tools, v1 vs v2)

**Supported in direction; not statistically significant at n = 26.**

- Accuracy rose from 19 to 24 of 26. Six claims were correct only with v2 (V03, V09, V12, V13, V14, V24), against one only with v1 (V22). Exact McNemar p = 0.13.
- Verdict–explanation mismatches fell from 3 to 0.
- Asserted errors fell from 7 to 2.

### Errors that remain in the best conditions

| Claim | Failure | Conditions affected | Comment |
| --- | --- | --- | --- |
| V25: threshold P < 10⁻⁶, published P = 2.59×10⁻⁶ | Says 2.59×10⁻⁶ is below 10⁻⁶ | Both no-tools runs | Never happens with tools, where the comparison is done in code. The same pattern as R02 and R03 in Run 2. |
| V14: claim about the C allele; record has effect allele G, other allele not recorded | Assumes C is the other allele and flips the sign | 3 of 4 runs (correct only without tools in v2) | Allele orientation remains the most persistent failure. |
| V22: a mechanism claim ("through IGF2 overexpression") with no allele named | Judged on direction (`contradicted`) instead of as a mechanism claim (`insufficient_evidence`) | 3 of 4 runs | The claim is also ambiguous about the allele. Under the rules the correct verdict is `insufficient_evidence`, but the models consistently treat it as a direction claim. |
| V04: paternal-specific claim, both parental effects significant | v2 with tools ignored the strict rule and answered `supported` | Tools, v2 | A rule-application error. v1 with tools never reached this question, because its search failed. |
| V03: genome-wide threshold not met | Labelled `contradicted` where the rule says `insufficient_evidence`. The explanation said "not supported". | Tools v2; no tools v1 | The model treats a failed significance threshold as evidence against the claim. |

### Interpretation

1. **The two fixes did what they were designed to do.** rsID-first search removed retrieval failures. Explanation-first removed verdict–explanation mismatches and gave the largest single accuracy gain. Neither accuracy difference is statistically significant with 26 claims.
2. **Tools and explanation-first fix different errors.**
    - Tools remove numerical errors: threshold comparisons (V25 here, R02 and R03 in Run 2) and the use of another variant's record (R05).
    - Explanation-first removes inconsistency between reasoning and label.
    - On this claim set, explanation-first without tools scored highest. But it still made the threshold error that tools never make.
3. **Allele orientation and mechanism claims remain open problems** for both the model and the rule design. A natural next step is a tool that reports allele compatibility explicitly, so the model doesn't have to infer it.

### Limitations

- One model and one run per condition.
- 26 claims, written by the same author after seeing the Run 2 failure modes. They are therefore targeted at those failures. The paired v1-vs-v2 comparisons are the valid result, not the absolute accuracy.
- Both systems used the v2 rules, so these runs do not test the effect of the rule change itself.

## Run 2: published parent-of-origin benchmark (primary result)

**Run settings**

- Date: 13 November 2026
- Model: gpt-4.1-mini, temperature 0
- Rules: fixed before this run
- Claims: 32, all in the `test` split
- Traces: [agent](../results/poe_published_agent_20261113-212430/runs.jsonl), [no_tools](../results/poe_published_no_tools_20261113-212643/runs.jsonl)

### Accuracy

| Condition | Correct | Accuracy (95% bootstrap CI) | Asserted a claim the records do not establish* | Tokens | Seconds per claim |
| --- | --- | --- | --- | --- | --- |
| agent (tools) | 26 / 32 | 0.81 (0.69–0.94) | 4 | 156,607 | 3.7 |
| no_tools | 23 / 32 | 0.72 (0.56–0.88) | 9 | 228,478 | 1.8 |
| always "supported" (reference) | 15 / 32 | 0.47 | 17 | – | – |

\*Errors where the model returned `supported` or `contradicted` and the correct verdict was different.

**Paired comparison.** 7 claims were correct only with tools: R02, R03, R05, R09, R13, R23 and R24. 4 were correct only without tools: R10, R12, R16 and R31. Exact McNemar p = 0.55, so with 32 claims the accuracy difference is not statistically detectable.

**What differs is the kind of error.** Without tools, every error asserted something the records do not establish. With tools, 2 of the 6 errors were cautious `insufficient_evidence` verdicts.

### Error analysis (from the traces)

Every error was classified by reading its full trace.

**Without tools (9 errors)**

| Failure mode | Claims | What the trace shows |
| --- | --- | --- |
| Verdict contradicts the model's own explanation | R09, R13, R15, R18, R23, R24 | In R09, R15 and R23 the explanation reaches the correct conclusion, but the `verdict` field says something else. In R18 the explanation reaches a different, also incorrect, conclusion. In R13 and R24 the explanation contradicts itself or hedges. |
| Comparing small p-values | R02, R03 | The explanation states that 7.53×10⁻⁸ and 2.22×10⁻⁷ are below 5×10⁻⁸. |
| Substituted evidence | R05 | No leg-fat record exists for rs80116540, so the model used the leg-fat record of a different variant (rs3730173) to support the claim. |

**With tools (6 errors, plus one correct verdict for the wrong reason)**

| Failure mode | Claims | What the trace shows |
| --- | --- | --- |
| Retrieval: trait vocabulary | R16, R31, and R32 (correct by chance) | Searches for "type 2 diabetes" and "IGF-1" found no records labelled "T2D" and "IGF1", because `find_records` requires every word to match. In R16 and R31 the model then gave up. In R17, after the same failed search, it retried with "T2D" and succeeded. R32 got the correct verdict, `insufficient_evidence`, because no record was found, not because P = 2.96×10⁻⁶ is above the stated 10⁻⁶. |
| Meaning of "maternal-specific" | R10 | Both parental effects are significant, with the maternal one larger. The model read "maternal-specific" as excluding any significant paternal effect, which departs from rule B. |
| Inconsistent reasoning | R12 | The explanation states the conditions for `supported` and then concludes `contradicted`. The same pattern in R11 was answered `supported`. |
| Absence of evidence | R15 | A non-significant paternal effect (P = 0.14) was treated as evidence against the claim. |
| Allele orientation, and verdict contradicting explanation | R18 | The model assumed C is the non-effect allele, which the record does not state. It reasoned to `contradicted` but submitted `supported`. |

### Interpretation

1. **Tools removed the numeric and evidence-substitution errors.** No with-tools run misjudged a p-value threshold or used another variant's record.
2. **The baseline's main problem is that its verdicts don't follow its own explanations.** This happened in 6 of 32 no-tools claims, against 1 of 32 with tools. A likely cause: `submit_verdict` lists `verdict` before `explanation`, so in a single call the model commits to a label before writing its reasoning. In the agent condition, most of the reasoning has already happened across the earlier tool calls. This is a hypothesis; it has not been tested.
3. **The agent's main weakness is retrieval, not statistics.** Three claims (R16, R31, R32) depended on spelling variants of trait names. R32 shows that accuracy alone can overstate performance: a verdict can be right for the wrong reason.
4. **Rule wording still matters.** R10 and R12 involve "parent-specific" claims where both parental effects are significant. The paper's own classification separates these cases ("maternal" vs "paternal asymmetric"), and a stricter reading of "specific" is defensible.

### Sensitivity analysis: strict reading of "specific"

This analysis was defined after the run. Under a strict reading, a parent-specific claim is false when the other parent's effect is also significant. That changes the correct verdict of three claims, R10, R11 and R12, from `supported` to `contradicted`.

| Condition | Pre-registered rules | Strict reading |
| --- | --- | --- |
| agent | 26 / 32 | 27 / 32 |
| no_tools | 23 / 32 | 20 / 32 |

The primary result is the pre-registered one.

### Limitations of this run

- One model and one run per condition.
- 32 claims written by one author.
- The traces were classified by a single reader.

The fixes these failure modes suggest are listed in the [CHANGELOG](CHANGELOG.md) as candidates for the next version. They were not applied to this benchmark, and they would need new claims to evaluate them.

## Run 1: development benchmark (synthetic records)

**Run settings**

- Date: 13 November 2026
- Model: gpt-4.1-mini, temperature 0
- Rules: version 1 (before the claim-type restructuring; see [CHANGELOG](CHANGELOG.md))
- Claims: 15 parent-of-origin and 8 energy, all in the `dev` split

### Accuracy

| Domain | Condition | Correct | Accuracy (95% bootstrap CI) | Mean tool calls | Tokens in / out |
| --- | --- | --- | --- | --- | --- |
| Parent-of-origin | agent | 14 / 15 | 0.93 (0.80–1.00) | 3.4 | 34,691 / 2,443 |
| Parent-of-origin | no_tools | 11 / 15 | 0.73 (0.53–0.93) | 1.0 | 20,658 / 1,341 |
| Energy | agent | 8 / 8 | 1.00 | 2.1 | 11,434 / 899 |
| Energy | no_tools | 7 / 8 | 0.88 (0.62–1.00) | 1.0 | 5,054 / 648 |

### Paired comparison (same claims)

| | Correct only with agent | Correct only with no_tools | Exact McNemar p |
| --- | --- | --- | --- |
| Parent-of-origin | 3 (P01, P03, P07) | 0 | 0.25 |
| Energy | 1 (E04) | 0 | 1.00 |
| Both domains | 4 | 0 | 0.13 |

### Error analysis

**Errors without tools.** Every claim the baseline missed needed a calculation:

- **P01, P03, P15:** a test of the maternal–paternal difference.
- **P07:** a covariance-adjusted difference test. The claim is significant only with the covariance (p = 0.033, versus 0.099 assuming zero).
- **E04:** a missing value. The vertical depth is missing, and the claimed figure equals the measured depth. The baseline called this `contradicted`, confusing a value it couldn't check with a wrong one.

All four parent-of-origin errors without tools went to `insufficient_evidence`. When the model could not compute the test, it withheld judgement rather than inventing a result.

**Error with tools (P15).** The claim was "LOCUS_C shows a parent-of-origin effect on BMI". The correct verdict is `supported`: the difference z is −3.64, and the paternal effect is larger. The agent returned `contradicted`.

The trace shows the tool outputs were correct. The model applied the maternal-specific sub-rule ("contradicted if the paternal effect is larger") to a claim that names no parent.

The cause was a rule that bundled three claim types together. The rules were then restructured into explicit types A–G, with a "classify first, then apply one rule" instruction. Five held-out claims (P16–P20) were added to test the change.

**Efficiency.** With tools, the model often called `test_single_effect` after `test_parental_difference`, although the difference test already reports both single-parent tests. The tool description now says so.

### Interpretation

On this benchmark, the tools removed every error that depended on computation. The remaining error came from the model applying a rule written in natural language, not from the numbers. Because the benchmark is small and synthetic, these results show how the method behaves and what fails. They are not a performance estimate.
