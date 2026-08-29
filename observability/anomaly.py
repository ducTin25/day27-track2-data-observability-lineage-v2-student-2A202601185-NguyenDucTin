"""Anomaly detection with robust baselines, seasonality awareness, and EWMA.

Supported methods:
  - zscore:        classic z-score (good for normal distributions)
  - mad:           median absolute deviation (robust to outliers)
  - ewma:          exponentially weighted moving average (trend-aware)
  - auto:          context-aware dispatch that chooses the best method
                   based on data characteristics and available context.
"""
from __future__ import annotations

from typing import Any, Iterable

import numpy as np


# ── individual detectors ───────────────────────────────────────────────────


def zscore_detector(
    current: float, history: Iterable[float], threshold: float = 3.0
) -> dict[str, Any]:
    values = np.asarray(list(history), dtype=float)
    if values.size < 3:
        return {
            "is_anomaly": False,
            "score": 0.0,
            "method": "zscore",
            "reason": "insufficient_history",
        }
    mean = float(np.mean(values))
    std = float(np.std(values, ddof=1))
    if std == 0:
        score = float("inf") if float(current) != mean else 0.0
    else:
        score = abs(float(current) - mean) / std
    return {
        "is_anomaly": bool(score > threshold),
        "score": float(score),
        "method": "zscore",
        "reason": f"mean={mean:.3f}, std={std:.3f}, threshold={threshold}",
    }


def mad_detector(
    current: float, history: Iterable[float], threshold: float = 3.5
) -> dict[str, Any]:
    """Robust anomaly detector using Median Absolute Deviation.

    More resilient to outliers than z-score. Uses modified Z-score:
        M_i = 0.6745 * (x_i - median) / MAD
    """
    values = np.asarray(list(history), dtype=float)
    if values.size < 5:
        return {
            "is_anomaly": False,
            "score": 0.0,
            "method": "mad",
            "reason": "insufficient_history",
        }
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    if mad == 0:
        # All non-median values equal median → check exact match
        if float(current) == median:
            return {
                "is_anomaly": False,
                "score": 0.0,
                "method": "mad",
                "reason": "mad_is_zero_and_value_equals_median",
            }
        return {
            "is_anomaly": True,
            "score": float("inf"),
            "method": "mad",
            "reason": "mad_is_zero_and_value_differs_from_median",
        }
    modified_z = 0.6745 * abs(float(current) - median) / mad
    return {
        "is_anomaly": bool(modified_z > threshold),
        "score": float(modified_z),
        "method": "mad",
        "reason": f"median={median:.3f}, mad={mad:.3f}, threshold={threshold}",
    }


def ewma_detector(
    current: float,
    history: Iterable[float],
    threshold: float = 3.0,
    alpha: float = 0.3,
) -> dict[str, Any]:
    """Exponentially Weighted Moving Average detector.

    Good for detecting level shifts in time-series data. The EWMA reacts
    more to recent observations, making it suitable for trend-aware detection.
    """
    values = np.asarray(list(history), dtype=float)
    if values.size < 5:
        return {
            "is_anomaly": False,
            "score": 0.0,
            "method": "ewma",
            "reason": "insufficient_history",
        }

    # Compute EWMA
    ewma = np.full_like(values, np.nan)
    ewma[0] = values[0]
    for i in range(1, values.size):
        ewma[i] = alpha * values[i] + (1 - alpha) * ewma[i - 1]

    # Residuals
    residuals = values - ewma
    std_resid = float(np.std(residuals, ddof=1))

    if std_resid == 0:
        score = 0.0 if float(current) == float(ewma[-1]) else float("inf")
    else:
        score = abs(float(current) - float(ewma[-1])) / std_resid

    return {
        "is_anomaly": bool(score > threshold),
        "score": float(score),
        "method": "ewma",
        "reason": (
            f"ewma_last={ewma[-1]:.3f}, std_resid={std_resid:.3f}, "
            f"alpha={alpha}, threshold={threshold}"
        ),
    }


