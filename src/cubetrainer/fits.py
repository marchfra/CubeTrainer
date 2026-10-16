"""Fitting the ex-Gaussian distribution to solve times.

Solve times are skewed: most cluster around a typical time, with a tail of slow
solves. The ex-Gaussian, a normal distribution plus an exponential one, is the usual
model for that shape, and its three parameters each mean something for a cuber:

- μ: the typical clean solve, when nothing goes wrong;
- σ: how consistent those clean solves are;
- τ: how big the tail of bad solves is (lockups, misrecognitions, pauses).

The fit also reports the Kolmogorov-Smirnov statistic D: the largest gap between
the fitted and the observed cumulative distribution (smaller is better).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats as sps

#: Fewest finished solves worth fitting a distribution to.
MIN_FIT_SAMPLES: int = 10


@dataclass(frozen=True, slots=True)
class ExGaussianFit:
    """An ex-Gaussian fitted to some times (in seconds).

    Attributes:
        mu: Mean of the normal part: the typical clean solve.
        sigma: Spread of the normal part: the consistency of clean solves.
        tau: Mean of the exponential part: the size of the bad-solve tail.
        ks: Kolmogorov-Smirnov statistic D against the data (0 to 1).
        pdf: Density at given times.
        cdf: Cumulative probability at given times.
        ppf: Time below which a given share of solves falls (inverse of ``cdf``).

    """

    mu: float
    sigma: float
    tau: float
    ks: float
    pdf: Callable[[np.ndarray], np.ndarray]
    cdf: Callable[[np.ndarray], np.ndarray]
    ppf: Callable[[np.ndarray], np.ndarray]


def fit_ex_gaussian(seconds: Sequence[float] | np.ndarray) -> ExGaussianFit | None:
    """Fit an ex-Gaussian distribution to some times.

    Args:
        seconds: Finished solve times in seconds (no DNFs), as a list or array.

    Returns:
        The fit, or None if there are fewer than ``MIN_FIT_SAMPLES`` times or they're
        all equal.

    """
    data = np.asarray(seconds, dtype=float)
    if data.size < MIN_FIT_SAMPLES or np.ptp(data) == 0:
        return None
    # scipy's exponnorm uses (K, loc, scale): μ = loc, σ = scale, τ = K·scale.
    k, loc, scale = (float(p) for p in sps.exponnorm.fit(data))
    frozen = sps.exponnorm(k, loc, scale)
    ks = float(sps.kstest(data, frozen.cdf).statistic)
    return ExGaussianFit(loc, scale, k * scale, ks, frozen.pdf, frozen.cdf, frozen.ppf)


def empirical_cdf(
    seconds: Sequence[float] | np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return the observed cumulative distribution of some times.

    Args:
        seconds: Times in seconds.

    Returns:
        The sorted times and, for each, the fraction of times at or below it.

    """
    data = np.sort(np.asarray(seconds, dtype=float))
    return data, np.arange(1, data.size + 1) / data.size
