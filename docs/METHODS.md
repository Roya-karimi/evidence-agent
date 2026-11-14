# Methods

## 1. Task

Each input is one natural-language claim and one domain. The output is a verdict, `supported`, `contradicted` or `insufficient_evidence`, together with the IDs of the records used and a short explanation. Verdicts are defined by the domain's decision rules (`data/<domain>/rules.md`), not by the model's background knowledge.

## 2. Agent loop

`evidence_agent/agent.py` runs a standard tool-calling loop on the OpenAI Chat Completions API:

1. Messages: a system prompt (task definition + decision rules) and the claim.
2. The model must respond with tool calls (`tool_choice="required"`), so it cannot answer in free text.
3. Each call's arguments are checked against the tool's schema: object shape, required and unknown fields, types, enumerated values and finite numbers. A valid call is executed in Python, and the result is returned as a `tool` message. An invalid call is returned as an error, so the model can correct it.
4. The loop ends when the model submits a verdict that passes the acceptance checks below, or after 8 rounds.

**Acceptance checks for a verdict.** `submit_verdict` is itself a tool, so requiring a tool call does not by itself force an evidence lookup. A verdict is accepted only if:

- its arguments fit the schema and the explanation is not empty;
- it is the only call in its turn, so the model has seen every result it relies on;
- with tools: at least one evidence tool has returned a result, every cited record ID was returned by a tool, and a `supported` or `contradicted` verdict cites at least one record whose estimates were retrieved;
- without tools: every cited ID exists in the records, and a `supported` or `contradicted` verdict cites at least one.

A rejected verdict is returned to the model as an error. These checks are structural. They show that a verdict cites evidence that was looked up; whether the verdict is right is what the evaluation measures.

**Outcomes.** Each claim ends with one of three statuses: `ok` (a verdict was accepted), `no_valid_verdict` (the model did not produce an acceptable verdict within 8 rounds) or `operational_error` (the model call failed). An operational error is never recorded as `insufficient_evidence`.

Temperature is 0. Each request has a 60-second time limit, at most 2 retries and a 1,000-token output limit. Each run records the full trace, token use and latency.

## 3. Tool design

- **IDs, not numbers.** Lookup and test tools take a record ID. The only numbers the model passes are values stated in the claim itself. This removes transcription and invention of estimates as error sources.
- **All arithmetic in Python.** That includes statistical tests, unit conversion (feet to metres) and tolerances. A value stated in a claim is passed as text, so the tool can read its precision: an exact value must match within half a unit of its last written digit, and an "about" value within 1% of the record value.
- **Structured final answer.** The verdict is a tool call with an enumerated verdict field and an evidence list, so every output can be scored automatically.
- **Explicit "not found".** Missing records and missing values come back as `found: false`, or as a null value with a note, never as an error the model might work around by guessing.

## 4. Statistics (`evidence_agent/stats.py`)

**Single-parent effect.** A Wald test of H0: β = 0, with z = β / SE and a two-sided normal p-value.

**Maternal–paternal difference.** A test of H0: β_m − β_p = 0.

```
diff    = β_m − β_p
SE_diff = sqrt(SE_m² + SE_p² − 2·Cov(β_m, β_p))
z       = diff / SE_diff
```

The test gives a two-sided p-value and a (1 − α) confidence interval for the difference.

**Covariance is never assumed.** Estimates from the same trio regression are correlated, and the covariance should come from that model's variance–covariance matrix. The difference test therefore has three cases:

1. The record has a published p-value for the difference. That p-value is the result. No SE, z or confidence interval of the difference is returned, because the source gives rounded estimates and no covariance.
2. The record has a stored covariance. The test is computed with it.
3. The record has neither. The test is reported as unavailable.

The synthetic records state their covariance explicitly. In that benchmark, locus F is significant only with its covariance (p = 0.033 with it, p = 0.099 with zero).

