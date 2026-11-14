"""Test the agent loop offline with a scripted model (no API key, no cost)."""

import json
from argparse import Namespace

import pytest

from evidence_agent.__main__ import cmd_evaluate
from evidence_agent.agent import run_agent
from evidence_agent.domains import load_domain
from evidence_agent.llm import ScriptedLLM


def test_loop_runs_tool_then_returns_verdict():
    domain = load_domain("poe")
    llm = ScriptedLLM([
        [("test_parental_difference", {"locus_id": "LOCUS_B"})],
        [("submit_verdict", {"verdict": "insufficient_evidence", "evidence_ids": ["LOCUS_B"],
                             "explanation": "Difference p = 0.27."})],
    ])
    out = run_agent("LOCUS_B has a maternal-specific effect on BMI.", domain, llm)
    assert out["verdict"] == "insufficient_evidence"
    assert out["tool_calls"] == 2
    first = out["trace"][0]
    assert first["tool"] == "test_parental_difference"
    assert first["result"]["difference_significant"] is False


def test_unknown_locus_is_reported_not_invented():
    domain = load_domain("poe")
    llm = ScriptedLLM([
        [("get_estimates", {"locus_id": "LOCUS_Z"})],
        [("submit_verdict", {"verdict": "insufficient_evidence", "evidence_ids": [], "explanation": "Not found."})],
    ])
    out = run_agent("LOCUS_Z has a maternal effect.", domain, llm)
    assert out["trace"][0]["result"]["found"] is False


def test_bad_arguments_are_returned_to_model_as_error():
    domain = load_domain("energy")
    llm = ScriptedLLM([
        [("compare_field", {"record_id": "WELL-T1"})],          # missing required args
        [("submit_verdict", {"verdict": "insufficient_evidence", "evidence_ids": [], "explanation": "x"})],
    ])
    out = run_agent("WELL-T1 is deep.", domain, llm, max_steps=2)
    assert "missing required field 'field'" in out["trace"][0]["result"]["error"]
    # a call that never ran is not an evidence check, so the verdict is refused as well
    assert out["status"] == "no_valid_verdict"


def test_no_verdict_within_step_limit():
    domain = load_domain("poe")
    llm = ScriptedLLM([[("get_estimates", {"locus_id": "LOCUS_A"})]] * 3)
    out = run_agent("LOCUS_A ...", domain, llm, max_steps=3)
    assert out["verdict"] is None and out["status"] == "no_valid_verdict"


def _lookup_then(verdict, record="WELL-T1", ids=("WELL-T1",)):
    """Two scripted turns: open one record, then submit."""
    return [[("get_record", {"record_id": record})],
            [("submit_verdict", {"verdict": verdict, "evidence_ids": list(ids), "explanation": "From the record."})]]


def test_evaluate_end_to_end_with_scripted_model(tmp_path):
    # Script: look up WELL-T1, then answer 'supported', for every claim.
    domain = load_domain("energy")
    n = sum(1 for _ in open(domain["claims_path"], encoding="utf-8")) - 1
    llm = ScriptedLLM(_lookup_then("supported") * n)
    rows = cmd_evaluate(Namespace(domain="energy", mode="agent", limit=None, out_root=tmp_path), llm=llm)
    summaries = list(tmp_path.glob("*/summary.md"))
    assert len(summaries) == 1 and "Confusion matrix" in summaries[0].read_text(encoding="utf-8")
    assert len(rows) == n
    assert sum(r["verdict"] == r["gold"] for r in rows) == 3   # E01, E03, E07 are 'supported'
    manifest = json.loads(next(tmp_path.glob("*/manifest.json")).read_text(encoding="utf-8"))
    assert manifest["status"] == "complete" and manifest["claims_with_verdict"] == n
    assert set(manifest["sha256"]) == {"rules", "claims", "records", "code"}


# --- Regression tests for the review of 13 November 2026 ----------------------------

