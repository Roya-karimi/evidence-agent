# poe_published_v2 — agent / system v1 — gpt-4.1-mini

Claims: 26  
Accuracy: 0.77 (95% bootstrap CI 0.62–0.92)  
No verdict: 0  
Verdict/explanation mismatches (heuristic flag): none  
Mean tool calls: 3.7  
Tokens (prompt / completion): 140700 / 4497

## Recall by true verdict

| True verdict | Correct / total |
| --- | --- |
| supported | 10 / 12 |
| contradicted | 6 / 7 |
| insufficient_evidence | 4 / 7 |

## Confusion matrix (rows = true, columns = predicted)

| | supported | contradicted | insufficient_evidence | no_verdict |
|---|---|---|---|---|
| supported | 10 | 1 | 1 | 0 |
| contradicted | 0 | 6 | 1 | 0 |
| insufficient_evidence | 2 | 1 | 4 | 0 |

## Accuracy by split

| Split | Correct / total |
| --- | --- |
| test_v2 | 20 / 26 |

## Accuracy by trap type

| Trap type | Correct / total |
| --- | --- |
| allele_not_recorded | 0 / 1 |
| both_significant | 2 / 3 |
| causal_overreach | 0 / 1 |
| equivalence_claim | 1 / 1 |
| gene_level | 1 / 1 |
| larger_parent | 2 / 2 |
| none | 2 / 3 |
| numeric | 1 / 1 |
| opposite_direction | 2 / 2 |
| same_direction | 1 / 1 |
| single_effect_ns | 1 / 2 |
| threshold | 2 / 2 |
| trait_synonym | 3 / 4 |
| trait_synonym_threshold | 1 / 1 |
| wrong_variant_trait | 1 / 1 |

## Errors

- **V04** (true: contradicted, predicted: insufficient_evidence): rs12528876 has a paternal-specific effect on IGF-1 level.
- **V11** (true: supported, predicted: contradicted): The maternally inherited G allele of rs146982369 is associated with lower total protein level.
- **V12** (true: supported, predicted: insufficient_evidence): The paternally inherited A allele of rs62471721 is associated with lower triglycerides.
- **V14** (true: insufficient_evidence, predicted: supported): The paternally inherited C allele of rs217215 is associated with higher creatinine level.
- **V22** (true: insufficient_evidence, predicted: supported): rs77708343 increases standing height through IGF2 overexpression when paternally inherited.
- **V23** (true: insufficient_evidence, predicted: contradicted): The paternally inherited T allele of rs2299620 is associated with lower HbA1c.
