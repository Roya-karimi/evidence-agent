# Pilot: does the review catch what it should?

A small check of the review workflow on 14 draft-style sentences about Table 1 of Hofmeister et al. (2025). Nine sentences have a problem and five are sound.

| Problem | Sentences |
| --- | --- |
| a number that differs from the table | 1 |
| the wrong direction of an effect | 1 |
| a significance threshold that is not met | 1 |
| a parent-of-origin pattern the table contradicts | 2 |
| wording stronger than the table can support | 1 |
| a trait the table does not hold for that variant | 1 |
| an allele the table does not record | 1 |
| a statement about mechanism | 1 |

## Files

- `statements.txt`: the 14 sentences, as a researcher would supply them.
- `expected.csv`: the expected finding for each sentence, with the reason.

## Expected findings

The expected findings were drafted from the decision rules and then reviewed by the author on 14 November 2026, before the tool was run on these sentences. The review changed two of them, and the review rules with them (`data/review/rules.md`):

- **S05**, "genome-wide significant" with a reported P of 2.59e-6. The draft said insufficient evidence. It is now contradicted: the sentence is about the reported test, and the p-value does not meet the threshold. That says the wording is wrong, not that there is no effect.
- **S04**, "specific to the maternally inherited allele", with a non-significant paternal estimate. The draft said supported, and the sentence had been written as a sound one. It is now insufficient evidence: a non-significant estimate does not show that the paternal effect is zero.

`python scripts/verify_gold.py poe_published pilot/expected.csv` confirms that all 14 expected findings follow from the rules.

## Procedure

```
python -m evidence_agent review --statements pilot/statements.txt --out review_output/pilot
python scripts/score_pilot.py review_output/pilot/review.csv
```

## What is counted

- Problems caught: problem sentences that were flagged (any finding other than "supported").
- Problems missed: problem sentences returned as supported.
- False alarms: sound sentences that were flagged.
- Same finding: the review gives exactly the expected finding.
- Source row right: the cited rows include the expected row and no row of another variant.
- Time: the model calls. Time to read the output is reported only if it was measured.

## Result (14 November 2026, gpt-4.1-mini)

| Problems caught | Problems missed | False alarms | Same finding as expected | Source row right | Model time |
| --- | --- | --- | --- | --- | --- |
| 8 / 9 | 1 / 9 | 0 / 5 | 13 / 14 | 14 / 14 | 51 s |

The miss was S04: the model returned `supported` for "specific to the maternally inherited allele". Reading time was not measured. The full account is in [docs/RESULTS.md](../docs/RESULTS.md), and the output is in `results/review_pilot_20261114/`.

## Limits

- 14 sentences, on a table that was also used to develop the checker. This shows whether the workflow is usable. It is not an accuracy estimate.
- The sentences and expected findings were written for this pilot, and one person reviewed them.
- There is no comparison with a review by hand, so the pilot does not show a time saving.
