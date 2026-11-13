"""Tools the agent may call, per domain.

Each tool has
  - a JSON schema (what the language model sees and fills in), and
  - a Python function (what actually runs).

Design rule: tools take record IDs, not numbers copied by the model. The tool
looks the numbers up itself, so the model cannot mistype or invent an estimate.
The only numbers the model passes are values *stated in the claim*.
"""

import re
from dataclasses import dataclass
from typing import Callable

from . import stats

VERDICTS = ["supported", "contradicted", "insufficient_evidence"]
FEET_TO_M = 0.3048


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    function: Callable

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# The final answer is itself a tool call, so the verdict is always structured.
SUBMIT_VERDICT = Tool(
    name="submit_verdict",
    description="Submit the final verdict on the claim. Call exactly once, at the end.",
    parameters={
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": VERDICTS},
            "evidence_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "IDs of the records the verdict is based on (empty if none).",
            },
            "explanation": {
                "type": "string",
                "description": "Two or three sentences citing the numbers returned by the tools.",
            },
        },
        "required": ["verdict", "evidence_ids", "explanation"],
        "additionalProperties": False,
    },
    function=lambda **kwargs: kwargs,
)


# System v2: the explanation comes first, so the model writes its reasoning
# before it commits to a label (motivated by verdict/explanation mismatches in Run 2).
SUBMIT_VERDICT_V2 = Tool(
    name="submit_verdict",
    description="Submit the final verdict on the claim. Call exactly once, at the end. "
                "Write the explanation first; then choose the verdict that follows from it.",
    parameters={
        "type": "object",
        "properties": {
            "explanation": {
                "type": "string",
                "description": "Two or three sentences citing the numbers returned by the tools, "
                               "ending with the conclusion.",
            },
            "evidence_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "IDs of the records the verdict is based on (empty if none).",
            },
            "verdict": {"type": "string", "enum": VERDICTS},
        },
        "required": ["explanation", "evidence_ids", "verdict"],
        "additionalProperties": False,
    },
    function=lambda **kwargs: kwargs,
)


def submit_verdict_tool(system: str = "v1") -> Tool:
    return SUBMIT_VERDICT_V2 if system == "v2" else SUBMIT_VERDICT


def _normalise(text: str) -> str:
    """Lower case, '%' -> 'percentage', drop punctuation inside words (IGF-1 -> igf1)."""
    text = str(text).lower().replace("%", " percentage ")
    return " ".join(re.sub(r"[^a-z0-9]", "", w) for w in text.split())


def _not_found(record_id, records):
    return {"found": False, "record_id": record_id, "available_ids": sorted(records)}


def _use_reported_p(result: dict, reported, alpha: float, key: str = "p") -> dict:
    """Prefer the p-value printed in the source over one recomputed from rounded estimates."""
    if isinstance(reported, float):
        result[f"{key}_computed_from_rounded_estimates"] = result[key]
        result[key] = reported
        result[f"{key}_source"] = "reported"
    else:
        result[f"{key}_source"] = "computed"
    return result


