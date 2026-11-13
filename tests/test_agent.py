"""Test the agent loop offline with a scripted model (no API key, no cost)."""

from argparse import Namespace

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
    out = run_agent("WELL-T1 is deep.", domain, llm)
    assert "error" in out["trace"][0]["result"]


def test_no_verdict_within_step_limit():
    domain = load_domain("poe")
    llm = ScriptedLLM([[("get_estimates", {"locus_id": "LOCUS_A"})]] * 3)
    out = run_agent("LOCUS_A ...", domain, llm, max_steps=3)
    assert out["verdict"] is None and "no verdict" in out["error"]


def test_evaluate_end_to_end_with_scripted_model(tmp_path, monkeypatch):
    # Script: answer 'supported' to every claim; the summary must still be produced.
    domain = load_domain("energy")
    n = sum(1 for _ in open(domain["claims_path"], encoding="utf-8")) - 1
    llm = ScriptedLLM([[("submit_verdict", {"verdict": "supported", "evidence_ids": [], "explanation": ""})]] * n)
    rows = cmd_evaluate(Namespace(domain="energy", mode="agent", limit=None, out_root=tmp_path), llm=llm)
    summaries = list(tmp_path.glob("*/summary.md"))
    assert len(summaries) == 1 and "Confusion matrix" in summaries[0].read_text(encoding="utf-8")
    assert len(rows) == n
    assert sum(r["verdict"] == r["gold"] for r in rows) == 3   # E01, E03, E07 are 'supported'


def test_published_records_use_reported_p_values():
    domain = load_domain("poe_published")
    tools = {t.name: t.function for t in domain["tools"]}
    r = tools["test_parental_difference"]("rs4264135_urate_level", alpha=5e-8)
    # rounded estimates suggest ~3e-8, the published value is 2.22e-7
    assert r["p_difference_computed_from_rounded_estimates"] < 5e-8
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
    assert module.main("poe_published_v2") == 0


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
    llm = ScriptedLLM([[("submit_verdict", {"explanation": "x", "evidence_ids": [], "verdict": "supported"})]] * n)
    rows = cmd_evaluate(Namespace(domain="poe_published_v2", mode="agent", system="v2", limit=None,
                                  split=None, out_root=tmp_path), llm=llm)
    assert rows[0]["system"] == "v2" and list(tmp_path.glob("*_v2_*/summary.md"))
