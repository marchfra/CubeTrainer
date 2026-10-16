"""Tests for the ex-Gaussian fit."""

import numpy as np
import pytest
from scipy import stats as sps

from cubetrainer.fits import (
    MIN_CURVE_SAMPLES,
    MIN_FIT_SAMPLES,
    fit_ex_gaussian,
    fit_learning_curve,
)

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
    """Density positive, cumulative curve rising from 0 to 1."""
    fit = fit_ex_gaussian(EX_GAUSSIAN)
    assert fit is not None
    grid = np.linspace(5, 60, 200)

    assert (fit.pdf(grid) >= 0).all()
    cdf = fit.cdf(grid)
    assert np.all(np.diff(cdf) >= -1e-12)
    assert cdf[0] < 0.01
    assert cdf[-1] > 0.99


@pytest.mark.parametrize(
    "data",
    [[10.0] * (MIN_FIT_SAMPLES - 1), [12.0] * 50, []],
    ids=["too few", "all equal", "empty"],
)
def test_no_fit_without_enough_varied_data(data: list[float]) -> None:
    """Fitting needs enough times that aren't all the same."""
    assert fit_ex_gaussian(data) is None


def improving_times(n: int = 400) -> np.ndarray:
    """Return times whose trend falls from 22 s towards 16 s (plus noise and tail).

    Args:
        n: How many.

    Returns:
        The times, oldest first.

    """
    rng = np.random.default_rng(1)
    numbers = np.arange(n)
    return 16 + 6 * np.exp(-numbers / 80) + rng.normal(0, 1.0, n)


def test_learning_curve_recovers_its_trend() -> None:
    """The fitted start, plateau and speed match the trend the times follow."""
    curve = fit_learning_curve(improving_times())

    assert curve is not None
    assert curve.start == pytest.approx(22, abs=0.6)
    assert curve.plateau == pytest.approx(16, abs=0.4)
    assert curve.scale == pytest.approx(80, abs=20)
    assert curve.half_life == pytest.approx(curve.scale * np.log(2))
    assert curve.improving
    assert curve.at(np.array([0.0]))[0] == pytest.approx(curve.start)


def test_flat_times_show_no_improvement() -> None:
    """Times with no trend don't count as improving."""
    curve = fit_learning_curve(np.random.default_rng(2).normal(15, 1, 200))

    assert curve is not None
    assert not curve.improving


def test_learning_curve_needs_enough_solves() -> None:
    """Too few times give no curve."""
    assert fit_learning_curve(improving_times(MIN_CURVE_SAMPLES - 1)) is None
