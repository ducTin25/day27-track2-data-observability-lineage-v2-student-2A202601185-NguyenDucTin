"""RAG metrics for detecting drift in text length and embedding distributions.

Provides:
  - Text length shift detection via z-score on mean lengths
  - Embedding norm shift detection via KS test and distribution comparison
"""
from __future__ import annotations

from typing import Any, Iterable

import numpy as np

from observability.anomaly import zscore_detector


def approximate_token_lengths(texts: Iterable[str]) -> list[int]:
    # Deliberately simple proxy; no tokenizer/model download needed.
    return [len(str(t).split()) for t in texts]


def detect_text_length_shift(
    current_texts: Iterable[str],
    baseline_batch_means: Iterable[float],
    *,
    threshold: float = 3.0,
) -> dict[str, Any]:
    """Detect shift in text length distribution of RAG documents.

    Parameters
    ----------
    current_texts : Iterable[str]
        Current batch of documents.
    baseline_batch_means : Iterable[float]
        Historical batch-mean lengths for baseline comparison.
    threshold : float
        Z-score threshold for anomaly detection.

    Returns
    -------
    dict with keys: is_anomaly, score, method, reason, metric, current_mean
    """
    lengths = approximate_token_lengths(current_texts)
    current_mean = float(np.mean(lengths)) if lengths else 0.0
    result = zscore_detector(current_mean, baseline_batch_means, threshold=threshold)
    result["metric"] = "mean_text_length"
    result["current_mean"] = current_mean
    return result


def _ks_statistic(current: np.ndarray, baseline: np.ndarray) -> float:
    """Compute the Kolmogorov-Smirnov statistic."""
    if current.size == 0 or baseline.size == 0:
        return 0.0
    combined = np.sort(np.concatenate([current, baseline]))
    cdf_current = np.searchsorted(np.sort(current), combined, side="right") / current.size
    cdf_baseline = np.searchsorted(np.sort(baseline), combined, side="right") / baseline.size
    return float(np.max(np.abs(cdf_current - cdf_baseline)))


def detect_embedding_norm_shift(
    current_norms: Iterable[float], baseline_norms: Iterable[float]
) -> dict[str, Any]:
    """Detect drift in embedding vector norms.

    Uses KS statistic to compare the distribution of current embedding norms
    against a baseline distribution. A significant shift in norm distribution
    can indicate embedding drift (e.g. from model change, data drift, or
    retrieval quality degradation).

    Parameters
    ----------
    current_norms : Iterable[float]
        Norms of current embedding vectors.
    baseline_norms : Iterable[float]
        Reference norms from the baseline embedding distribution.

    Returns
    -------
    dict with keys: is_anomaly, score, method, reason
    """
    cur = np.asarray(list(current_norms), dtype=float)
    base = np.asarray(list(baseline_norms), dtype=float)

    if cur.size < 3 or base.size < 3:
        return {
            "is_anomaly": False,
            "score": 0.0,
            "method": "embedding_ks",
            "reason": f"insufficient_data: current={cur.size}, baseline={base.size}",
        }

    # KS test on norm distributions
    ks = _ks_statistic(cur, base)

    # Also compare mean and std
    cur_mean = float(np.mean(cur))
    base_mean = float(np.mean(base))
    cur_std = float(np.std(cur, ddof=1)) if cur.size > 1 else 0.0
    base_std = float(np.std(base, ddof=1)) if base.size > 1 else 0.0

    # Z-score on means
    mean_se = base_std / np.sqrt(base.size) if base_std > 0 and base.size > 0 else 1.0
    mean_z = abs(cur_mean - base_mean) / float(mean_se) if mean_se > 0 else 0.0

    # Combined score
    score = max(ks * 3, mean_z / 2)  # Normalize to ~comparable scale

    # Threshold: KS > 0.3 or mean_z > 3.0
    is_anomaly = ks > 0.3 or mean_z > 3.0

    return {
        "is_anomaly": bool(is_anomaly),
        "score": float(score),
        "method": "embedding_ks",
        "reason": (
            f"ks_statistic={ks:.4f}, mean_z={mean_z:.2f}, "
            f"base_mean={base_mean:.4f}, cur_mean={cur_mean:.4f}, "
            f"base_std={base_std:.4f}, cur_std={cur_std:.4f}"
        ),
    }
