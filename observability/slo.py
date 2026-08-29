"""SLO / error-budget calculator and multi-window burn-rate alerting.

Based on Google SRE Workbook — Alerting on SLOs:
  https://sre.google/workbook/alerting-on-slos/
"""
from __future__ import annotations

from typing import Any


def calculate_slo(target: float, bad_events: int, total_events: int) -> dict[str, Any]:
    """Compute SLO status and error budget consumption.

    Parameters
    ----------
    target : float
        Target availability (e.g. 0.995 for 99.5%).
    bad_events : int
        Number of bad events in the window.
    total_events : int
        Total events in the window.

    Returns
    -------
    dict with keys: target, actual_bad_rate, allowed_bad_rate,
                    burn_rate, remaining_error_budget_fraction, breached
    """
    if not 0 < target < 1:
        raise ValueError("target must be between 0 and 1 (exclusive)")
    if bad_events < 0 or total_events < 0 or bad_events > total_events:
        raise ValueError("invalid event counts")
    allowed_bad_rate = 1.0 - target
    if total_events == 0:
        return {
            "target": target,
            "actual_bad_rate": 0.0,
            "allowed_bad_rate": allowed_bad_rate,
            "burn_rate": 0.0,
            "remaining_error_budget_fraction": 1.0,
            "breached": False,
        }
    actual_bad_rate = bad_events / total_events
    burn_rate = actual_bad_rate / allowed_bad_rate
    consumed_fraction = min(1.0, actual_bad_rate / allowed_bad_rate)
    return {
        "target": target,
        "actual_bad_rate": actual_bad_rate,
        "allowed_bad_rate": allowed_bad_rate,
        "burn_rate": burn_rate,
        "remaining_error_budget_fraction": max(0.0, 1.0 - consumed_fraction),
        "breached": bool(actual_bad_rate > allowed_bad_rate),
    }


def evaluate_multiwindow_burn(
    *,
    short_window_burn: float,
    long_window_burn: float,
    policy: str = "default",
    short_threshold: float = 10.0,
    long_threshold: float = 2.0,
) -> dict[str, Any]:
    """Multi-window burn-rate alerting policy.

    Implements Google SRE practice:
      - A short burst (high short-window burn, low long-window burn) is a
        transient spike → no page.
      - Sustained fast burn (both windows elevated) → page.

    Parameters
    ----------
    short_window_burn : float
        Burn rate over a short window (e.g. 1 hour).
    long_window_burn : float
        Burn rate over a long window (e.g. 6 hours or 1 day).
    policy : str
        'default' or 'starter'. 'starter' never pages (backwards compat).
    short_threshold : float
        Short-window burn rate threshold for alerting (default 10x).
    long_threshold : float
        Long-window burn rate threshold for sustained burn (default 2x).

    Returns
    -------
    dict with keys: page, severity, reason, short_window_burn, long_window_burn
    """
    if policy == "starter":
        return {
            "page": False,
            "severity": "info",
            "reason": "starter_policy_not_implemented",
            "short_window_burn": short_window_burn,
            "long_window_burn": long_window_burn,
        }

    # ── Default Google SRE-style policy ──
    reasons: list[str] = []
    page = False
    severity = "info"

    if long_window_burn >= long_threshold:
        # Sustained burn: error budget would be exhausted within the long window
        if short_window_burn >= short_threshold:
            page = True
            severity = "critical"
            reasons.append(
                f"sustained_fast_burn: short={short_window_burn:.2f}x, "
                f"long={long_window_burn:.2f}x"
            )
        else:
            # Long window elevated but short window moderate — still sustained
            page = True
            severity = "warning"
            reasons.append(
                f"sustained_burn: long_window={long_window_burn:.2f}x "
                f"(short={short_window_burn:.2f}x)"
            )
    elif short_window_burn >= short_threshold:
        # Transient spike: short window high but long window normal
        reasons.append(
            f"transient_spike: short={short_window_burn:.2f}x, "
            f"long={long_window_burn:.2f}x — no page"
        )
    else:
        reasons.append("normal_burn_rate_within_budget")

    return {
        "page": page,
        "severity": severity,
        "reason": "; ".join(reasons),
        "short_window_burn": short_window_burn,
        "long_window_burn": long_window_burn,
    }
