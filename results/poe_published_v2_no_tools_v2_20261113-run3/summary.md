# poe_published_v2 — no_tools / system v2 — gpt-4.1-mini

Claims: 26  
Accuracy: 0.92 (95% bootstrap CI 0.81–1.00)  
No verdict: 0  
Verdict/explanation mismatches (heuristic flag): none  
Mean tool calls: 1.0  
Tokens (prompt / completion): 186213 / 3346

## Recall by true verdict

| True verdict | Correct / total |
| --- | --- |
| supported | 12 / 12 |
| contradicted | 7 / 7 |
| insufficient_evidence | 5 / 7 |

## Confusion matrix (rows = true, columns = predicted)

| | supported | contradicted | insufficient_evidence | no_verdict |
|---|---|---|---|---|
| supported | 12 | 0 | 0 | 0 |
| contradicted | 0 | 7 | 0 | 0 |
| insufficient_evidence | 1 | 1 | 5 | 0 |

## Accuracy by split

| Split | Correct / total |
| --- | --- |
| test_v2 | 24 / 26 |

## Accuracy by trap type

| Trap type | Correct / total |
| --- | --- |
| allele_not_recorded | 1 / 1 |
| both_significant | 3 / 3 |
| causal_overreach | 0 / 1 |
| equivalence_claim | 1 / 1 |
| gene_level | 1 / 1 |
| larger_parent | 2 / 2 |
| none | 3 / 3 |
| numeric | 1 / 1 |
| opposite_direction | 2 / 2 |
| same_direction | 1 / 1 |
| single_effect_ns | 2 / 2 |
| threshold | 1 / 2 |
| trait_synonym | 4 / 4 |
| trait_synonym_threshold | 1 / 1 |
| wrong_variant_trait | 1 / 1 |

## Errors

- **V22** (true: insufficient_evidence, predicted: contradicted): rs77708343 increases standing height through IGF2 overexpression when paternally inherited.
- **V25** (true: insufficient_evidence, predicted: supported): rs146982369 shows a parent-of-origin effect on total protein level at P < 1e-6.