def test_verdict_without_evidence_lookup_is_rejected():
    """Review finding 2: an immediate verdict citing an invented source was accepted."""
    domain = load_domain("poe_published")
    llm = ScriptedLLM([[("submit_verdict", {"verdict": "supported", "evidence_ids": ["MADE_UP"], "explanation": ""})]])
    out = run_agent("x", domain, llm, max_steps=1)
    assert out["verdict"] is None and out["status"] == "no_valid_verdict"
    rejected = " ".join(out["trace"][0]["rejected"])
    assert "explanation is empty" in rejected and "no evidence tool" in rejected and "MADE_UP" in rejected


def test_rejected_verdict_can_be_corrected():
    domain = load_domain("poe_published")
    good = {"verdict": "supported", "evidence_ids": ["rs576603_standing_height"], "explanation": "Published P = 3.86e-08."}
    llm = ScriptedLLM([
        [("submit_verdict", good)],                                                      # too early: nothing looked up
        [("test_parental_difference", {"locus_id": "rs576603_standing_height"})],
        [("submit_verdict", {**good, "evidence_ids": ["rs576603_standing_height", "rs1_invented"]})],   # invented ID
        [("submit_verdict", good)],
    ])
    out = run_agent("rs576603 shows a parent-of-origin effect on standing height.", domain, llm)
    assert out["status"] == "ok" and out["verdict"] == "supported" and out["steps"] == 4
    assert [bool(t.get("rejected")) for t in out["trace"]] == [True, False, True, False]


def test_asserting_verdict_must_cite_a_retrieved_record():
    domain = load_domain("poe_published")
    llm = ScriptedLLM([
        [("find_records", {"query": "rs576603"})],        # found by search, estimates never retrieved
        [("submit_verdict", {"verdict": "contradicted", "evidence_ids": ["rs576603_standing_height"], "explanation": "x"})],
    ])
    out = run_agent("x", domain, llm, max_steps=2)
    assert out["status"] == "no_valid_verdict"
    assert "whose estimates were retrieved" in out["trace"][-1]["rejected"][0]


def test_verdict_in_the_same_turn_as_a_lookup_is_rejected():
    domain = load_domain("poe_published")
    llm = ScriptedLLM([[("get_estimates", {"locus_id": "rs576603_standing_height"}),
                        ("submit_verdict", {"verdict": "supported", "evidence_ids": ["rs576603_standing_height"],
                                            "explanation": "x"})]])
    out = run_agent("x", domain, llm, max_steps=1)
    assert out["status"] == "no_valid_verdict"


def test_no_tools_verdict_must_cite_existing_records():
    domain = load_domain("poe_published")
    llm = ScriptedLLM([[("submit_verdict", {"verdict": "supported", "evidence_ids": ["MADE_UP"], "explanation": "x"})],
                       [("submit_verdict", {"verdict": "supported", "evidence_ids": ["rs576603_standing_height"],
                                            "explanation": "x"})]])
    out = run_agent("x", domain, llm, mode="no_tools")
    assert out["status"] == "ok" and out["steps"] == 2 and out["trace"][0]["rejected"]


@pytest.mark.parametrize("arguments, problem", [
    ([], "must be a JSON object"),                                                      # review finding 3
    ({"verdict": "maybe", "evidence_ids": [], "explanation": "x"}, "must be one of"),
    ({"verdict": "supported", "evidence_ids": "WELL-T1", "explanation": "x"}, "must be a array"),
    ({"verdict": "supported", "evidence_ids": [], "explanation": "x", "extra": 1}, "unknown field"),
])
def test_malformed_verdicts_do_not_crash(arguments, problem):
    out = run_agent("x", load_domain("energy"), ScriptedLLM([[("submit_verdict", arguments)]]), max_steps=1)
    assert out["status"] == "no_valid_verdict" and problem in " ".join(out["trace"][0]["rejected"])


