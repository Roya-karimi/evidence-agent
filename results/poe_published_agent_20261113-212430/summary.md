# poe_published — agent — gpt-4.1-mini — 20261113-212430

Claims: 32  
Accuracy: 0.81 (95% bootstrap CI 0.69–0.94)  
No verdict: 0  
Mean tool calls: 3.4  
Tokens (prompt / completion): 151148 / 5459

## Recall by true verdict

| True verdict | Correct / total |
| --- | --- |
| supported | 11 / 15 |
| contradicted | 7 / 7 |
| insufficient_evidence | 8 / 10 |

## Confusion matrix (rows = true, columns = predicted)

| | supported | contradicted | insufficient_evidence | no_verdict |
|---|---|---|---|---|
| supported | 11 | 2 | 2 | 0 |
| contradicted | 0 | 7 | 0 | 0 |
| insufficient_evidence | 1 | 1 | 8 | 0 |

## Accuracy by split

| Split | Correct / total |
| --- | --- |
| test | 26 / 32 |

## Accuracy by trap type

| Trap type | Correct / total |
| --- | --- |
| allele_not_recorded | 0 / 1 |
| binary_trait | 0 / 1 |
| both_significant | 0 / 2 |
| causal_overreach | 1 / 1 |
| equivalence_claim | 1 / 1 |
| gene_level | 1 / 1 |
| label_mismatch | 1 / 1 |
| none | 8 / 9 |
| not_in_records | 1 / 1 |
| numeric | 2 / 2 |
| opposite_direction | 1 / 1 |
| rounding | 1 / 1 |
| same_direction | 1 / 1 |
| single_effect_ns | 1 / 2 |
| threshold | 2 / 2 |
| wrong_parent | 3 / 3 |
| wrong_variant_trait | 2 / 2 |

## Errors

- **R10** (true: supported, predicted: contradicted): rs7705526 has a maternal-specific effect on telomere length.
- **R12** (true: supported, predicted: contradicted): rs2293607 has a paternal-specific effect on telomere length.
- **R15** (true: insufficient_evidence, predicted: contradicted): The paternally inherited T allele of rs143840904 is associated with lower standing height.
- **R16** (true: supported, predicted: insufficient_evidence): The paternally inherited A allele of rs10838787 is associated with higher type 2 diabetes risk.
- **R18** (true: insufficient_evidence, predicted: supported): The maternally inherited C allele of rs143840904 is associated with lower standing height.
- **R31** (true: supported, predicted: insufficient_evidence): rs7188903 has a maternal-specific effect on IGF-1 level.
