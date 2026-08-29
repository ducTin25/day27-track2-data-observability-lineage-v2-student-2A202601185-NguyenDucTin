#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INCOMING = ROOT / "data" / "incoming"


def duplicate_pk() -> None:
    path = INCOMING / "orders.csv"
    df = pd.read_csv(path)
    df = pd.concat([df, df.iloc[:3]], ignore_index=True)
    df.to_csv(path, index=False)
    print("Injected duplicate order_id rows.")


def volume_drop() -> None:
    path = INCOMING / "orders.csv"
    df = pd.read_csv(path)
    keep = max(10, int(len(df) * 0.25))
    df.iloc[:keep].to_csv(path, index=False)
    print(f"Injected partial-ingestion fault: kept {keep}/{len(df)} rows.")


def stale_kb() -> None:
    path = INCOMING / "kb_documents.jsonl"
    docs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for doc in docs:
        ts = pd.to_datetime(doc["published_at"], utc=True)
        doc["published_at"] = (ts - timedelta(hours=3)).isoformat()
    with open(path, "w", encoding="utf-8") as f:
        for row in docs:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print("Injected stale knowledge-base publish timestamps (-3h).")


SCENARIOS = {
    "duplicate_pk": duplicate_pk,
    "volume_drop": volume_drop,
    "stale_kb": stale_kb,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inject a public practice fault.")
    parser.add_argument("scenario", choices=sorted(SCENARIOS))
    args = parser.parse_args()
    SCENARIOS[args.scenario]()
