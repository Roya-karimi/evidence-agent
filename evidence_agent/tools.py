"""Tools the agent may call, per domain.

Each tool has
  - a JSON schema (what the language model sees and fills in), and
  - a Python function (what actually runs).

Design rule: tools take record IDs, not numbers copied by the model. The tool
looks the numbers up itself, so the model cannot mistype or invent an estimate.
The only numbers the model passes are values *stated in the claim*.
"""

import math
import re
from dataclasses import dataclass
from typing import Callable

from . import stats

VERDICTS = ["supported", "contradicted", "insufficient_evidence"]
UNIT_TO_M = {"m": 1.0, "ft": 0.3048}


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

    def problems(self, arguments) -> list:
        """Reasons the model's arguments do not fit this tool's schema (empty if they fit)."""
        return validate_arguments(arguments, self.parameters)


_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v),
    "array": lambda v: isinstance(v, list),
}


def validate_arguments(arguments, parameters: dict) -> list:
    """Check model-supplied arguments against a tool's JSON schema.

    The API does not guarantee that arguments follow the schema, so every call is
    checked before it runs: object shape, required and unknown fields, types
    (a string "false" is not a boolean), enumerated values and finite numbers.
    """
    if not isinstance(arguments, dict):
        return [f"arguments must be a JSON object, got {type(arguments).__name__}"]
    props = parameters.get("properties", {})
    problems = [f"missing required field '{k}'" for k in parameters.get("required", []) if k not in arguments]
    problems += [f"unknown field '{k}'" for k in arguments if k not in props]
    for key, value in arguments.items():
        spec = props.get(key)
        if spec is None:
            continue
        kind = spec.get("type")
        if kind in _TYPE_CHECKS and not _TYPE_CHECKS[kind](value):
            problems.append(f"'{key}' must be a {kind}, got {value!r}")
            continue
        if "enum" in spec and value not in spec["enum"]:
            problems.append(f"'{key}' must be one of {spec['enum']}, got {value!r}")
        if kind == "array" and spec.get("items", {}).get("type") == "string":
            if not all(isinstance(item, str) for item in value):
                problems.append(f"every item of '{key}' must be a string")
    return problems


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


def _single_parent_test(r: dict, parent: str, alpha: float) -> dict:
    """One parent's effect: the published p-value if the record has one, otherwise a Wald test."""
    wald = stats.wald_test(r[f"beta_{parent}"], r[f"se_{parent}"])
    reported = r.get(f"p_{parent}")
    if isinstance(reported, float):
        out = {"beta": wald["beta"], "se": wald["se"], "p": reported, "p_source": "reported",
               "p_recomputed_from_rounded_estimates": wald["p"]}
    else:
        out = {**wald, "p_source": "computed"}
    out["significant"] = out["p"] < alpha
    return out


