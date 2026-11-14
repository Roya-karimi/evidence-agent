# Data

Each domain folder holds:

| File | Content |
| --- | --- |
| `records.csv` | Source records, one row per locus–trait or well, with a `source` column |
| `rules.md` | Decision rules, read verbatim by the model |
| `claims.csv` | Labelled claims: `claim_id`, `claim`, `gold_verdict`, `trap_type`, `split`, `notes`. The published benchmark also has structured columns used only by `scripts/verify_gold.py`. |

## Domains

| Domain | Records | Status |
| --- | --- | --- |
| `poe_published` | 30 published estimates | Test benchmark (Run 2); rules fixed before any model run |
| `poe_published_v2` | The same 30 records (read from `poe_published`) | 26 test claims and rules v2, as given to the model in Run 3. Kept unchanged. |
| `poe_published_v2_1` | The same 30 records | Corrected rules v2.1 and labels: magnitude claims with opposite-sign estimates are `insufficient_evidence`; V05 relabelled. |
| `review` | No records of its own | Rules for the `review` command: v2.1 with two changes from the author's review (stated significance levels; parent-specific wording). See `pilot/README.md`. |
| `poe` | Synthetic loci (`LOCUS_A` …) built to exercise each rule | Development benchmark |
| `energy` | Synthetic wells (`WELL-T1` …) | Development benchmark |

The synthetic records don't report any real estimate. The synthetic parent-of-origin records state their maternal–paternal covariance explicitly (0, except `LOCUS_F`).

## `poe_published`: source and provenance

**Source:** Hofmeister RJ, Cavinato T, Karimi R, et al. "Parent-of-origin effects on complex traits in up to 236,781 individuals". *Nature* (2025). [doi:10.1038/s41586-025-09357-5](https://doi.org/10.1038/s41586-025-09357-5), PMCID PMC12527933.

**Licence:** [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).

**What is reused:** the numerical values of Table 1 ("Significant POEs identified in this study"):
- effect allele (A1)
- maternal and paternal β, SE and p
- p-value of the differential test

**Changes from the source:**
- One row per variant–trait.
- Locus typo "KFL14" corrected to KLF14.
- The POE pattern column (B/M/P/PA) left out of `records.csv`, so the agent cannot read the authors' conclusion.
- A trait-scale note added.

No text from the article is reproduced.

**Files:**
- `source/hofmeister2025_table1_extracted.csv`: Table 1 as extracted, including the published pattern labels, scan flags and positions (hg19).
- `records.csv`: built from it by `scripts/build_poe_published.py`.

**Scale:**
- Quantitative traits were averaged over visits and inverse-normal transformed, so β is in SD units.
- For T2D, β is taken as log-odds. This is consistent with the odds ratios reported in the text (exp(0.136) ≈ 1.14 paternal; exp(−0.091) ≈ 0.91 maternal), but the table doesn't state it.

**Known limits:**
- β and SE are rounded to three decimals. The tools therefore use the published p-values for every significance decision.
- The other allele and the maternal–paternal covariance are not reported. The tools therefore use the published p-value of the difference and return no SE or confidence interval for it.
- **Verification:** the values were transcribed from the PMC version of Table 1. A second, independent reading used the article's own column order (paternal before maternal), so any swap of the parental columns would show up. All 240 values (30 rows × 8 values, including effect alleles) were identical.