**Magnitude claims.** "The paternal effect is larger" is a claim about |β_p| and |β_m|. When the two estimates have the same sign, the difference test addresses it. When they have opposite signs, equal magnitudes means β_m + β_p = 0, a different contrast with variance SE_m² + SE_p² + 2·Cov. The published records hold neither that test nor the covariance, so such a claim is `insufficient_evidence`. The tool reports `effect_signs` so that the model does not have to work this out.

**Input checks.** The statistics functions reject non-finite numbers, non-positive standard errors, α outside (0, 1), and a covariance larger in absolute value than SE_m·SE_p.

**Equality claims.** A non-significant difference never supports a claim that two effects are equal. Supporting equality would need an equivalence test with a pre-specified margin, which is not implemented.

## 5. Decision rules (parent-of-origin)

Claims are first classified into exactly one type, and only that type's rule is applied:

| Type | Claim | Supported when | Contradicted when |
| --- | --- | --- | --- |
| A | General parent-of-origin effect (no parent named) | difference significant | never (no direction claimed) |
| B | Maternal-specific | difference significant, maternal significant, \|β_m\| > \|β_p\| | difference significant and \|β_p\| > \|β_m\| |
| C | Paternal-specific | as B with the parents swapped | as B with the parents swapped |
| D | One parent's allele associated with the trait | that effect significant in the claimed direction | significant in the opposite direction |
| E | Effects equal / no parent-of-origin effect | never | difference significant |
| F | Effects in opposite directions | both significant, opposite signs | both significant, same sign |
| G | A stated value for an estimate | the stored value matches at the stated precision | it does not match |

In every other case, the verdict is `insufficient_evidence`. That includes missing records or estimates, and any claim about mechanism or causation, because the records contain association estimates only. The default α is 0.05. The full wording is in `data/poe/rules.md`.

## 6. Published parent-of-origin benchmark

**Records.** All 30 parent-of-origin effects in Table 1 of Hofmeister et al. (2025):
- 25 variants and 23 traits, from UK Biobank, with parental origin inferred from relatives
- for each: the effect allele, the maternal and paternal β, SE and p, and the p-value of the direct differential scan

Quantitative traits were inverse-normal transformed, so β is in SD units. T2D β is on the log-odds scale. That is inferred from the paper's odds ratios, not stated in the table.

The published pattern label (bipolar, maternal, paternal) is **not** stored. The agent has to reason from the estimates, not from the authors' conclusion.

**Published p-values take priority.** Table 1 rounds β and SE to three decimals, so p-values recomputed from them can differ from the exact ones by about an order of magnitude. When a record holds a published p-value, the tools return it, flag it as `reported`, and base significance decisions on it. The recomputed value is shown only for reference. Claim R03 tests this: the rounded estimates give P ≈ 3×10⁻⁸ for rs4264135 and urate, below the genome-wide threshold, but the published value is 2.2×10⁻⁷, above it.

**Extra rules for published data:**
- **Thresholds.** A threshold stated in the claim (for example "genome-wide significant", meaning P < 5×10⁻⁸) is passed to the tests as α.
- **Alleles.** Estimates refer to the stored effect allele. A claim about the other allele reverses the sign only if that allele is recorded. Otherwise the verdict is `insufficient_evidence`, because the table does not report the non-effect allele.
- **Variant and trait must both match.** A claim about a recorded variant but a different trait, or a recorded trait but a different variant, is `insufficient_evidence`.
- **Gene-level claims** ("a variant near KLF14…") are `supported` if at least one record at that locus satisfies them.

**Differences from the paper's classification.** The paper classifies patterns by the ratio of Z-scores, for example "maternal" when |Z_pat| < 0.5·|Z_mat|. Our types B and C instead test the claim as stated: a significant difference, a significant effect in the named parent, and the larger magnitude in that parent. A locus where both parental effects are significant but the maternal one is larger (rs7705526, TERT) therefore counts as maternal-specific here; the paper would call it maternal or maternal-asymmetric. Likewise, a claim that two effects go in opposite directions (type F) can be supported where the paper's label is "paternal" (rs4264135, urate), because both effects are individually significant with opposite signs.

