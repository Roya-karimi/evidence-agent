# poe_published_v2 — agent / system v2 — gpt-4.1-mini

Claims: 26  
Accuracy: 0.85 (95% bootstrap CI 0.69–0.96)  
No verdict: 0  
Verdict/explanation mismatches (heuristic flag): V03  
Mean tool calls: 4.0  
Tokens (prompt / completion): 146224 / 5748

## Recall by true verdict

| True verdict | Correct / total |
| --- | --- |
| supported | 12 / 12 |
| contradicted | 6 / 7 |
| insufficient_evidence | 4 / 7 |

## Confusion matrix (rows = true, columns = predicted)

| | supported | contradicted | insufficient_evidence | no_verdict |
|---|---|---|---|---|
| supported | 12 | 0 | 0 | 0 |
| contradicted | 1 | 6 | 0 | 0 |
| insufficient_evidence | 0 | 3 | 4 | 0 |

## Accuracy by split

| Split | Correct / total |
| --- | --- |
| test_v2 | 22 / 26 |

## Accuracy by trap type

| Trap type | Correct / total |
| --- | --- |
| allele_not_recorded | 0 / 1 |
| both_significant | 2 / 3 |
| causal_overreach | 0 / 1 |
| equivalence_claim | 1 / 1 |
| gene_level | 1 / 1 |
| larger_parent | 2 / 2 |
| none | 3 / 3 |
| numeric | 1 / 1 |
| opposite_direction | 2 / 2 |
| same_direction | 1 / 1 |
| single_effect_ns | 2 / 2 |
| threshold | 2 / 2 |
| trait_synonym | 4 / 4 |
| trait_synonym_threshold | 0 / 1 |
| wrong_variant_trait | 1 / 1 |

## Errors

- **V03** (true: insufficient_evidence, predicted: contradicted): rs10239342 shows a genome-wide significant (P < 5e-8) parent-of-origin effect on sex hormone-binding globulin.
- **V04** (true: contradicted, predicted: supported): rs12528876 has a paternal-specific effect on IGF-1 level.
- **V14** (true: insufficient_evidence, predicted: contradicted): The paternally inherited C allele of rs217215 is associated with higher creatinine level.
- **V22** (true: insufficient_evidence, predicted: contradicted): rs77708343 increases standing height through IGF2 overexpression when paternally inherited.