def test_energy_tool_rejects_unsupported_units_and_non_boolean_flags():
    """Review finding 3: 74 km was read as 74 m, and the string "false" switched on the 1% tolerance."""
    tool = {t.name: t for t in load_domain("energy")["tools"]}["compare_field"]
    base = {"record_id": "WELL-T1", "field": "water_depth_m", "claimed_value": "74"}
    assert "claimed_unit" in tool.problems({**base, "claimed_unit": "km"})[0]
    assert "approximate" in tool.problems({**base, "approximate": "false"})[0]
    assert "claimed_value" in tool.problems({**base, "claimed_value": 74})[0]            # must be text
    with pytest.raises(ValueError):
        tool.function("WELL-T1", "water_depth_m", "74", claimed_unit="km")
    with pytest.raises(ValueError):
        tool.function("WELL-T1", "water_depth_m", "seventy-four")


def test_exact_values_are_compared_at_the_precision_of_the_claim():
    compare = {t.name: t.function for t in load_domain("energy")["tools"]}["compare_field"]
    assert compare("WELL-T1", "water_depth_m", "74")["matches"] is True
    assert compare("WELL-T1", "water_depth_m", "74.4")["matches"] is False             # was accepted: fixed 0.5 m
    assert compare("WELL-T1", "water_depth_m", "74.0")["matches"] is True
    assert compare("WELL-T1", "water_depth_m", "74", claimed_unit="ft")["matches"] is False
    assert compare("WELL-T2", "measured_depth_m", "3570", approximate=True)["matches"] is True


def test_missing_covariance_is_not_replaced_by_zero():
    """Review finding 4."""
    from evidence_agent.tools import poe_tools
    record = {"trait": "x", "beta_maternal": 0.040, "se_maternal": 0.016, "beta_paternal": 0.015, "se_paternal": 0.016}
    test = {t.name: t.function for t in poe_tools({"L": dict(record)})}["test_parental_difference"]
    out = test("L")
    assert out["p_difference"] is None and out["difference_significant"] is None and "unavailable" in out["error"]
    with_cov = {t.name: t.function for t in poe_tools({"L": {**record, "cov_maternal_paternal": 0.0002}})}
    assert with_cov["test_parental_difference"]("L")["p_difference"] == pytest.approx(0.01816, abs=1e-4)


def test_reported_p_is_not_mixed_with_a_recomputed_interval():
    """Review finding 5: 'not significant' was returned next to a CI that excluded zero."""
    tools = {t.name: t.function for t in load_domain("poe_published")["tools"]}
    r = tools["test_parental_difference"]("rs4264135_urate_level", alpha=5e-8)
    assert r["p_difference"] == 2.22e-07 and r["difference_significant"] is False
    assert r["se_difference"] is None and r["ci_difference"] is None
    assert "z_difference" not in r and "ci_low" not in r


def test_tools_reject_impossible_alpha():
    tools = {t.name: t.function for t in load_domain("poe_published")["tools"]}
    with pytest.raises(ValueError):
        tools["test_parental_difference"]("rs4264135_urate_level", alpha=1.5)


def test_api_failure_is_recorded_and_the_batch_continues(tmp_path):
    """Review finding 7: a failed model call left no row and no summary."""
    domain = load_domain("energy")
    n = sum(1 for _ in open(domain["claims_path"], encoding="utf-8")) - 1
    turns = _lookup_then("supported") + [RuntimeError("connection lost")] + _lookup_then("supported") * (n - 2)
    rows = cmd_evaluate(Namespace(domain="energy", mode="agent", limit=None, out_root=tmp_path), llm=ScriptedLLM(turns))
    assert len(rows) == n
    assert rows[1]["status"] == "operational_error" and rows[1]["verdict"] is None and "connection lost" in rows[1]["error"]
    assert rows[2]["status"] == "ok"
    manifest = json.loads(next(tmp_path.glob("*/manifest.json")).read_text(encoding="utf-8"))
    assert manifest["status"] == "incomplete" and manifest["claims_failed_operationally"] == 1
    assert "INCOMPLETE RUN" in next(tmp_path.glob("*/summary.md")).read_text(encoding="utf-8")


def test_batch_stops_after_repeated_api_failures(tmp_path):
    rows = cmd_evaluate(Namespace(domain="energy", mode="agent", limit=None, out_root=tmp_path),
                        llm=ScriptedLLM([RuntimeError("no network")] * 20))
    manifest = json.loads(next(tmp_path.glob("*/manifest.json")).read_text(encoding="utf-8"))
    assert len(rows) == 3 and len(manifest["claims_not_attempted"]) == 5 and manifest["status"] == "incomplete"


