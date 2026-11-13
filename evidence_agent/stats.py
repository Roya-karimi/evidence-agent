"""Statistical tools the agent can call.

The key idea: the language model never does arithmetic itself. It asks for a
calculation by name, and this module computes it exactly.
"""

import math
from statistics import NormalDist

_STD_NORMAL = NormalDist()


def two_sided_p(z: float) -> float:
    """Two-sided p-value for a standard normal test statistic."""
    return math.erfc(abs(z) / math.sqrt(2))


def wald_test(beta: float, se: float) -> dict:
    """Test H0: beta = 0 for a single estimate."""
    if se <= 0:
        raise ValueError("Standard error must be positive.")
    z = beta / se
    return {"beta": beta, "se": se, "z": z, "p": two_sided_p(z)}


def compare_parental_effects(
    beta_maternal: float,
    se_maternal: float,
    beta_paternal: float,
    se_paternal: float,
    cov: float = 0.0,
    alpha: float = 0.05,
) -> dict:
    """Test whether the maternal and paternal effects differ.

    H0: beta_maternal - beta_paternal = 0

        diff    = beta_m - beta_p
        se_diff = sqrt(se_m^2 + se_p^2 - 2 * cov)
        z       = diff / se_diff

    `cov` is the covariance between the two estimates. It is 0 only if they
    come from independent samples. If both come from the same regression
    model (common in trio designs), the covariance should be taken from the
    model's variance-covariance matrix; assuming 0 can make the test too
    conservative or too liberal depending on its sign.

    Why this test matters: "maternal p < 0.05, paternal p > 0.05" does not
    show that the two effects differ. The difference must be tested directly.
    """
    var_diff = se_maternal**2 + se_paternal**2 - 2 * cov
    if se_maternal <= 0 or se_paternal <= 0 or var_diff <= 0:
        raise ValueError("Standard errors must be positive and the variance of the difference > 0.")

    diff = beta_maternal - beta_paternal
    se_diff = math.sqrt(var_diff)
    z = diff / se_diff
    q = _STD_NORMAL.inv_cdf(1 - alpha / 2)

    return {
        "maternal": wald_test(beta_maternal, se_maternal),
        "paternal": wald_test(beta_paternal, se_paternal),
        "difference": diff,
        "se_difference": se_diff,
        "z_difference": z,
        "p_difference": two_sided_p(z),
        "ci_low": diff - q * se_diff,
        "ci_high": diff + q * se_diff,
        "alpha": alpha,
        "difference_significant": two_sided_p(z) < alpha,
        "covariance_assumed": cov,
    }


def compare_value(claimed: float, source: float, tolerance: float = 0.0) -> dict:
    """Compare a claimed number with the source number."""
    abs_diff = abs(claimed - source)
    return {
        "claimed": claimed,
        "source": source,
        "absolute_difference": abs_diff,
        "tolerance": tolerance,
        "matches": abs_diff <= tolerance,
    }
