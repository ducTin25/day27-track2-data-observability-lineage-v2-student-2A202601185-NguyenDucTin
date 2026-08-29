"""Distribution drift detection using multiple statistical methods.

Provides:
  - KS test (Kolmogorov-Smirnov): non-parametric test comparing two distributions
  - PSI (Population Stability Index): measures relative entropy between bins
  - Quantile drift: checks for drift in key percentiles
  - Mean-ratio: simple mean comparison (starter baseline)
  - Auto: chooses best method based on data size
"""
from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def _psi(current: np.ndarray, baseline: np.ndarray, n_bins: int = 10) -> float:
    """Compute Population Stability Index."""
    all_vals = np.concatenate([current, baseline])
    if all_vals.size == 0:
        return 0.0
    bins = np.percentile(baseline, np.linspace(0, 100, n_bins + 1))
    # Handle duplicate bin edges
    bins = np.unique(bins)
    if len(bins) < 2:
        return 0.0

    base_counts, _ = np.histogram(baseline, bins=bins)
    curr_counts, _ = np.histogram(current, bins=bins)

    # Convert to proportions
    base_pct = base_counts / max(baseline.size, 1)
    curr_pct = curr_counts / max(current.size, 1)

    # Add epsilon to avoid log(0)
    eps = 1e-10
    base_pct = np.clip(base_pct, eps, 1)
    curr_pct = np.clip(curr_pct, eps, 1)

    psi_val = float(np.sum((curr_pct - base_pct) * np.log(curr_pct / base_pct)))
    return psi_val


def _ks_statistic(current: np.ndarray, baseline: np.ndarray) -> float:
    """Compute the Kolmogorov-Smirnov statistic (max absolute ECDF difference)."""
    all_vals = np.concatenate([current, baseline])
    if all_vals.size == 0:
        return 0.0

    # Sort and compute ECDFs
    combined = np.sort(np.concatenate([current, baseline]))
    cdf_current = np.searchsorted(np.sort(current), combined, side="right") / current.size
    cdf_baseline = np.searchsorted(np.sort(baseline), combined, side="right") / baseline.size

    return float(np.max(np.abs(cdf_current - cdf_baseline)))


def _quantile_drift(current: np.ndarray, baseline: np.ndarray) -> tuple[float, str]:
    """Check drift in key quantiles (median, IQR)."""
    if baseline.size < 2 or current.size < 2:
        return 0.0, "insufficient_data"

    q_baseline = np.percentile(baseline, [25, 50, 75])
    q_current = np.percentile(current, [25, 50, 75])

    # Relative drift in median
    median_drift = abs(q_current[1] - q_baseline[1]) / max(abs(q_baseline[1]), 1e-10)

    # Relative drift in IQR
    iqr_base = q_baseline[2] - q_baseline[0]
    iqr_curr = q_current[2] - q_current[0]
    iqr_drift = abs(iqr_curr - iqr_base) / max(iqr_base, 1e-10)

    combined_drift = max(median_drift, iqr_drift)
    return float(combined_drift), (
        f"baseline_q50={q_baseline[1]:.3f}, current_q50={q_current[1]:.3f}, "
        f"baseline_iqr={iqr_base:.3f}, current_iqr={iqr_curr:.3f}"
    )


