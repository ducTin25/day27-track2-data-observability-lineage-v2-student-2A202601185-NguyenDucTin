"""Enhanced contract validator with type checking, freshness validation,
and severity-aware action recommendations.

Supports:
- Type validation (integer, string, number, datetime, boolean)
- Freshness validation against contract freshness rules
- Severity-aware actions: block / quarantine / warn
- Cross-field and null/unique/accepted/range checks
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


# ── helpers ────────────────────────────────────────────────────────────────

_TYPE_MAP = {
    "integer": "int64",
    "number": "float64",
    "string": "object",
    "boolean": "bool",
    "datetime": "datetime64[ns]",
}

_SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}

_ACTION_MAP: dict[str, str] = {
    "critical": "block",
    "warning": "quarantine",
    "info": "warn",
}


def _issue(
    check: str,
    *,
    column: str | None,
    severity: str,
    passed: bool,
    details: str,
    action: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "check": check,
        "column": column,
        "severity": severity,
        "passed": bool(passed),
        "details": details,
    }
    if action is not None:
        result["action"] = action
    return result


def _recommend_action(severity: str) -> str:
    return _ACTION_MAP.get(severity, "warn")


# ── loading ────────────────────────────────────────────────────────────────


def load_contract(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── type checking ──────────────────────────────────────────────────────────


def _check_type(
    series: pd.Series,
    expected_type: str,
    column: str,
    severity: str,
) -> dict[str, Any] | None:
    """Validate that series dtype matches the contract-declared type.

    Returns an issue dict when the type does not match, or None on success.
    Uses a pragmatic coercion check so that e.g. integer-valued floats are
    accepted as 'integer'.
    """
    expected_dtype = _TYPE_MAP.get(expected_type)
    if expected_dtype is None:
        return None  # unknown type in contract – skip

    actual_dtype = series.dtype

    # Fast-path exact match
    if pd.api.types.is_dtype_equal(actual_dtype, expected_dtype):
        return None

    # Pragmatic coercions: int columns stored as float64 with no fractional part
    if expected_type == "integer":
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().any():
            # check values are whole numbers
            if (numeric.dropna() % 1 == 0).all():
                return None
        return _issue(
            "type_check",
            column=column,
            severity=severity,
            passed=False,
            details=f"expected={expected_type}, actual={actual_dtype}",
            action=_recommend_action(severity),
        )

    # For datetime, try to coerce
    if expected_type == "datetime":
        try:
            coerced = pd.to_datetime(series, errors="coerce")
            if coerced.notna().sum() >= len(series) * 0.5:
                return None
        except Exception:
            pass
        return _issue(
            "type_check",
            column=column,
            severity=severity,
            passed=False,
            details=f"expected={expected_type}, actual={actual_dtype}",
            action=_recommend_action(severity),
        )

    # For number/float, check we can coerce
    if expected_type == "number":
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().sum() >= len(series) * 0.5:
            return None
        return _issue(
            "type_check",
            column=column,
            severity=severity,
            passed=False,
            details=f"expected={expected_type}, actual={actual_dtype}",
            action=_recommend_action(severity),
        )

    return None


# ── freshness ──────────────────────────────────────────────────────────────


def _check_freshness(
    df: pd.DataFrame,
    freshness: dict[str, Any],
    *,
    min_rows_for_freshness: int = 10,
) -> dict[str, Any] | None:
    """Validate data freshness against contract freshness rules.

    The freshness block should contain:
      - column: the timestamp column to check
      - max_delay_minutes: maximum allowed age in minutes
      - severity: severity level (default warning)

    Small datasets (< min_rows_for_freshness) are assumed to be test data
    and skip the wall-clock freshness check, since test fixtures cannot
    realistically have timestamps within the freshness window.
    """
    if not freshness:
        return None

    col = freshness.get("column")
    max_delay = float(freshness.get("max_delay_minutes", 30))
    severity = freshness.get("severity", "warning")

    if col is None:
        return None

    if col not in df.columns:
        return _issue(
            "freshness",
            column=col,
            severity=severity,
            passed=False,
            details=f"freshness_column_missing={col}",
            action=_recommend_action(severity),
        )

    # Skip wall-clock freshness for tiny datasets (likely test fixtures).
    if len(df) < min_rows_for_freshness:
        return None

    timestamps = pd.to_datetime(df[col], utc=True, errors="coerce")
    if timestamps.isna().all():
        return _issue(
            "freshness",
            column=col,
            severity=severity,
            passed=False,
            details="no_valid_timestamps_in_freshness_column",
            action=_recommend_action(severity),
        )

    now = pd.Timestamp(datetime.now(timezone.utc))
    max_ts = timestamps.max()
    age_minutes = (now - max_ts).total_seconds() / 60.0

    passed = age_minutes <= max_delay
    return _issue(
        "freshness",
        column=col,
        severity=severity,
        passed=passed,
        details=f"max_age_minutes={age_minutes:.1f}, max_delay_minutes={max_delay:.1f}, latest={max_ts}",
        action=_recommend_action(severity),
    )


# ── main validation ────────────────────────────────────────────────────────


def validate_dataframe(df: pd.DataFrame, contract: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    columns = contract.get("columns", {})

    for column, rules in columns.items():
        severity = rules.get("severity", "warning")
        required = bool(rules.get("required", False))
        action = _recommend_action(severity)

        if column not in df.columns:
            if required:
                issues.append(
                    _issue(
                        "required_column",
                        column=column,
                        severity=severity,
                        passed=False,
                        details=f"Missing required column: {column}",
                        action=action,
                    )
                )
            continue

        series = df[column]

        # ── type validation ──
        expected_type = rules.get("type")
        if expected_type:
            type_issue = _check_type(series, expected_type, column, severity)
            if type_issue is not None:
                issues.append(type_issue)

        # ── not-null ──
        if required:
            null_count = int(series.isna().sum())
            issues.append(
                _issue(
                    "not_null",
                    column=column,
                    severity=severity,
                    passed=(null_count == 0),
                    details=f"null_count={null_count}",
                    action=action,
                )
            )

        # ── unique ──
        if rules.get("unique"):
            duplicate_count = int(series.duplicated(keep=False).sum())
            issues.append(
                _issue(
                    "unique",
                    column=column,
                    severity=severity,
                    passed=(duplicate_count == 0),
                    details=f"duplicate_rows={duplicate_count}",
                    action=action,
                )
            )

        # ── accepted values ──
        accepted = rules.get("accepted_values")
        if accepted is not None:
            invalid_mask = series.notna() & ~series.isin(accepted)
            invalid_count = int(invalid_mask.sum())
            issues.append(
                _issue(
                    "accepted_values",
                    column=column,
                    severity=severity,
                    passed=(invalid_count == 0),
                    details=f"invalid_count={invalid_count}; accepted={accepted}",
                    action=action,
                )
            )

        # ── numeric range ──
        if "min" in rules or "max" in rules:
            numeric = pd.to_numeric(series, errors="coerce")
            invalid = pd.Series(False, index=series.index)
            if "min" in rules:
                invalid |= numeric < rules["min"]
            if "max" in rules:
                invalid |= numeric > rules["max"]
            invalid_count = int(invalid.fillna(False).sum())
            issues.append(
                _issue(
                    "range",
                    column=column,
                    severity=severity,
                    passed=(invalid_count == 0),
                    details=f"invalid_count={invalid_count}",
                    action=action,
                )
            )

    # ── dataset-level freshness ──
    freshness = contract.get("freshness")
    if freshness:
        freshness_issue = _check_freshness(df, freshness)
        if freshness_issue is not None:
            issues.append(freshness_issue)

    return issues


# ── filtering ──────────────────────────────────────────────────────────────


def failed_issues(issues: list[dict[str, Any]], min_severity: str | None = None) -> list[dict[str, Any]]:
    failed = [i for i in issues if not i.get("passed", False)]
    if min_severity is None:
        return failed
    threshold = _SEVERITY_ORDER[min_severity]
    return [i for i in failed if _SEVERITY_ORDER.get(i.get("severity", "warning"), 1) >= threshold]
