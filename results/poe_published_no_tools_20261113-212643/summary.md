# poe_published — no_tools — gpt-4.1-mini — 20261113-212643

Claims: 32  
Accuracy: 0.72 (95% bootstrap CI 0.56–0.88)  
No verdict: 0  
Mean tool calls: 1.0  
Tokens (prompt / completion): 224495 / 3983

## Recall by true verdict

| True verdict | Correct / total |
| --- | --- |
| supported | 15 / 15 |
| contradicted | 4 / 7 |
| insufficient_evidence | 4 / 10 |

## Confusion matrix (rows = true, columns = predicted)

| | supported | contradicted | insufficient_evidence | no_verdict |
|---|---|---|---|---|
| supported | 15 | 0 | 0 | 0 |
| contradicted | 3 | 4 | 0 | 0 |
| insufficient_evidence | 5 | 1 | 4 | 0 |

## Accuracy by split

| Split | Correct / total |
| --- | --- |
| test | 23 / 32 |

## Accuracy by trap type

| Trap type | Correct / total |
| --- | --- |
| allele_not_recorded | 0 / 1 |
| binary_trait | 1 / 1 |
| both_significant | 2 / 2 |
| causal_overreach | 1 / 1 |
| equivalence_claim | 1 / 1 |
| gene_level | 1 / 1 |
| label_mismatch | 1 / 1 |
| none | 9 / 9 |
| not_in_records | 1 / 1 |
| numeric | 2 / 2 |
| opposite_direction | 1 / 1 |
| rounding | 0 / 1 |
| same_direction | 0 / 1 |
| single_effect_ns | 0 / 2 |
| threshold | 1 / 2 |
| wrong_parent | 1 / 3 |
| wrong_variant_trait | 1 / 2 |

## Errors

- **R02** (true: insufficient_evidence, predicted: supported): rs77708343 shows a genome-wide significant (P < 5e-8) parent-of-origin effect on basal metabolic rate.
- **R03** (true: insufficient_evidence, predicted: supported): rs4264135 shows a genome-wide significant (P < 5e-8) parent-of-origin effect on urate level.
- **R05** (true: insufficient_evidence, predicted: supported): rs80116540 shows a parent-of-origin effect on leg fat percentage.
- **R09** (true: contradicted, predicted: supported): rs11100479 has a maternal-specific effect on telomere length.
- **R13** (true: contradicted, predicted: supported): rs2299620 has a paternal-specific effect on HbA1c.
- **R15** (true: insufficient_evidence, predicted: contradicted): The paternally inherited T allele of rs143840904 is associated with lower standing height.
- **R18** (true: insufficient_evidence, predicted: supported): The maternally inherited C allele of rs143840904 is associated with lower standing height.
- **R23** (true: contradicted, predicted: supported): The maternal and paternal effects of rs2293607 on telomere length go in opposite directions.
- **R24** (true: insufficient_evidence, predicted: supported): The maternal and paternal effects of rs3847104 on hip circumference go in opposite directions.
