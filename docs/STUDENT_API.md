# Stable Student API

Bộ hidden evaluation của giảng viên sẽ import `student_api.py`.

Bạn có thể refactor code bên trong, nhưng giữ các hàm sau và return shape cơ bản.

## 1. `validate_orders(df, contract_path)`

Return: list dictionary.

Mỗi item nên có dạng:

```python
{
  "check": "unique",
  "column": "order_id",
  "severity": "critical",
  "passed": False,
  "details": "..."
}
```

Hidden cases có thể kiểm tra: required/missing columns, null/unique/accepted/range, type drift, freshness và severity.

## 2. `detect_metric(current, history, method="auto", context=None)`

Return:

```python
{
  "is_anomaly": bool,
  "score": float,
  "method": str,
  "reason": str
}
```

`context` có thể chứa:

```python
{
  "metric_name": "row_count",
  "day_of_week": 5,
  "same_segment_history": [...],
  "known_event": None
}
```

`auto` là nơi phù hợp để bổ sung seasonality/robust baseline.

## 3. `detect_distribution(current_values, baseline_values)`

Return ít nhất `is_anomaly`, `score`, `method`, `reason`.

## 4. `slo_status(target, bad_events, total_events)`

Return ít nhất:

- `allowed_bad_rate`
- `actual_bad_rate`
- `burn_rate`
- `remaining_error_budget_fraction`
- `breached`

## 5. `multiwindow_burn(short_window_burn, long_window_burn)`

Return:

```python
{"page": bool, "severity": str, "reason": str, ...}
```

## 6. `downstream_assets(graph, start)`

Return list transitive downstream assets.

## 7. `column_downstream(graph, start)`

Return transitive downstream columns.

## 8. `rag_length_shift(current_texts, baseline_batch_means)`

Return anomaly dictionary.

## 9. `rag_embedding_shift(current_norms, baseline_norms)`

Return anomaly dictionary.

> Hidden tests không yêu cầu một tool cụ thể. Có thể dùng GX/Soda/Elementary/OpenLineage bên trong miễn interface và behavior đúng.