def detect_distribution_shift(
    current_values: Iterable[float],
    baseline_values: Iterable[float],
    *,
    method: str = "auto",
    psi_threshold: float = 0.2,
    ks_threshold: float = 0.3,
    ratio_threshold: float = 3.0,
    quantile_threshold: float = 2.0,
) -> dict[str, Any]:
    """Detect distribution shift between current and baseline values.

    Parameters
    ----------
    current_values : Iterable[float]
        Current period values.
    baseline_values : Iterable[float]
        Reference/baseline period values.
    method : str
        One of 'mean_ratio', 'ks', 'psi', 'quantile', or 'auto'.
        'auto' chooses the best method based on data size.
    psi_threshold : float
        Threshold for PSI (>0.2 typically indicates significant drift).
    ks_threshold : float
        Threshold for KS statistic.
    ratio_threshold : float
        Threshold for mean ratio method.
    quantile_threshold : float
        Threshold for quantile drift.

    Returns
    -------
    dict with keys: is_anomaly, score, method, reason
    """
    cur = np.asarray(list(current_values), dtype=float)
    base = np.asarray(list(baseline_values), dtype=float)

    if cur.size == 0 or base.size == 0:
        return {
            "is_anomaly": False,
            "score": 0.0,
            "method": method,
            "reason": "empty_input",
        }

    # ── mean_ratio (starter baseline) ──
    if method == "mean_ratio":
        cur_mean = float(np.mean(cur))
        base_mean = float(np.mean(base))
        if base_mean == 0:
            score = float("inf") if cur_mean != 0 else 1.0
        else:
            score = (
                max(abs(cur_mean / base_mean), abs(base_mean / cur_mean))
                if cur_mean != 0
                else float("inf")
            )
        return {
            "is_anomaly": bool(score >= ratio_threshold),
            "score": float(score),
            "method": "mean_ratio",
            "reason": f"baseline_mean={base_mean:.3f}, current_mean={cur_mean:.3f}",
        }

    # ── KS test ──
    if method == "ks":
        ks = _ks_statistic(cur, base)
        return {
            "is_anomaly": bool(ks > ks_threshold),
            "score": float(ks),
            "method": "ks",
            "reason": f"ks_statistic={ks:.4f}, threshold={ks_threshold}",
        }

    # ── PSI ──
    if method == "psi":
        psi_val = _psi(cur, base)
        return {
            "is_anomaly": bool(psi_val > psi_threshold),
            "score": float(psi_val),
            "method": "psi",
            "reason": f"psi={psi_val:.4f}, threshold={psi_threshold}",
        }

    # ── quantile drift ──
    if method == "quantile":
        score, detail = _quantile_drift(cur, base)
        return {
            "is_anomaly": bool(score > quantile_threshold),
            "score": float(score),
            "method": "quantile",
            "reason": f"quantile_drift={score:.4f}, threshold={quantile_threshold}; {detail}",
        }

    # ── auto: choose method based on data ──
    if method == "auto":
        if cur.size >= 10 and base.size >= 10:
            # Use KS + PSI combo for larger samples
            ks = _ks_statistic(cur, base)
            psi_val = _psi(cur, base)
            score = max(ks / ks_threshold, psi_val / psi_threshold)
            is_anomaly = ks > ks_threshold or psi_val > psi_threshold
            return {
                "is_anomaly": bool(is_anomaly),
                "score": float(score),
                "method": "auto:ks+psi",
                "reason": f"ks={ks:.4f}, psi={psi_val:.4f}, thresholds=({ks_threshold}, {psi_threshold})",
            }

        # Use quantile drift for moderate samples
        if cur.size >= 5 and base.size >= 5:
            score, detail = _quantile_drift(cur, base)
            return {
                "is_anomaly": bool(score > quantile_threshold),
                "score": float(score),
                "method": "auto:quantile",
                "reason": f"quantile_drift={score:.4f}, threshold={quantile_threshold}; {detail}",
            }

        # Fall back to mean ratio for small samples
        cur_mean = float(np.mean(cur))
        base_mean = float(np.mean(base))
        if base_mean == 0:
            score = float("inf") if cur_mean != 0 else 1.0
        else:
            score = (
                max(abs(cur_mean / base_mean), abs(base_mean / cur_mean))
                if cur_mean != 0
                else float("inf")
            )
        return {
            "is_anomaly": bool(score >= ratio_threshold),
            "score": float(score),
            "method": "auto:mean_ratio",
            "reason": f"baseline_mean={base_mean:.3f}, current_mean={cur_mean:.3f}",
        }

    raise ValueError(f"Unsupported method: {method}")