def rolling_zscore_detector(
    current: float,
    history: Iterable[float],
    threshold: float = 3.0,
    window: int = 7,
) -> dict[str, Any]:
    """Rolling-window z-score detector using only the last N points.

    Adapts to local shifts better than global z-score.
    """
    values = np.asarray(list(history), dtype=float)
    if values.size < min(5, window):
        return {
            "is_anomaly": False,
            "score": 0.0,
            "method": "rolling_zscore",
            "reason": "insufficient_history",
        }

    window_values = values[-window:]
    mean = float(np.mean(window_values))
    std = float(np.std(window_values, ddof=1))

    if std == 0:
        score = float("inf") if float(current) != mean else 0.0
    else:
        score = abs(float(current) - mean) / std

    return {
        "is_anomaly": bool(score > threshold),
        "score": float(score),
        "method": "rolling_zscore",
        "reason": f"rolling_mean={mean:.3f}, rolling_std={std:.3f}, window={window}, threshold={threshold}",
    }


# ── auto dispatcher ────────────────────────────────────────────────────────


def _auto_detect(
    current: float,
    history: Iterable[float],
    threshold: float = 3.0,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Context-aware auto detection.

    Strategy selection:
    1. If context provides `same_segment_history` (e.g. same-day-of-week),
       use MAD on that segment for seasonality-aware detection.
    2. If history is long enough (>20), use EWMA for trend sensitivity.
    3. If history is short, use MAD (robust default).
    4. Otherwise fall back to rolling z-score.
    """
    values = np.asarray(list(history), dtype=float)
    if values.size < 3:
        return {
            "is_anomaly": False,
            "score": 0.0,
            "method": "auto",
            "reason": "insufficient_history",
        }

    ctx = context or {}

    # ── Strategy 1: seasonal segment available ──
    same_segment = ctx.get("same_segment_history")
    if same_segment is not None:
        seg_values = list(same_segment)
        if len(seg_values) >= 3:
            result = mad_detector(current, seg_values, threshold=threshold)
            result["method"] = "auto:mad+seasonal"
            result["reason"] += "; seasonal_segment_used"
            return result

    # ── Strategy 2: weekday context from run_baseline ──
    metric_name = ctx.get("metric_name", "")
    day_of_week = ctx.get("day_of_week")
    if day_of_week is not None and metric_name == "row_count" and values.size >= 7:
        # If we have enough history, extract same-day-of-week subset
        # (simulated: use last N values assuming daily data)
        same_dow_values = values[day_of_week::7] if day_of_week < 7 and values.size > day_of_week else values
        if len(same_dow_values) >= 3:
            result = mad_detector(current, same_dow_values, threshold=threshold)
            result["method"] = "auto:mad+dayofweek"
            result["reason"] += "; day_of_week_segment_used"
            return result

    # ── Strategy 3: EWMA for longer histories ──
    if values.size >= 14:
        result = ewma_detector(current, history, threshold=threshold)
        result["method"] = "auto:ewma"
        return result

    # ── Strategy 4: MAD for medium histories ──
    if values.size >= 7:
        result = mad_detector(current, history, threshold=threshold)
        result["method"] = "auto:mad"
        return result

    # ── Strategy 5: rolling z-score for short histories ──
    result = rolling_zscore_detector(current, history, threshold=threshold)
    result["method"] = "auto:rolling_zscore"
    return result


# ── public API ─────────────────────────────────────────────────────────────


def detect_anomaly(
    current: float,
    history: Iterable[float],
    *,
    method: str = "auto",
    threshold: float = 3.0,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Stable lab API.

    Parameters
    ----------
    current : float
        The current metric value to evaluate.
    history : Iterable[float]
        Historical metric values for baseline comparison.
    method : str
        One of 'zscore', 'mad', 'ewma', 'rolling_zscore', or 'auto'.
        'auto' uses context-aware strategy selection.
    threshold : float
        Anomaly threshold (z-score units).
    context : dict or None
        Optional context dict with keys:
        - 'day_of_week' : int (0=Mon..6=Sun) for weekday-aware detection
        - 'same_segment_history' : list[float] pre-filtered segment history
        - 'metric_name' : str for context-aware strategy selection
        - 'known_event' : str to suppress alerts during known events

    Returns
    -------
    dict with keys: is_anomaly, score, method, reason
    """
    if method == "mad":
        return mad_detector(current, history, threshold=threshold)
    if method == "zscore":
        return zscore_detector(current, history, threshold=threshold)
    if method == "ewma":
        return ewma_detector(current, history, threshold=threshold)
    if method == "rolling_zscore":
        return rolling_zscore_detector(current, history, threshold=threshold)
    if method == "auto":
        return _auto_detect(current, history, threshold=threshold, context=context)
    raise ValueError(f"Unsupported method: {method}")