def test_published_records_use_reported_p_values():
    domain = load_domain("poe_published")
    tools = {t.name: t.function for t in domain["tools"]}
    r = tools["test_parental_difference"]("rs4264135_urate_level", alpha=5e-8)
    # rounded estimates suggest ~3e-8, the published value is 2.22e-7
    assert r["p_difference_recomputed_from_rounded_estimates_assuming_zero_covariance"] < 5e-8
    assert r["p_difference"] == 2.22e-07 and r["p_difference_source"] == "reported"
    assert r["difference_significant"] is False


def test_find_records_matches_all_terms():
    domain = load_domain("poe_published")
    tools = {t.name: t.function for t in domain["tools"]}
    hits = tools["find_records"]("KLF14 hip")["matches"]
    assert {h["locus_id"] for h in hits} == {"rs6467315_hip_circumference", "rs3847104_hip_circumference"}


def test_gold_verdicts_match_rule_implementation():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent / "scripts" / "verify_gold.py"
    spec = importlib.util.spec_from_file_location("verify_gold", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main("poe_published") == 0
    assert module.main("poe") == 0
    assert module.main("poe_published_v2") == 0        # V05 is reported as superseded, not as a mismatch
    assert module.main("poe_published_v2_1") == 0


def test_magnitude_claim_with_opposite_signs_is_insufficient_evidence():
    """Review finding 1: a signed-difference p-value was used to support a magnitude claim."""
    import csv
    domain = load_domain("poe_published_v2_1")
    tools = {t.name: t.function for t in domain["tools"]}
    r = tools["test_parental_difference"]("rs12528876_igf1_level")
    assert r["effect_signs"] == "opposite" and r["difference_significant"] is True and "magnitude_note" in r
    with open(domain["claims_path"], newline="", encoding="utf-8") as f:
        v05 = next(c for c in csv.DictReader(f) if c["claim_id"] == "V05")
    assert v05["gold_verdict"] == "insufficient_evidence"
    same = tools["test_parental_difference"]("rs7705526_telomere_length_ts_ratio")        # V06: same sign
    assert same["effect_signs"] == "same" and "magnitude_note" not in same


def test_run2_parent_specific_labels_do_not_rest_on_opposite_sign_magnitudes():
    """R08, R29 and R31 involve opposite-sign estimates. Their labels must also follow from the
    version 2.1 rule, which uses significance only and no magnitude comparison."""
    import csv
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent / "scripts" / "verify_gold.py"
    spec = importlib.util.spec_from_file_location("verify_gold", path)
    vg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vg)
    domain = load_domain("poe_published")
    tools = {t.name: t.function for t in domain["tools"]}
    with open(domain["claims_path"], newline="", encoding="utf-8") as f:
        claims = {c["claim_id"]: c for c in csv.DictReader(f)}
    for cid in ("R08", "R29", "R31"):
        strict = {**claims[cid], "claim_type": claims[cid]["claim_type"] + "2"}
        assert vg.verdict(strict, tools, domain["records"]) == claims[cid]["gold_verdict"], cid


def test_v2_search_returns_all_records_for_an_rsid():
    tools = {t.name: t.function for t in load_domain("poe_published_v2", "v2")["tools"]}
    hits = tools["find_records"]("rs10838787 type 2 diabetes")["matches"]
    assert {h["locus_id"] for h in hits} == {"rs10838787_t2d", "rs10838787_hba1c_level"}
    v1 = {t.name: t.function for t in load_domain("poe_published_v2", "v1")["tools"]}
    assert v1["find_records"]("rs10838787 type 2 diabetes")["n_matches"] == 0   # the Run 2 failure