def poe_tools(records: dict, system: str = "v1") -> list:
    """Tools for parent-of-origin claims. Records need beta/se for each parent.

    If a record holds published p-values (p_maternal, p_paternal, p_difference),
    significance decisions use them: published estimates are rounded, so p-values
    recomputed from them can differ substantially from the exact ones.

    Without a published difference p-value, the difference test needs the record's
    maternal-paternal covariance. If that is missing too, the test is reported as
    unavailable; a covariance is never assumed.
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
        alpha = stats.check_alpha(alpha)
        if locus_id not in records:
            return _not_found(locus_id, records)
        r = records[locus_id]
        needed = ["beta_maternal", "se_maternal", "beta_paternal", "se_paternal"]
        missing = [k for k in needed if r.get(k) is None]
        if missing:
            return {"found": True, "locus_id": locus_id, "error": f"Missing fields: {missing}"}

        bm, bp = r["beta_maternal"], r["beta_paternal"]
        out = {"found": True, "locus_id": locus_id, "trait": r.get("trait"),
               "effect_allele": r.get("effect_allele"), "alpha": alpha,
               "maternal": _single_parent_test(r, "maternal", alpha),
               "paternal": _single_parent_test(r, "paternal", alpha),
               "difference": bm - bp,
               "effect_signs": "opposite" if (bm > 0) != (bp > 0) else "same"}
        if out["effect_signs"] == "opposite":
            out["magnitude_note"] = ("The estimates have opposite signs. The difference test is about "
                                     "beta_maternal - beta_paternal; it does not test which effect is larger in magnitude.")

        reported, cov = r.get("p_difference"), r.get("cov_maternal_paternal")
        if isinstance(reported, float):
            # The published test is the decision. Its SE, z and CI are not returned: the source
            # gives rounded estimates and no covariance, so they cannot be reconstructed.
            out.update({"p_difference": reported, "p_difference_source": "reported",
                        "difference_significant": reported < alpha,
                        "se_difference": None, "ci_difference": None,
                        "uncertainty_note": "SE and CI of the difference are unavailable: the source reports "
                                            "the p-value of the difference but not the maternal-paternal covariance."})
            approx = stats.compare_parental_effects(bm, r["se_maternal"], bp, r["se_paternal"], cov=0.0, alpha=alpha)
            out["p_difference_recomputed_from_rounded_estimates_assuming_zero_covariance"] = approx["p_difference"]
            out["recomputed_note"] = "Recomputed values are for illustration only. Never use them for a verdict."
        elif cov is None:
            out.update({"p_difference": None, "p_difference_source": "unavailable",
                        "difference_significant": None,
                        "error": "Difference test unavailable: the record has no published p-value for the "
                                 "difference and no maternal-paternal covariance."})
        else:
            test = stats.compare_parental_effects(bm, r["se_maternal"], bp, r["se_paternal"], cov=cov, alpha=alpha)
            out.update({"p_difference": test["p_difference"], "p_difference_source": "computed",
                        "difference_significant": test["difference_significant"],
                        "se_difference": test["se_difference"], "z_difference": test["z_difference"],
                        "ci_difference": [test["ci_low"], test["ci_high"]],
                        "covariance_used": cov})
        return out

    def test_single_effect(locus_id: str, parent: str, alpha: float = 0.05):
        alpha = stats.check_alpha(alpha)
        if parent not in ("maternal", "paternal"):
            raise ValueError("parent must be 'maternal' or 'paternal'.")
        if locus_id not in records:
            return _not_found(locus_id, records)
        r = records[locus_id]
        if r.get(f"beta_{parent}") is None or r.get(f"se_{parent}") is None:
            return {"found": True, "locus_id": locus_id, "error": f"No {parent} estimate"}
        return {"found": True, "locus_id": locus_id, "parent": parent, "alpha": alpha,
                "effect_allele": r.get("effect_allele"), **_single_parent_test(r, parent, alpha)}

    locus = {"locus_id": {"type": "string", "description": "Locus ID exactly as in the data."}}
    return [
        Tool("find_records",
             "Search records by rsID, gene/locus name or trait words. All words must match. "
             "Use this to find the exact locus_id before testing.",
             {"type": "object",
              "properties": {"query": {"type": "string", "description": "e.g. 'rs10838787' or 'KLF14 hip'"}},
              "required": ["query"], "additionalProperties": False},
             find_records),
        Tool("get_estimates", "Look up the stored maternal and paternal estimates for a locus.",
             {"type": "object", "properties": locus, "required": ["locus_id"], "additionalProperties": False},
             get_estimates),
        Tool("test_parental_difference",
             "Test whether maternal and paternal effects differ (beta_maternal - beta_paternal). "
             "The result also contains the single-parent tests for both parents, so "
             "test_single_effect is not needed for the same locus.",
             {"type": "object",
              "properties": {**locus, "alpha": {"type": "number", "description": "Significance level, default 0.05."}},
              "required": ["locus_id"], "additionalProperties": False},
             test_parental_difference),
        Tool("test_single_effect", "Test whether one parent's effect differs from zero.",
             {"type": "object",
              "properties": {**locus,
                             "parent": {"type": "string", "enum": ["maternal", "paternal"]},
                             "alpha": {"type": "number", "description": "Significance level, default 0.05."}},
              "required": ["locus_id", "parent"], "additionalProperties": False},
             test_single_effect),
    ]


def energy_tools(records: dict) -> list:
    """Tools for factual claims about well records."""

    def get_record(record_id: str):
        if record_id not in records:
            return _not_found(record_id, records)
        return {"found": True, "record_id": record_id, **records[record_id]}

    def compare_field(record_id: str, field: str, claimed_value: str,
                      claimed_unit: str = "m", approximate: bool = False):
        if claimed_unit not in UNIT_TO_M:
            raise ValueError(f"Unsupported unit '{claimed_unit}'. Supported: {sorted(UNIT_TO_M)}.")
        if not isinstance(approximate, bool):
            raise ValueError("approximate must be true or false.")
        text = str(claimed_value).replace(",", "").replace(" ", "")
        if not re.fullmatch(r"-?\d+(\.\d+)?", text):
            raise ValueError(f"claimed_value must be a plain number as written in the claim, got {claimed_value!r}.")
        if record_id not in records:
            return _not_found(record_id, records)
        r = records[record_id]
        if field not in r:
            return {"found": True, "error": f"Unknown field '{field}'", "fields": sorted(r)}
        if r[field] is None:
            return {"found": True, "record_id": record_id, "field": field, "source": None,
                    "note": "Value missing in source."}
        if isinstance(r[field], str):
            return {"found": True, "error": f"Field '{field}' is not numeric", "fields": sorted(r)}
        to_m = UNIT_TO_M[claimed_unit]
        decimals = len(text.split(".")[1]) if "." in text else 0
        claimed_m = float(text) * to_m
        if approximate:
            tolerance, basis = 0.01 * abs(r[field]), "1% of the record value ('about')"
        else:       # half a unit of the last digit written in the claim, in the claim's own unit
            tolerance, basis = 0.5 * 10 ** (-decimals) * to_m, f"claim stated to {decimals} decimal place(s)"
        return {"found": True, "record_id": record_id, "field": field,
                "claimed_unit": claimed_unit, "claimed_in_m": round(claimed_m, 4), "tolerance_basis": basis,
                **stats.compare_value(claimed_m, r[field], tolerance)}

    rid = {"record_id": {"type": "string", "description": "Record ID exactly as in the data."}}
    return [
        Tool("get_record", "Look up a full source record by ID.",
             {"type": "object", "properties": rid, "required": ["record_id"], "additionalProperties": False},
             get_record),
        Tool("compare_field",
             "Compare a value stated in the claim with the record value. Handles feet-to-metre conversion, "
             "the precision stated in the claim, and the 1% tolerance for 'about' claims.",
             {"type": "object",
              "properties": {**rid,
                             "field": {"type": "string", "description": "Column name, e.g. vertical_depth_m."},
                             "claimed_value": {"type": "string",
                                               "description": "The number exactly as written in the claim, as text, "
                                                              "for example \"74\" or \"74.4\". Its decimals set the precision."},
                             "claimed_unit": {"type": "string", "enum": ["m", "ft"]},
                             "approximate": {"type": "boolean",
                                             "description": "True if the claim says 'about' or 'approximately'."}},
              "required": ["record_id", "field", "claimed_value"], "additionalProperties": False},
             compare_field),
    ]