def poe_tools(records: dict, system: str = "v1") -> list:
    """Tools for parent-of-origin claims. Records need beta/se for each parent.

    If a record also holds published p-values (p_maternal, p_paternal, p_difference),
    significance decisions use them: published estimates are rounded, so p-values
    recomputed from them can differ substantially from the exact ones.
    """

    def find_records(query: str):
        if system == "v2":
            return _find_records_v2(query)
        terms = [t for t in query.lower().replace(",", " ").split() if t]
        hits = []
        for rid, r in records.items():
            text = " ".join(str(v) for v in [rid, r.get("rsid"), r.get("locus"), r.get("trait")]).lower()
            if all(t in text for t in terms):
                hits.append({"locus_id": rid, "rsid": r.get("rsid"), "locus": r.get("locus"),
                             "trait": r.get("trait")})
        return {"query": query, "n_matches": len(hits), "matches": hits[:20]}

    def _find_records_v2(query: str):
        """rsIDs in the query take priority: every record for those variants is returned,
        whatever the other words, so trait spellings (T2D / type 2 diabetes) cannot hide a
        record. Without an rsID, all normalised words must match."""
        def hit(rid, r):
            return {"locus_id": rid, "rsid": r.get("rsid"), "locus": r.get("locus"), "trait": r.get("trait")}
        rsids = set(re.findall(r"rs\d+", query.lower()))
        if rsids:
            hits = [hit(rid, r) for rid, r in records.items() if str(r.get("rsid", "")).lower() in rsids]
            return {"query": query, "matched_by": "rsID (all traits for this variant; check the trait yourself)",
                    "n_matches": len(hits), "matches": hits[:20]}
        terms = _normalise(query).split()
        hits = []
        for rid, r in records.items():
            text = _normalise(" ".join(str(v) for v in [rid, r.get("rsid"), r.get("locus"), r.get("trait")]))
            if all(t in text for t in terms):
                hits.append(hit(rid, r))
        return {"query": query, "matched_by": "all words", "n_matches": len(hits), "matches": hits[:20]}

    def get_estimates(locus_id: str):
        if locus_id not in records:
            return _not_found(locus_id, records)
        return {"found": True, "locus_id": locus_id, **records[locus_id]}

    def test_parental_difference(locus_id: str, alpha: float = 0.05):
        if locus_id not in records:
            return _not_found(locus_id, records)
        r = records[locus_id]
        needed = ["beta_maternal", "se_maternal", "beta_paternal", "se_paternal"]
        missing = [k for k in needed if r.get(k) is None]
        if missing:
            return {"found": True, "locus_id": locus_id, "error": f"Missing fields: {missing}"}
        result = stats.compare_parental_effects(
            r["beta_maternal"], r["se_maternal"], r["beta_paternal"], r["se_paternal"],
            cov=r.get("cov_maternal_paternal") or 0.0, alpha=alpha,
        )
        _use_reported_p(result["maternal"], r.get("p_maternal"), alpha)
        _use_reported_p(result["paternal"], r.get("p_paternal"), alpha)
        _use_reported_p(result, r.get("p_difference"), alpha, key="p_difference")
        result["maternal"]["significant"] = result["maternal"]["p"] < alpha
        result["paternal"]["significant"] = result["paternal"]["p"] < alpha
        result["difference_significant"] = result["p_difference"] < alpha
        return {"found": True, "locus_id": locus_id, "trait": r.get("trait"),
                "effect_allele": r.get("effect_allele"), **result}

    def test_single_effect(locus_id: str, parent: str, alpha: float = 0.05):
        if locus_id not in records:
            return _not_found(locus_id, records)
        r = records[locus_id]
        beta, se = r.get(f"beta_{parent}"), r.get(f"se_{parent}")
        if beta is None or se is None:
            return {"found": True, "locus_id": locus_id, "error": f"No {parent} estimate"}
        result = _use_reported_p(stats.wald_test(beta, se), r.get(f"p_{parent}"), alpha)
        result["significant"] = result["p"] < alpha
        return {"found": True, "locus_id": locus_id, "parent": parent,
                "effect_allele": r.get("effect_allele"), **result}

    locus = {"locus_id": {"type": "string", "description": "Locus ID exactly as in the data."}}
    return [
        Tool("find_records",
             "Search records by rsID, gene/locus name or trait words. All words must match. "
             "Use this to find the exact locus_id before testing.",
             {"type": "object",
              "properties": {"query": {"type": "string", "description": "e.g. 'rs10838787' or 'KLF14 hip'"}},
              "required": ["query"]},
             find_records),
        Tool("get_estimates", "Look up the stored maternal and paternal estimates for a locus.",
             {"type": "object", "properties": locus, "required": ["locus_id"]}, get_estimates),
        Tool("test_parental_difference",
             "Test whether maternal and paternal effects differ (z-test of the difference). "
             "The result also contains the single-parent tests for both parents, so "
             "test_single_effect is not needed for the same locus.",
             {"type": "object",
              "properties": {**locus, "alpha": {"type": "number", "description": "Significance level, default 0.05."}},
              "required": ["locus_id"]},
             test_parental_difference),
        Tool("test_single_effect", "Test whether one parent's effect differs from zero.",
             {"type": "object",
              "properties": {**locus,
                             "parent": {"type": "string", "enum": ["maternal", "paternal"]},
                             "alpha": {"type": "number", "description": "Significance level, default 0.05."}},
              "required": ["locus_id", "parent"]},
             test_single_effect),
    ]


def energy_tools(records: dict) -> list:
    """Tools for factual claims about well records."""

    def get_record(record_id: str):
        if record_id not in records:
            return _not_found(record_id, records)
        return {"found": True, "record_id": record_id, **records[record_id]}

    def compare_field(record_id: str, field: str, claimed_value: float,
                      claimed_unit: str = "m", approximate: bool = False):
        if record_id not in records:
            return _not_found(record_id, records)
        r = records[record_id]
        if field not in r:
            return {"found": True, "error": f"Unknown field '{field}'", "fields": sorted(r)}
        if r[field] is None:
            return {"found": True, "record_id": record_id, "field": field, "source": None,
                    "note": "Value missing in source."}
        claimed_m = claimed_value * FEET_TO_M if claimed_unit == "ft" else claimed_value
        tolerance = 0.01 * abs(r[field]) if approximate else 0.5   # 0.5 m = rounding to whole metres
        return {"found": True, "record_id": record_id, "field": field,
                "claimed_unit": claimed_unit, "claimed_in_m": round(claimed_m, 2),
                **stats.compare_value(claimed_m, r[field], tolerance)}

    rid = {"record_id": {"type": "string", "description": "Record ID exactly as in the data."}}
    return [
        Tool("get_record", "Look up a full source record by ID.",
             {"type": "object", "properties": rid, "required": ["record_id"]}, get_record),
        Tool("compare_field",
             "Compare a value stated in the claim with the record value. Handles feet-to-metre "
             "conversion and the 1% tolerance for 'about' claims.",
             {"type": "object",
              "properties": {**rid,
                             "field": {"type": "string", "description": "Column name, e.g. vertical_depth_m."},
                             "claimed_value": {"type": "number", "description": "The number as written in the claim."},
                             "claimed_unit": {"type": "string", "enum": ["m", "ft"]},
                             "approximate": {"type": "boolean",
                                             "description": "True if the claim says 'about' or 'approximately'."}},
              "required": ["record_id", "field", "claimed_value"]},
             compare_field),
    ]