def test_v2_search_normalises_spelling():
    tools = {t.name: t.function for t in load_domain("poe_published_v2", "v2")["tools"]}
    assert {h["locus_id"] for h in tools["find_records"]("IGF-1 PLAGL1")["matches"]} == {"rs12528876_igf1_level"}
    assert {h["locus_id"] for h in tools["find_records"]("GNAS trunk fat percentage")["matches"]} == {"rs6026426_trunk_fat"}


def test_v2_verdict_tool_asks_for_explanation_first():
    from evidence_agent.tools import submit_verdict_tool
    v1 = list(submit_verdict_tool("v1").parameters["properties"])
    v2 = list(submit_verdict_tool("v2").parameters["properties"])
    assert v1[0] == "verdict" and v2[0] == "explanation" and v2[-1] == "verdict"


def test_evaluate_runs_with_system_v2(tmp_path):
    domain = load_domain("poe_published_v2", "v2")
    n = sum(1 for _ in open(domain["claims_path"], encoding="utf-8")) - 1
    llm = ScriptedLLM([[("get_estimates", {"locus_id": "rs576603_standing_height"})],
                       [("submit_verdict", {"explanation": "x", "evidence_ids": ["rs576603_standing_height"],
                                            "verdict": "supported"})]] * n)
    rows = cmd_evaluate(Namespace(domain="poe_published_v2", mode="agent", system="v2", limit=None,
                                  split=None, out_root=tmp_path), llm=llm)
    assert rows[0]["system"] == "v2" and list(tmp_path.glob("*_v2_*/summary.md"))


def test_openai_client_sets_limits_and_records_the_returned_model(monkeypatch):
    pytest.importorskip("openai")
    from types import SimpleNamespace
    from evidence_agent.llm import OpenAIChat
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    llm = OpenAIChat(model="some-model")
    sent = {}

    def fake_create(**kwargs):
        sent.update(kwargs)
        call = SimpleNamespace(id="call_1", function=SimpleNamespace(name="submit_verdict", arguments="[1, 2]"))
        message = SimpleNamespace(content=None, tool_calls=[call])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None,
                               model="some-model-2026-01-01", id="chatcmpl-1")

    monkeypatch.setattr(llm.client.chat.completions, "create", fake_create)
    resp = llm.chat([{"role": "user", "content": "x"}], [])
    assert sent["max_completion_tokens"] == 1000 and sent["tool_choice"] == "required" and sent["temperature"] == 0.0
    assert llm.client.timeout == 60.0 and llm.client.max_retries == 2
    assert resp.model == "some-model-2026-01-01" and resp.response_id == "chatcmpl-1"
    assert resp.tool_calls[0].arguments == [1, 2]          # passed on as-is; the agent loop rejects it


# Sample arguments that every tool must handle through the full agent loop.
_TOOL_CALLS = {
    "poe_published_v2_1": [("find_records", {"query": "rs576603"}),
                           ("get_estimates", {"locus_id": "rs576603_standing_height"}),
                           ("test_parental_difference", {"locus_id": "rs576603_standing_height", "alpha": 5e-8}),
                           ("test_single_effect", {"locus_id": "rs576603_standing_height", "parent": "paternal"})],
    "poe": [("find_records", {"query": "LOCUS_F"}), ("get_estimates", {"locus_id": "LOCUS_G"}),
            ("test_parental_difference", {"locus_id": "LOCUS_F"}), ("test_parental_difference", {"locus_id": "LOCUS_G"}),
            ("test_single_effect", {"locus_id": "LOCUS_A", "parent": "maternal"})],
    "energy": [("get_record", {"record_id": "WELL-T1"}), ("get_record", {"record_id": "WELL-T9"}),
               ("compare_field", {"record_id": "WELL-T1", "field": "water_depth_m", "claimed_value": "74"}),
               ("compare_field", {"record_id": "WELL-T1", "field": "water_depth_m", "claimed_value": "74", "claimed_unit": "ft"}),
               ("compare_field", {"record_id": "WELL-T2", "field": "measured_depth_m", "claimed_value": "3570", "approximate": True}),
               ("compare_field", {"record_id": "WELL-T2", "field": "vertical_depth_m", "claimed_value": "3574"})],
}


