"""Tests for the ex-Gaussian fit."""

import numpy as np
import pytest
from scipy import stats as sps

from cubetrainer.fits import MIN_FIT_SAMPLES, empirical_cdf, fit_ex_gaussian

RNG = np.random.default_rng(0)
EX_GAUSSIAN = RNG.normal(15, 1.5, 3000) + RNG.exponential(2.5, 3000)


def test_recovers_its_parameters() -> None:
    """On ex-Gaussian data the fit finds μ, σ and τ, with a small D."""
    fit = fit_ex_gaussian(EX_GAUSSIAN)

    assert fit is not None
    assert fit.mu == pytest.approx(15, abs=0.2)
    assert fit.sigma == pytest.approx(1.5, abs=0.2)
    assert fit.tau == pytest.approx(2.5, abs=0.2)
    assert fit.ks < 0.03


def test_fits_skewed_data_better_than_a_gaussian() -> None:
    """D is smaller than a Gaussian's on the same skewed times."""
    fit = fit_ex_gaussian(EX_GAUSSIAN)
    gaussian = sps.norm(*sps.norm.fit(EX_GAUSSIAN))

    assert fit is not None
    assert fit.ks < sps.kstest(EX_GAUSSIAN, gaussian.cdf).statistic


def test_fitted_functions_are_a_distribution() -> None:
    """Density positive, cumulative curve rising from 0 to 1, ppf its inverse."""
    fit = fit_ex_gaussian(EX_GAUSSIAN)
    assert fit is not None
    grid = np.linspace(5, 60, 200)

    assert (fit.pdf(grid) >= 0).all()
    cdf = fit.cdf(grid)
    assert np.all(np.diff(cdf) >= -1e-12)
    assert cdf[0] < 0.01
    assert cdf[-1] > 0.99
    assert fit.cdf(fit.ppf(np.array([0.5])))[0] == pytest.approx(0.5)


@pytest.mark.parametrize(
    "data",
    [[10.0] * (MIN_FIT_SAMPLES - 1), [12.0] * 50, []],
    ids=["too few", "all equal", "empty"],
)
def test_no_fit_without_enough_varied_data(data: list[float]) -> None:
    """Fitting needs enough times that aren't all the same."""
    assert fit_ex_gaussian(data) is None


def test_empirical_cdf() -> None:
    """Sorted times with the share of times at or below each."""
    times, shares = empirical_cdf([3.0, 1.0, 2.0, 2.0])

    assert times.tolist() == [1.0, 2.0, 2.0, 3.0]
    assert shares.tolist() == [0.25, 0.5, 0.75, 1.0]
