from evidence_agent import metrics


def test_accuracy_and_ci_bounds():
    gold = ["supported"] * 8 + ["contradicted"] * 2
    pred = ["supported"] * 7 + ["contradicted"] * 3
    assert metrics.accuracy(gold, pred) == 0.9
    lo, hi = metrics.bootstrap_ci(gold, pred)
    assert 0.0 <= lo <= 0.9 <= hi <= 1.0


def test_mcnemar_exact():
    assert metrics.mcnemar_exact(0, 0) == 1.0
    assert abs(metrics.mcnemar_exact(4, 0) - 0.125) < 1e-12      # 2 * 0.5^4
    assert abs(metrics.mcnemar_exact(3, 0) - 0.25) < 1e-12
    assert metrics.mcnemar_exact(5, 5) == 1.0


def test_paired_comparison_counts_discordant_claims():
    run_1 = [{"claim_id": "a", "gold": "supported", "verdict": "supported"},
             {"claim_id": "b", "gold": "supported", "verdict": "supported"}]
    run_2 = [{"claim_id": "a", "gold": "supported", "verdict": "supported"},
             {"claim_id": "b", "gold": "supported", "verdict": "contradicted"}]
    text = metrics.paired_comparison(run_1, run_2, "agent", "no_tools")
    assert "Correct only with agent: 1 (b)" in text


def test_confusion_counts_missing_verdict():
    table = metrics.confusion(["supported", "contradicted"], ["supported", None])
    assert table["contradicted"][metrics.NO_VERDICT] == 1


def test_explanation_conclusion_reads_final_sentence():
    f = metrics.explanation_conclusion
    assert f("P = 0.27. Therefore, there is insufficient evidence to support the claim.") == "insufficient_evidence"
    assert f("The paternal effect is larger. Thus, the claim is contradicted.") == "contradicted"
    assert f("Both are significant. This supports the claim.") == "supported"
    assert f("The p-value is 7.53e-08, which is not supported at P < 5e-8.") == "insufficient_evidence"


def test_mismatch_flag():
    rows = [{"claim_id": "a", "verdict": "supported", "explanation": "x. So the claim is contradicted."},
            {"claim_id": "b", "verdict": "contradicted", "explanation": "x. So the claim is contradicted."}]
    assert metrics.verdict_explanation_mismatches(rows) == ["a"]


def _row(cid, verdict="supported", gold="supported", claim="c"):
    return {"claim_id": cid, "gold": gold, "verdict": verdict, "claim": claim}


def test_paired_comparison_refuses_incompatible_runs():
    """Review finding 8."""
    import pytest
    a = [_row("a"), _row("b")]
    with pytest.raises(ValueError, match="Duplicate"):
        metrics.paired_comparison(a + [_row("a")], a, "1", "2")
    with pytest.raises(ValueError, match="different claims"):
        metrics.paired_comparison(a, [_row("a")], "1", "2")
    with pytest.raises(ValueError, match="'claim'"):
        metrics.paired_comparison(a, [_row("a"), _row("b", claim="the opposite claim")], "1", "2")
    with pytest.raises(ValueError, match="'gold'"):
        metrics.paired_comparison(a, [_row("a"), _row("b", gold="contradicted")], "1", "2")
    text = metrics.paired_comparison(a, [_row("a")], "1", "2", allow_subset=True)
    assert "Claims compared: 1" in text and "left out: b" in text


def test_cluster_bootstrap_resamples_whole_clusters():
    gold = ["supported"] * 6
    pred = ["supported"] * 3 + ["contradicted"] * 3
    # two clusters, one all right and one all wrong: resampled accuracy can only be 0, 0.5 or 1
    lo, hi = metrics.bootstrap_ci(gold, pred, clusters=["x"] * 3 + ["y"] * 3)
    assert (lo, hi) == (0.0, 1.0)
    lo_claims, hi_claims = metrics.bootstrap_ci(gold, pred)
    assert 0.0 < lo_claims and hi_claims < 1.0