@pytest.mark.parametrize("domain_name, tool, arguments",
                         [(d, name, args) for d, calls in _TOOL_CALLS.items() for name, args in calls])
def test_every_tool_result_passes_through_the_agent_loop(domain_name, tool, arguments):
    """Found by a live smoke test on 14 November 2026: compare_field returns a true/false
    field called "matches", and the loop read it as the list of search matches. The tool's
    result was replaced by a TypeError. The offline tests had only called the tool directly."""
    domain = load_domain(domain_name, "v2" if domain_name.startswith("poe_published") else "v1")
    submit = {"verdict": "insufficient_evidence", "evidence_ids": [], "explanation": "x"}
    out = run_agent("x", domain, ScriptedLLM([[(tool, arguments)], [("submit_verdict", submit)]]))
    direct = {t.name: t.function for t in domain["tools"]}[tool](**arguments)
    assert out["trace"][0]["result"] == direct          # the model sees exactly what the tool returned
    assert out["status"] == "ok"


def test_all_tools_are_covered_by_the_loop_test():
    for domain_name, calls in _TOOL_CALLS.items():
        assert {t.name for t in load_domain(domain_name)["tools"]} == {name for name, _ in calls}


def test_energy_claim_runs_end_to_end_through_compare_field():
    domain = load_domain("energy")
    llm = ScriptedLLM([
        [("compare_field", {"record_id": "WELL-T1", "field": "water_depth_m", "claimed_value": "74", "claimed_unit": "ft"})],
        [("submit_verdict", {"verdict": "contradicted", "evidence_ids": ["WELL-T1"], "explanation": "74 ft is 22.56 m."})],
    ])
    out = run_agent("The water depth at WELL-T1 is 74 feet.", domain, llm)
    assert out["status"] == "ok" and out["verdict"] == "contradicted"
    assert out["trace"][0]["result"]["matches"] is False and out["trace"][0]["result"]["claimed_in_m"] == 22.5552


# --- Review workflow ----------------------------------------------------------------

def _review_turns():
    urate, height = "rs4264135_urate_level", "rs576603_standing_height"
    return [
        [("find_records", {"query": "rs4264135"})],
        [("test_parental_difference", {"locus_id": urate, "alpha": 5e-8})],
        [("submit_verdict", {"explanation": "Published P = 2.22e-07 | above 5e-8.", "evidence_ids": [urate],
                             "check_type": "significance", "verdict": "insufficient_evidence"})],
        [("get_estimates", {"locus_id": height})],
        [("submit_verdict", {"explanation": "Stored value is -0.027.", "evidence_ids": [height],
                             "check_type": "quoted_number", "verdict": "supported"})],
        [("find_records", {"query": "rs999"})],
        [("submit_verdict", {"explanation": "No record.", "evidence_ids": [],
                             "check_type": "parental_difference", "verdict": "insufficient_evidence"})],
        RuntimeError("connection lost"),
    ]


def test_review_command_writes_a_readable_table(tmp_path):
    from evidence_agent.__main__ import cmd_review
    from evidence_agent.domains import DATA
    statements = tmp_path / "statements.txt"
    statements.write_text("# draft sentences\n\nUrate is genome-wide significant.\nThe paternal estimate is -0.027.\n"
                          "rs999 has an effect.\nA fourth sentence.\n", encoding="utf-8")
    rows = cmd_review(Namespace(statements=str(statements), records=str(DATA / "poe_published" / "records.csv"),
                                out=str(tmp_path / "out")), llm=ScriptedLLM(_review_turns()))
    assert [r["finding"] for r in rows] == ["Insufficient evidence", "Supported", "Insufficient evidence", "Not checked"]
    assert rows[0]["action"].startswith("Check the significance wording")
    assert "difference P 2.22e-07" in rows[0]["source"] and "effect allele G" in rows[0]["source"]   # read from the table
    assert rows[1]["action"] == "No change needed." and "paternal -0.027 (SE 0.004, P 8.53e-11)" in rows[1]["source"]
    assert rows[2]["action"].startswith("No matching row") and rows[2]["source"] == "No source row used."
    assert rows[3]["action"].startswith("The checker did not reach a verdict")
    table = (tmp_path / "out" / "review.md").read_text(encoding="utf-8")
    assert "4 statement(s) checked, 3 flagged" in table and "2.22e-07 \\| above" in table      # '|' escaped
    assert len(table.splitlines()[5].split(" | ")) == 6
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "incomplete" and manifest["statements_without_verdict"] == 1
    assert (tmp_path / "out" / "review.csv").exists() and (tmp_path / "out" / "traces.jsonl").exists()


