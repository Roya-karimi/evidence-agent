# Evidence agent

An LLM agent that checks scientific and technical claims against source records, and an evaluation framework that measures how often it reaches the correct verdict, and why it fails when it does not.

**Status:** the agent and evaluation pipeline work. A test benchmark of 32 claims against published parent-of-origin estimates (Hofmeister et al. 2025, *Nature*) has been run with and without tools, and its decision rules were fixed before the run. A synthetic development benchmark is also included. Version 2 targets the failure modes found in Run 2, and was evaluated on 26 new claims under a pre-registered plan (Run 3).

## Motivation

When language models summarise evidence, two kinds of error are common:

- **Factual errors:** a number is copied wrongly, or two similar fields are confused (measured vs vertical depth).
- **Inferential errors:** "not shown" is reported as "shown false", or "significant in one group but not the other" is reported as "the groups differ".

This project separates the two jobs. The model decides **which checks to run**. Deterministic Python tools **look up the records and compute every statistic**. The model then applies explicit decision rules and returns one of three verdicts.

| Verdict | Meaning |
| --- | --- |
| `supported` | The records show the claim is true under the decision rules |
| `contradicted` | The records show the claim is false |
| `insufficient_evidence` | The records cannot settle the claim: missing record or value, non-significant result, or outside their scope |

Keeping `contradicted` and `insufficient_evidence` apart is central. A missing value or a non-significant test is not evidence against a claim.

## Domains

| Domain | Records | Claims | Example trap |
| --- | --- | --- | --- |
| `poe_published` (test) | 30 published parent-of-origin effects: maternal and paternal β, SE and p in UK Biobank (Hofmeister et al. 2025, Table 1) | 32 | **Rounding.** Recomputing the difference test from the rounded Table 1 estimates gives P ≈ 3×10⁻⁸ for rs4264135 and urate, but the published value is 2.2×10⁻⁷. So a "genome-wide significant" claim is `insufficient_evidence`. |
| `poe` (development) | Synthetic loci built to exercise each rule | 20 | A significant maternal and a non-significant paternal estimate do not show that the two effects differ. The difference must be tested directly, with the maternal–paternal covariance when available. |
| `energy` (development) | Synthetic well records | 8 | 3,574 m is the measured depth and the vertical depth is missing, so a claim of 3,574 m vertical depth is `insufficient_evidence`, not `contradicted`. |

Both domains use the same engine. A new domain needs a records file, a rules file, a labelled claim set and a few tools.

## How it works

```
claim ─▶ LLM ─(tool call)─▶ Python tool ─(result)─▶ LLM ─▶ … ─▶ submit_verdict
```

1. The model receives the decision rules, the claim and the tool definitions.
2. It requests lookups and tests by tool call. Tools take **record IDs, not numbers**, so the model cannot alter an estimate.
3. Python computes the statistics: Wald tests, the maternal–paternal difference test with covariance, unit conversion, and tolerance checks.
4. The model ends with a structured `submit_verdict` call that lists the evidence it used.
5. Every step is logged, so each verdict can be audited.

Method details: [docs/METHODS.md](docs/METHODS.md).

## Evaluation

Each claim has a verdict assigned before any model run, and a tag for the error it is designed to provoke. For both parent-of-origin benchmarks, every verdict is also reproduced by a deterministic implementation of the decision rules (`scripts/verify_gold.py`), which never calls the model. Two conditions are compared on the same claims:

- **`agent`:** the model uses the tools.
- **`no_tools`:** the model sees the raw records in its prompt and must reason without tools.

Reported metrics:

- accuracy with a 95% bootstrap CI
- recall for each verdict
- a confusion matrix
- accuracy by error type and by split (development vs held-out)
- tool calls and tokens per claim
- a paired comparison of the two conditions (exact McNemar test)

### Published benchmark (32 claims, rules fixed before the run, gpt-4.1-mini)

| | Correct | Accuracy (95% CI) | Asserted a claim the records do not establish |
| --- | --- | --- | --- |
| `agent` (tools) | 26 / 32 | 0.81 (0.69–0.94) | 4 |
| `no_tools` | 23 / 32 | 0.72 (0.56–0.88) | 9 |
| always "supported" | 15 / 32 | 0.47 | 17 |

The accuracy difference is not statistically detectable with 32 claims (paired exact McNemar p = 0.55). The kinds of error differ:

- **Without tools,** every error asserted something the records do not establish. Six verdicts contradicted the model's own explanation. Two p-values were misjudged against a threshold. In one case, evidence from a different variant was used.
- **With tools,** there were no threshold or evidence-substitution errors. The main weakness was retrieval: trait names written differently in the claim and in the records ("type 2 diabetes" vs "T2D", "IGF-1" vs "IGF1"). One verdict was correct for the wrong reason.

