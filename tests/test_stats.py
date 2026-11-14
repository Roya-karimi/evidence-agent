import math

import pytest

from evidence_agent import stats


def test_difference_test_known_values():
    r = stats.compare_parental_effects(0.10, 0.02, 0.0, 0.02, cov=0.0)
    assert r["difference"] == pytest.approx(0.10)
    assert r["se_difference"] == pytest.approx(math.sqrt(0.02**2 * 2))
    assert r["z_difference"] == pytest.approx(3.5355, abs=1e-3)
    assert r["p_difference"] == pytest.approx(0.000407, abs=1e-5)
    assert r["difference_significant"]


def test_one_side_significant_is_not_a_difference():
    # maternal p ~ 0.012, paternal p ~ 0.35, yet the difference is not significant
    r = stats.compare_parental_effects(0.040, 0.016, 0.015, 0.016, cov=0.0)
    assert r["maternal"]["p"] < 0.05
    assert r["paternal"]["p"] > 0.05
    assert not r["difference_significant"]


def test_positive_covariance_shrinks_se_of_difference():
    without = stats.compare_parental_effects(0.045, 0.015, 0.010, 0.015, cov=0.0)
    with_cov = stats.compare_parental_effects(0.045, 0.015, 0.010, 0.015, cov=0.00009)
    assert with_cov["se_difference"] < without["se_difference"]
    assert not without["difference_significant"] and with_cov["difference_significant"]


def test_covariance_has_no_default():
    with pytest.raises(TypeError):
        stats.compare_parental_effects(0.1, 0.02, 0.0, 0.02)


@pytest.mark.parametrize("kwargs", [
    dict(se_maternal=0.0),                    # SE must be positive
    dict(se_paternal=-0.01),
    dict(cov=0.00024),                        # beyond se_m * se_p = 0.0002: correlation > 1
    dict(cov=-0.00024),
    dict(alpha=1.5), dict(alpha=0.0), dict(alpha=True),
    dict(beta_maternal=float("inf")), dict(beta_paternal=float("nan")), dict(se_maternal="0.01"),
])
def test_impossible_inputs_are_rejected(kwargs):
    args = dict(beta_maternal=0.05, se_maternal=0.01, beta_paternal=0.0, se_paternal=0.02, cov=0.0, alpha=0.05)
    with pytest.raises(ValueError):
        stats.compare_parental_effects(**{**args, **kwargs})


def test_zero_variance_of_difference_is_rejected():
    with pytest.raises(ValueError):
        stats.compare_parental_effects(0.1, 0.01, 0.0, 0.01, cov=0.0001)   # perfectly correlated, equal SEs


def test_wald_and_value_comparison_reject_non_finite_numbers():
    with pytest.raises(ValueError):
        stats.wald_test(float("inf"), 0.1)
    with pytest.raises(ValueError):
        stats.compare_value(1.0, 1.0, tolerance=-0.5)