def test_review_requires_the_kind_of_check():
    from evidence_agent.review import load_review_domain
    from evidence_agent.domains import DATA
    domain = load_review_domain(DATA / "poe_published" / "records.csv")
    v2_style = {"explanation": "x", "evidence_ids": ["rs576603_standing_height"], "verdict": "supported"}
    llm = ScriptedLLM([[("get_estimates", {"locus_id": "rs576603_standing_height"})], [("submit_verdict", v2_style)]])
    out = run_agent("x", domain, llm, max_steps=2)
    assert out["status"] == "no_valid_verdict" and "check_type" in out["trace"][-1]["rejected"][0]
    assert "Hofmeister" not in domain["rules"] and "Type H" in domain["rules"] and "Type S" in domain["rules"]
    assert "Never supported" in domain["rules"]


def test_review_refuses_a_table_without_the_needed_columns(tmp_path):
    from evidence_agent.review import load_review_domain
    bad = tmp_path / "table.csv"
    bad.write_text("locus_id,trait,beta_maternal\nx,y,0.1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="se_maternal"):
        load_review_domain(bad)


def test_every_verdict_and_check_type_has_an_action():
    from evidence_agent.review import action_for
    from evidence_agent.tools import CHECK_TYPES, VERDICTS
    records = {"r1": {}}
    for verdict in VERDICTS:
        for kind in CHECK_TYPES:
            result = {"status": "ok", "verdict": verdict, "check_type": kind, "evidence_ids": ["r1"]}
            assert action_for(result, records).endswith(".")
    mechanism = {"status": "ok", "verdict": "insufficient_evidence", "check_type": "interpretation", "evidence_ids": []}
    assert "human review" in action_for(mechanism, records)


def test_pilot_labels_follow_the_review_rules_and_scoring_counts_correctly(tmp_path, capsys):
    import csv
    import importlib.util
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent

    def load(name):
        spec = importlib.util.spec_from_file_location(name, root / "scripts" / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    assert load("verify_gold").main("poe_published", root / "pilot" / "expected.csv") == 0
    with open(root / "pilot" / "expected.csv", newline="", encoding="utf-8") as f:
        expected = list(csv.DictReader(f))
    statements = (root / "pilot" / "statements.txt").read_text(encoding="utf-8").splitlines()
    assert statements == [e["claim"] for e in expected]

    # A made-up review: everything right, except S01 missed and S02 flagged with another variant's row.
    review = tmp_path / "review.csv"
    with open(review, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["number", "statement", "verdict", "check_type", "explanation", "evidence_ids", "source", "action",
                    "status", "seconds"])
        for i, e in enumerate(expected, 1):
            verdict, ids = e["gold_verdict"], e["record_ids"]
            if e["claim_id"] == "S01":
                verdict = "supported"
            if e["claim_id"] == "S02":
                verdict, ids = "contradicted", "rs576603_standing_height"
            w.writerow([i, e["claim"], verdict, "", "", ids, "", "", "ok", 2.0])
    old_argv, sys.argv = sys.argv, ["score_pilot.py", str(review)]
    try:
        assert load("score_pilot").main() == 0
    finally:
        sys.argv = old_argv
    out = capsys.readouterr().out
    assert "| Problems caught | 8 / 9 |" in out and "| Problems missed | 1 / 9 |" in out
    assert "| False alarms | 1 / 5 |" in out and "| Same finding as expected | 12 / 14 |" in out
    assert "| Source row right | 13 / 14 |" in out and "| Time in model calls | 28 s |" in out
