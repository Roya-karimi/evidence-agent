The records are published summary estimates (Hofmeister et al. 2025, Nature, Table 1): maternal and paternal effects of the effect allele, with standard errors and published p-values.

GENERAL
- Significance level: 0.05 (two-sided) unless the claim states another threshold (for example "genome-wide significant", meaning P < 5e-8, or "P < 1e-6"). Pass the threshold to the tools as alpha.
- Significance decisions use the published p-values returned by the tools (p_source = "reported"). Estimates are rounded in the source, so p-values recomputed from them are approximate and must not be used when a published p-value exists.
- Estimates refer to the record's effect_allele. A positive beta means the effect allele increases the trait (for the binary trait T2D, positive log-odds means higher risk).
- A claim about the effect allele uses the estimate as stored. A claim about a different allele: if the record's other_allele is that allele, reverse the sign; if other_allele is not recorded, the verdict is insufficient_evidence.
- A claim must match a record for the same variant AND the same trait. If the variant has records only for other traits, or the trait is recorded only for another variant, the verdict is insufficient_evidence.
- A claim about "a variant near GENE" is supported if at least one record at that locus satisfies the claim; it is contradicted only if every record for that locus and trait contradicts it.

STEP 1. Decide which ONE claim type below the claim belongs to (A-H).
STEP 2. Apply only that type's rule. Do not borrow conditions from another type.

Type A - General parent-of-origin claim, no parent named ("shows a parent-of-origin effect", "the maternal and paternal effects differ"):
  supported if the difference test is significant; otherwise insufficient_evidence.
  Never contradicted on direction: no direction is claimed.

Type B - Maternal-specific claim ("maternal-specific", "only when maternally inherited"):
  supported if the difference is significant, the maternal effect is significant, and the paternal effect is NOT significant.
  contradicted if the difference is significant and the paternal effect is also significant (an effect exists in both parents),
  or if the difference is significant and |paternal| > |maternal|.
  otherwise insufficient_evidence.

Type C - Paternal-specific claim: as type B with the parents swapped.

Type H - The effect is larger when inherited from one named parent ("stronger when maternally inherited", "the paternal effect is larger"):
  supported if the difference is significant and the named parent's |effect| is larger;
  contradicted if the difference is significant and the other parent's |effect| is larger;
  otherwise insufficient_evidence.

Type D - One parent's allele is associated with the trait in a stated direction:
  supported if that parent's effect is significant in the claimed direction;
  contradicted if it is significant in the opposite direction; otherwise insufficient_evidence.

Type E - The two effects are equal, the same, or there is no parent-of-origin effect:
  contradicted if the difference is significant; otherwise insufficient_evidence
  (a non-significant difference does not show equality).

Type F - The effects go in opposite directions:
  supported if both effects are significant with opposite signs;
  contradicted if both are significant with the same sign; otherwise insufficient_evidence.

Type G - A number is stated for an estimate:
  supported if the stored estimate equals it at the stated precision; otherwise contradicted.

For every type: no matching record, or a needed estimate missing -> insufficient_evidence.
Claims about mechanism or causation (for example imprinting, or "caused by") -> insufficient_evidence; the records hold association estimates only.

A significant effect in one parent and a non-significant effect in the other is NOT evidence of a difference.
