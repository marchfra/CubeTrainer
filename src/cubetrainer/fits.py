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

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats as sps
from scipy.optimize import curve_fit

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

    """

    mu: float
    sigma: float
    tau: float
    ks: float
    pdf: Callable[[np.ndarray], np.ndarray]
    cdf: Callable[[np.ndarray], np.ndarray]


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
    return ExGaussianFit(loc, scale, k * scale, ks, frozen.pdf, frozen.cdf)


#: Fewest finished solves worth fitting a learning curve to.
MIN_CURVE_SAMPLES: int = 30


@dataclass(frozen=True, slots=True)
class LearningCurve:
    """Exponential learning curve: t(n) = plateau + (start - plateau)·e^(-n/scale).

    Times improve quickly at first and then level off towards the plateau. Every
    ``half_life`` solves, the remaining gap to the plateau halves.

    Attributes:
        start: Fitted time at the first solve, in seconds.
        plateau: The time the curve levels off at, in seconds.
        scale: How many solves the improvement takes (larger is slower).
        gain_error: Standard error of the gain (start - plateau), in seconds.

    """

    start: float
    plateau: float
    scale: float
    gain_error: float = 0.0

    @property
    def half_life(self) -> float:
        """Solves it takes to halve the remaining gap to the plateau."""
        return self.scale * math.log(2)

    @property
    def improving(self) -> bool:
        """Whether the times really go down, beyond what noise could produce.

        The gain must be at least a tenth of a second and more than twice its
        standard error: random scatter alone often fits a small, spurious trend.
        """
        gain = self.start - self.plateau
        return gain >= 0.1 and gain > 2 * self.gain_error  # noqa: PLR2004

    def at(self, numbers: np.ndarray) -> np.ndarray:
        """Return the fitted times at some solve numbers.

        Args:
            numbers: Solve numbers (0 is the first solve).

        Returns:
            The fitted times, in seconds.

        """
        return _curve(numbers, self.start, self.plateau, self.scale)


def _curve(n: np.ndarray, start: float, plateau: float, scale: float) -> np.ndarray:
    """Evaluate the learning-curve formula (also used by the fitting routine).

    Args:
        n: Solve numbers.
        start: Time at the first solve.
        plateau: Time the curve levels off at.
        scale: Solves the improvement takes.

    Returns:
        The times.

    """
    return plateau + (start - plateau) * np.exp(-n / scale)


def fit_learning_curve(seconds: Sequence[float] | np.ndarray) -> LearningCurve | None:
    """Fit an exponential learning curve to times in the order they were done.

    Args:
        seconds: Finished solve times in seconds, oldest first.

    Returns:
        The curve, or None with fewer than ``MIN_CURVE_SAMPLES`` times or when the
        fit doesn't converge.

    """
    data = np.asarray(seconds, dtype=float)
    if data.size < MIN_CURVE_SAMPLES:
        return None
    numbers = np.arange(data.size, dtype=float)
    head, tail = float(np.median(data[:10])), float(np.median(data[-10:]))
    guess = (head, min(head, tail), data.size / 3)
    bounds = ([0.0, 0.0, 1.0], [np.inf, np.inf, 50.0 * data.size])
    try:
        params, covariance = curve_fit(
            _curve,
            numbers,
            data,
            p0=guess,
            bounds=bounds,
            maxfev=5000,
        )
    except (RuntimeError, ValueError):
        return None
    start, plateau, scale = (float(p) for p in params)
    # Var(start - plateau) = Var(start) + Var(plateau) - 2 Cov(start, plateau).
    variance = covariance[0, 0] + covariance[1, 1] - 2 * covariance[0, 1]
    gain_error = math.sqrt(variance) if math.isfinite(variance) and variance > 0 else 0
    return LearningCurve(start, plateau, scale, float(gain_error))
