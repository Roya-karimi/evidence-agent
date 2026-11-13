# poe_published_v2 — no_tools / system v1 — gpt-4.1-mini

Claims: 26  
Accuracy: 0.73 (95% bootstrap CI 0.54–0.88)  
No verdict: 0  
Verdict/explanation mismatches (heuristic flag): V24, V26  
Mean tool calls: 1.0  
Tokens (prompt / completion): 185095 / 3260

## Recall by true verdict

| True verdict | Correct / total |
| --- | --- |
| supported | 10 / 12 |
| contradicted | 6 / 7 |
| insufficient_evidence | 3 / 7 |

## Confusion matrix (rows = true, columns = predicted)

| | supported | contradicted | insufficient_evidence | no_verdict |
|---|---|---|---|---|
| supported | 10 | 2 | 0 | 0 |
| contradicted | 1 | 6 | 0 | 0 |
| insufficient_evidence | 1 | 3 | 3 | 0 |

## Accuracy by split

| Split | Correct / total |
| --- | --- |
| test_v2 | 19 / 26 |

## Accuracy by trap type

| Trap type | Correct / total |
| --- | --- |
| allele_not_recorded | 0 / 1 |
| both_significant | 2 / 3 |
| causal_overreach | 1 / 1 |
| equivalence_claim | 1 / 1 |
| gene_level | 1 / 1 |
| larger_parent | 2 / 2 |
| none | 2 / 3 |
| numeric | 1 / 1 |
| opposite_direction | 2 / 2 |
| same_direction | 1 / 1 |
| single_effect_ns | 1 / 2 |
| threshold | 1 / 2 |
| trait_synonym | 3 / 4 |
| trait_synonym_threshold | 0 / 1 |
| wrong_variant_trait | 1 / 1 |

## Errors

- **V03** (true: insufficient_evidence, predicted: contradicted): rs10239342 shows a genome-wide significant (P < 5e-8) parent-of-origin effect on sex hormone-binding globulin.
- **V09** (true: supported, predicted: contradicted): The paternally inherited T allele of rs4417225 is associated with higher glucose level.
- **V12** (true: supported, predicted: contradicted): The paternally inherited A allele of rs62471721 is associated with lower triglycerides.
- **V13** (true: insufficient_evidence, predicted: contradicted): The paternally inherited G allele of rs7188903 is associated with lower IGF-1 level.
- **V14** (true: insufficient_evidence, predicted: contradicted): The paternally inherited C allele of rs217215 is associated with higher creatinine level.
- **V24** (true: contradicted, predicted: supported): rs4417225 has a paternal-specific effect on glucose level.
- **V25** (true: insufficient_evidence, predicted: supported): rs146982369 shows a parent-of-origin effect on total protein level at P < 1e-6.