### Version 2 (26 new claims, pre-registered)

Run 2 showed two failure modes. Version 2 targets each one: rsID-first search, and asking for the explanation before the verdict.

| | system v1 | system v2 |
| --- | --- | --- |
| with tools | 20 / 26 | 22 / 26 |
| without tools | 19 / 26 | **24 / 26** |

- **Search fix:** searches returning no records fell from 17 to 1, and records that existed but were never opened fell from 3 to 0. Accuracy on the five trait-synonym claims did not change (4 of 5 in both).
- **Explanation first:** verdict–explanation mismatches fell from 3 to 0, and asserted errors from 7 to 2.
- **Significance:** neither accuracy difference is statistically significant with 26 claims (McNemar p = 0.63 and 0.13).
- **What remains:** threshold comparisons still fail without tools. Allele orientation and mechanism claims are the main open problems.

Details: [docs/RESULTS.md](docs/RESULTS.md).

### Development benchmark (synthetic records, gpt-4.1-mini)

| Domain | `agent` | `no_tools` |
| --- | --- | --- |
| Parent-of-origin (15 claims) | 14/15 (0.93; 95% CI 0.80–1.00) | 11/15 (0.73; 0.53–0.93) |
| Energy (8 claims) | 8/8 | 7/8 |

The tools corrected every baseline error that required a calculation: the difference test, the covariance-adjusted test, and the missing-value case. Without tools, the model's parent-of-origin errors all leaned towards `insufficient_evidence`. With 23 claims the paired difference is not statistically conclusive (exact McNemar p = 0.13). The agent's single error was traced to an ambiguous rule and fixed. That fix is now being checked on held-out claims.

Full results and error analysis: [docs/RESULTS.md](docs/RESULTS.md). Changes between runs: [docs/CHANGELOG.md](docs/CHANGELOG.md).

## Quick start

Requires Python 3.10 or newer and an OpenAI API key.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest                   # offline tests, no API key needed
cp .env.example .env               # add OPENAI_API_KEY and OPENAI_MODEL
```

```bash
# check one claim and print every tool call
python -m evidence_agent check --domain poe --trace "LOCUS_B has a maternal-specific effect on BMI."

# evaluate both conditions and compare them
python -m evidence_agent evaluate --domain poe --mode agent
python -m evidence_agent evaluate --domain poe --mode no_tools
python -m evidence_agent compare results/<agent_run> results/<no_tools_run>

# version 2 (rsID-first search, explanation-first verdict) on the v2 claims
python -m evidence_agent evaluate --domain poe_published_v2 --mode agent --system v2
```

Each run writes `summary.md` (metrics) and `runs.jsonl` (full traces) to `results/`.

## Repository layout

```
evidence_agent/
  agent.py      tool-calling loop
  tools.py      domain tools and the structured submit_verdict tool
  stats.py      Wald test, maternal–paternal difference test, value comparison
  prompts.py    system prompts for the two conditions
  llm.py        OpenAI client, and a scripted model for offline tests
  metrics.py    accuracy, bootstrap CI, confusion matrix, McNemar test
  domains.py    domain registry
data/<domain>/
  records.csv   source records
  rules.md      decision rules
  claims.csv    labelled claims: verdict, error type, split
scripts/
  build_poe_published.py   builds the published records from the extracted Table 1
  verify_gold.py           checks every gold verdict with a rule implementation
docs/           methods, results, changelog
tests/          offline tests (scripted model; no API calls)
```

## Limitations

- **Small benchmarks.** 32 published-data claims and 28 synthetic ones, so confidence intervals are wide. Rules and labels come from one author. The rule implementation checks consistency, not correctness, and independent labelling is planned.
- **Summary estimates only.** The published records are from a single table, with rounded estimates and no maternal–paternal covariance.
- **Rules are given, not learnt.** The benchmark tests whether the model applies the rules correctly, not whether it can derive them.
- **Zero covariance by default.** Without a stored covariance, the difference test assumes the maternal and paternal estimates are independent. That is not valid for estimates from the same trio model.
- **Model dependence.** Results depend on the model version, and runs at temperature 0 are not guaranteed to be identical.

## Data source

The published records come from Hofmeister RJ, et al. "Parent-of-origin effects on complex traits in up to 236,781 individuals". *Nature* (2025), [doi:10.1038/s41586-025-09357-5](https://doi.org/10.1038/s41586-025-09357-5), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Only numerical estimates from Table 1 are reused, rearranged into one row per variant and trait. See [data/README.md](data/README.md).

## Author

Roya Karimi, University of Bergen.

The author defined the research question, chose the data source (a publication she co-authored), ran all evaluations and signed off the final version. The decision rules, labelled claims, code and documentation were developed with AI assistance (Claude, ChatGPT Codex).

## License

MIT. See [LICENSE](LICENSE).
