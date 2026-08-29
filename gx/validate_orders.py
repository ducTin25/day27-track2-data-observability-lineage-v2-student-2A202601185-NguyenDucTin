#!/usr/bin/env python3
"""Great Expectations validation with Suite / ValidationDefinition / Checkpoint.

Builds a reusable Expectation Suite from the orders contract, creates a
ValidationDefinition, and runs validation.

Usage:
    python gx/validate_orders.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure HOME is set BEFORE any imports (altair needs it at import time)
if "HOME" not in os.environ:
    home = os.environ.get("USERPROFILE")
    if home:
        os.environ["HOME"] = home
    else:
        os.environ["HOME"] = "C:\\Users\\Admin"

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import great_expectations as gx
    from great_expectations.expectations import (
        ExpectColumnValuesToNotBeNull,
        ExpectColumnValuesToBeUnique,
        ExpectColumnValuesToBeBetween,
        ExpectColumnValuesToBeInSet,
    )
except ImportError as exc:
    raise SystemExit("great_expectations is not installed. Run: pip install -r requirements.txt") from exc


def _severity_label(severity) -> str:
    """Convert GX severity enum to string label."""
    if severity is None:
        return "unknown"
    return str(severity).split(".")[-1].lower()


def main() -> None:
    df = pd.read_csv(ROOT / "data" / "incoming" / "orders.csv")
    context = gx.get_context()

    # ── Suite ──
    suite_name = "orders_suite"
    try:
        suite = context.suites.add(gx.ExpectationSuite(name=suite_name))
    except Exception:
        suite = context.suites.get(suite_name)

    expectations = [
        ExpectColumnValuesToNotBeNull(column="order_id", severity="critical"),
        ExpectColumnValuesToBeUnique(column="order_id", severity="critical"),
        ExpectColumnValuesToNotBeNull(column="customer_id", severity="critical"),
        ExpectColumnValuesToNotBeNull(column="amount", severity="critical"),
        ExpectColumnValuesToBeBetween(column="amount", min_value=0, severity="critical"),
        ExpectColumnValuesToBeInSet(column="currency", value_set=["USD", "VND"], severity="critical"),
        ExpectColumnValuesToBeInSet(
            column="status",
            value_set=["pending", "completed", "refunded", "cancelled"],
            severity="warning",
        ),
        ExpectColumnValuesToNotBeNull(column="created_at", severity="critical"),
        ExpectColumnValuesToNotBeNull(column="updated_at", severity="critical"),
    ]
    for exp in expectations:
        try:
            suite.add_expectation(exp)
        except Exception:
            pass  # already exists

    # ── Data Source & Asset ──
    try:
        data_source = context.data_sources.add_pandas("orders_pandas")
    except Exception:
        data_source = context.data_sources.get("orders_pandas")
    try:
        asset = data_source.add_dataframe_asset(name="orders_dataframe")
    except Exception:
        asset = data_source.get_asset("orders_dataframe")

    # ── Batch Definition ──
    try:
        batch_definition = asset.add_batch_definition_whole_dataframe("whole_orders")
    except Exception:
        batch_definition = asset.get_batch_definition("whole_orders")

    # ── Validation Definition ──
    vd_name = "orders_validation"
    try:
        validation = context.validation_definitions.add(
            gx.ValidationDefinition(
                name=vd_name,
                data=batch_definition,
                suite=suite,
            )
        )
    except Exception:
        validation = context.validation_definitions.get(vd_name)

    # ── Run validation via batch ──
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    print("=== GX VALIDATION RESULTS ===")
    all_ok = True
    for expectation in expectations:
        result = batch.validate(expectation)
        success = result.success
        all_ok = all_ok and bool(success) if success is not None else all_ok
        severity = _severity_label(getattr(expectation, "severity", None))
        print(f"{expectation.expectation_type:<50} success={success}  severity={severity}")

    print(f"\nOverall: {'PASS' if all_ok else 'FAIL'}")
    print(f"Suite         : {suite.name}")
    print(f"Validation    : {validation.name}")


if __name__ == "__main__":
    main()
