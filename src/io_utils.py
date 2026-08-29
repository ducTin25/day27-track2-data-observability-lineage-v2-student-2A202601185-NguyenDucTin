from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]


def repo_path(*parts: str) -> Path:
    return ROOT.joinpath(*parts)


def load_yaml(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_orders(path: str | Path | None = None) -> pd.DataFrame:
    path = Path(path) if path else repo_path("data", "incoming", "orders.csv")
    return pd.read_csv(path)


def load_customers(path: str | Path | None = None) -> pd.DataFrame:
    path = Path(path) if path else repo_path("data", "incoming", "customers.csv")
    return pd.read_csv(path)


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def save_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
