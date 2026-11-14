"""System prompts for the two conditions we compare.

agent    : the model may call tools that look up records and compute statistics.
no_tools : the model sees the raw records in the prompt and must judge alone.
           This is the baseline that tells us what the tools add.
"""

import json

BASE = """You check whether a claim is supported by a fixed set of source records.

Return exactly one verdict:
- supported: the records show the claim is true, under the decision rules.
- contradicted: the records show the claim is false, under the decision rules.
- insufficient_evidence: the records cannot establish whether the claim is true
  (missing record, missing value, non-significant result, or a question the
  records do not address).

"Wrong" and "unknown" are different. Never fill a gap with a plausible number.
Base every statement on the records, not on your background knowledge.
Finish by calling submit_verdict exactly once.

Decision rules for this domain:
{rules}
"""

AGENT_EXTRA = """
Use the tools to look up records and to compute every statistic you rely on.
Do not do arithmetic yourself. If a record is not found, do not guess.
Look the records up before you submit a verdict, and cite only record IDs that
the tools returned. A verdict submitted without a lookup is rejected.
"""

NO_TOOLS_EXTRA = """
You have no calculation tools. Here are all source records as JSON:
{records}
"""


V2_EXTRA = """
In submit_verdict, write the explanation first and end it with your conclusion;
then choose the verdict that matches that conclusion.
"""


def system_prompt(domain: dict, mode: str) -> str:
    text = BASE.format(rules=domain["rules"])
    if domain.get("system") == "v2":
        text += V2_EXTRA
    if mode == "agent":
        return text + AGENT_EXTRA
    if mode == "no_tools":
        return text + NO_TOOLS_EXTRA.format(records=json.dumps(domain["records"], indent=1))
    raise ValueError(f"Unknown mode '{mode}'")
