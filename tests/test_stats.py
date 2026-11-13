import math

import pytest

from evidence_agent import stats


def test_difference_test_known_values():
    r = stats.compare_parental_effects(0.10, 0.02, 0.0, 0.02)
    assert r["difference"] == pytest.approx(0.10)
    assert r["se_difference"] == pytest.approx(math.sqrt(0.02**2 * 2))
    assert r["z_difference"] == pytest.approx(3.5355, abs=1e-3)
    assert r["p_difference"] == pytest.approx(0.000407, abs=1e-5)
    assert r["difference_significant"]


def test_one_side_significant_is_not_a_difference():
    # maternal p ~ 0.012, paternal p ~ 0.35, yet the difference is not significant
    r = stats.compare_parental_effects(0.040, 0.016, 0.015, 0.016)
    assert r["maternal"]["p"] < 0.05
    assert r["paternal"]["p"] > 0.05
    assert not r["difference_significant"]


def test_positive_covariance_shrinks_se_of_difference():
    without = stats.compare_parental_effects(0.045, 0.015, 0.010, 0.015)
    with_cov = stats.compare_parental_effects(0.045, 0.015, 0.010, 0.015, cov=0.00009)
    assert with_cov["se_difference"] < without["se_difference"]
    assert not without["difference_significant"] and with_cov["difference_significant"]


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        stats.compare_parental_effects(0.1, 0.0, 0.0, 0.02)
    with pytest.raises(ValueError):
        stats.compare_parental_effects(0.1, 0.01, 0.0, 0.01, cov=0.001)  # variance <= 0