**Retrieval.** A `find_records` tool searches record IDs, rsIDs, locus names and traits, so the agent can map a claim to the right record before testing it.

**Claims.** 32 claims cover types A–G, causal-overreach claims, and gene-level claims. Traps include:
- stated thresholds
- the rounding case
- the right variant with the wrong trait
- alleles that are not recorded
- both parental effects significant
- a claim that is true in the paper but outside the stored records
- a pattern that contradicts the paper's label

The verdicts are 15 `supported`, 7 `contradicted` and 10 `insufficient_evidence`.

**Gold verification.** `scripts/verify_gold.py` re-derives every gold verdict from structured columns in `claims.csv` (claim type, record IDs, parent, allele, direction, value, threshold). It uses the same statistical tools as the agent and never calls the model. All 32 verdicts are reproduced, and the test suite runs the check.

**Rules fixed in advance.** The decision rules for this benchmark were written before any model was run on it, and every claim belongs to the `test` split. The rules and plans in this project were not registered externally, and the repository's public history begins after Runs 2 and 3. From commit `6a79fb1` onwards, the git history records when each rule, claim and plan changed.

**Thresholds.** The paper identifies parent-of-origin effects with its own study-specific discovery thresholds. This benchmark tests agreement with its own rules at α = 0.05 or at a threshold stated in the claim. It does not reproduce the paper's discovery classification.

## 7. Version 2 and its test

The Run 2 traces pointed to three failure modes ([RESULTS](RESULTS.md)). Version 2 addresses each one. All three changes, the new claims and the analysis plan below were fixed before any version 2 run.

| Change | What it does | Failure it targets |
| --- | --- | --- |
| rsID-first search | If a query contains an rsID, `find_records` returns every record for that variant whatever the other words. Otherwise words are normalised ("IGF-1" → "igf1", "%" → "percentage") and must all match. | Records hidden by trait spellings (R16, R31, R32) |
| Explanation-first verdict | `submit_verdict` asks for the explanation before the verdict, and the prompt says to choose the verdict that follows from it. | Verdicts that contradict the model's own explanation (6 of 32 claims without tools) |
| Explicit parent-specific rules | "Maternal-/paternal-specific" now means the named parent's effect is significant and the other parent's is not (type B/C). A separate type H covers "larger when inherited from" one parent. | Disagreement over the meaning of "specific" (R10, R12) |

The strict "specific" rule treats a non-significant effect in the other parent as consistent with specificity. That matches common practice in the parent-of-origin literature, but it is a convention: a non-significant estimate does not show that the effect is absent.

**New test set.** `poe_published_v2` reuses the 30 published records with 26 new claims. Their verdicts are 12 supported, 7 contradicted and 7 insufficient evidence. They are written to probe the targeted failure modes:

- trait synonyms
- parent-specific claims where both parents' effects are significant
- thresholds, alleles that are not recorded, non-significant single effects
- claims about the wrong variant–trait pair

None repeats the wording of a Run 2 claim. One, V08, makes the same assertion as R31 (a maternal-specific effect of rs7188903 on IGF-1) with a different trait spelling; it is a regression case, not a new assertion. All 26 verdicts were reproduced by `scripts/verify_gold.py` under rules v2.

**Design.** A 2×2 comparison on the same 26 claims: system v1 or v2 (`--system`), crossed with tools or no tools (`--mode`). Both systems use the version 2 rules, so the comparison isolates the two system changes.

**Hypotheses.**

- **H1 (search).** With tools, v2 resolves the trait-synonym claims that v1 cannot retrieve. Comparison: `agent/v2` vs `agent/v1`.
- **H2 (explanation first).** Without tools, v2 has fewer verdict–explanation mismatches than v1. Comparing the two no-tools runs isolates this change, because search is not used without tools.

**Analysis.**

- Accuracy with a bootstrap CI.
- Asserted errors, meaning `supported` or `contradicted` when the correct verdict differs.
- Verdict–explanation mismatches, flagged automatically from the explanation's final sentence. The flag was validated on Run 2: it found the 4 clear no-tools mismatches and the 1 with-tools mismatch.
- Paired exact McNemar tests for each pair.

With 26 claims only large differences are detectable, so results are reported as counts with the claims named.

Results: [RESULTS, Run 3](RESULTS.md#run-3-version-2-test-26-new-claims).

**Correction: rules v2.1.** After Run 3, an external review showed that rule H was wrong for estimates with opposite signs (see "Magnitude claims" in §4). `data/poe_published_v2_1/` holds the corrected rules and labels:

- Rule H returns `insufficient_evidence` when the two estimates have opposite signs.
- The parent-specific rules (B, C) no longer use a magnitude comparison. A parent-specific claim is `contradicted` when the difference is significant and the other parent's effect is significant.
- One label changes: V05, from `supported` to `insufficient_evidence`. The v2.1 verdicts are 11 supported, 7 contradicted and 8 insufficient evidence.

`data/poe_published_v2/` keeps the rules and labels as they were given to the model in Run 3. `verify_gold.py` implements the corrected rules: it reproduces 26 of 26 labels in v2.1, and reports V05 in the as-run file as superseded. The same script cannot catch an error in a rule, because it implements that rule; this error was found by review, not by the check.

## 8. Evaluation design

- **Labelled claims.** Each claim has a verdict assigned by the author before any model run, an error-type tag (the trap it is designed to test), and a split.
- **Splits.** `dev` claims were available while the rules were developed. `heldout` claims were written after the last rule change, to check that changes generalise beyond the claims that motivated them.
- **Conditions.** `agent` (tools) vs `no_tools`, where the model sees all records as JSON in its prompt and can only call `submit_verdict`. The difference estimates what the tools contribute.
- **Metrics.**
    - accuracy with a 95% percentile bootstrap CI (2,000 resamples of claims)
    - recall for each true verdict
    - a confusion matrix
    - accuracy by error type and by split
    - mean tool calls and tokens
- **Reference point.** A model that always answers the most common verdict scores 15/32 (0.47) on the published benchmark and 9/20 on the synthetic parent-of-origin set. Results are read against that floor.
- **Paired comparison.** Both conditions run on the same claims, so they are compared on the discordant claims with an exact McNemar test (`python -m evidence_agent compare`). The comparison refuses runs with duplicate claim IDs, different claim sets, or claims whose text or label differ.
- **Shared records.** Several claims concern the same variant, so claims are not independent. `scripts/score_saved_runs.py` adds a bootstrap that resamples variants instead of claims. All intervals and tests are exploratory and describe this claim set only.
- **Error severity.** The confusion matrix is read asymmetrically. Calling an unresolved claim `contradicted` (or `supported`) states something the records do not establish. That is more serious than returning `insufficient_evidence` for a claim that could have been decided.

## 9. Reproducibility

Every run is saved to `results/<domain>_<mode>_<system>_<timestamp>/`:
- `runs.jsonl` holds, for each claim, the status, the model name, every tool call with its arguments and result, the verdict, tokens and latency. It is written claim by claim, so an interrupted run keeps what finished.
- `summary.md` holds the metrics. It is marked incomplete if any model call failed.
- `manifest.json` holds the model requested and the model the API reports, the request settings, SHA-256 hashes of the rules, claims, records and code, the git commit, the Python and `openai` versions, and the number of claims that finished, failed or were not attempted.

Runs 2 and 3 were made at commit `6a79fb1`, before the manifest existed. They record the requested model name only. `python scripts/score_saved_runs.py` recounts them from the saved traces.

The offline test suite (`tests/`) checks the statistics against known values, and exercises the agent loop and the evaluation pipeline with a scripted model, without any API calls.
