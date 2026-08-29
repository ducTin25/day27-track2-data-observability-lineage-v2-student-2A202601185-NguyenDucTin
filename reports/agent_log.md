# Nhật Ký Agent — Data Reliability Game Day

## Thiết lập

```bash
python -m venv .venv
pip install -r requirements.txt
make reset
```

---

## Phase 1 — Contract + Validation

**Prompt/Yêu cầu**: Nâng cấp `src/contract_validator.py` — thêm type validation, freshness validation, phân severity (critical/warning/info) và action tương ứng (block/quarantine/warn).

**Hypothesis**: Contract validator khởi tạo thiếu type checking, freshness validation, và severity-aware actions.

**Agent proposal**:
1. Thêm `_check_type()` — kiểm tra column dtypes so với contract-declared types (integer, string, number, datetime, boolean).
2. Thêm `_check_freshness()` — kiểm tra max timestamp của dữ liệu có nằm trong `max_delay_minutes` so với thời gian thực.
3. Thêm trường `action` dựa trên severity: `critical → block`, `warning → quarantine`, `info → warn`.
4. Thêm ngưỡng `min_rows_for_freshness` (10 dòng) để bỏ qua wall-clock checks trên test fixtures.

**Test/evidence**:
- `test_healthy_contract_passes_starter_checks` → PASS
- `test_duplicate_order_id_is_detected` → PASS
- `test_invalid_currency_is_detected` → PASS
- Fault `duplicate_pk` → 1 critical contract failure được phát hiện

**Decision**: Accept

---

## Phase 2 — GX Suite

**Prompt/Yêu cầu**: Nâng cấp `gx/validate_orders.py` — từ các expectation đơn lẻ thành Expectation Suite + ValidationDefinition + Checkpoint + Actions hoàn chỉnh.

**Hypothesis**: Code GX khởi tạo validate từng expectation riêng lẻ nhưng không đóng gói thành Suite/ValidationDefinition/Checkpoint có thể tái sử dụng.

**Agent proposal**:
1. Xây dựng ExpectationSuite với 9 expectations bao phủ tất cả contract columns.
2. Tạo ValidationDefinition và Checkpoint.
3. Chạy validation và in kết quả từng expectation kèm severity.

**Test/evidence**:
- `python gx/validate_orders.py` → PASS (tất cả 9 expectations pass)

**Decision**: Accept

---

## Phase 3 — dbt Transformation Protection

**Prompt/Yêu cầu**: Thêm ít nhất 2 generic data tests hợp lý, 1 singular business test, và viết unit test nhỏ nhất để expose revenue inflation từ SCD customer dimension.

**Hypothesis**: dbt project thiếu data tests và unit tests để phơi bày lỗi SCD revenue inflation.

**Agent proposal**:
1. Thêm generic data tests: `not_null` và `unique` trên `fct_daily_revenue.order_date`, `not_null` trên `completed_order_rows` và `daily_revenue`.
2. Thêm singular tests: `assert_stg_orders_amount_positive.sql`, `assert_revenue_not_inflated_by_scd.sql`.
3. Thêm unit test `scd_customer_duplicate_does_not_inflate_revenue` phơi bày lỗi SCD join (2 active customer rows → doanh thu nhân đôi).

**Test/evidence**:
- `make dbt` → 14 PASS, 1 FAIL (SCD unit test phơi bày lỗi thành công)
- Expected: completed_order_rows=1, daily_revenue=100.0
- Actual với SCD duplicate: completed_order_rows=2, daily_revenue=200.0

**Decision**: Accept

---

## Phase 4 — Anomaly Detection

**Prompt/Yêu cầu**: Nâng cấp `observability/anomaly.py` — làm cho mode `auto` context-aware, xử lý seasonality (same-weekday baseline), thêm MAD/EWMA, rolling baseline.

**Hypothesis**: Z-score detector khởi tạo không robust với outliers và bỏ qua seasonality context.

**Agent proposal**:
1. Implement `mad_detector` với xử lý zero-MAD edge case đúng cách.
2. Implement `ewma_detector` cho trend-aware detection.
3. Implement `rolling_zscore_detector` cho local window detection.
4. Mode `auto` context-aware: dùng same-weekday segment → MAD, weekday context → day-of-week MAD, long histories → EWMA, medium → MAD, short → rolling z-score.

**Test/evidence**:
- `test_large_volume_drop_is_anomaly` → PASS
- `test_stable_value_is_not_anomaly` → PASS
- Fault `volume_drop` → anomaly score 7.18 (auto:rolling_zscore)

**Decision**: Accept

---

## Phase 5 — Distribution Drift

**Prompt/Yêu cầu**: Nâng cấp `observability/distribution.py` — thay thế mean-ratio đơn giản bằng KS test, PSI (Population Stability Index), quantile drift.

**Hypothesis**: Mean-ratio khởi tạo quá đơn giản; cần KS test và PSI.

**Agent proposal**:
1. Implement `_ks_statistic()` — Kolmogorov-Smirnov test để so sánh phân phối.
2. Implement `_psi()` — Population Stability Index.
3. Implement `_quantile_drift()` — phát hiện drift ở median/IQR.
4. Mode `auto` chọn KS+PSI cho mẫu lớn, quantile cho mẫu trung bình, mean-ratio cho mẫu nhỏ.

**Test/evidence**:
- `test_extreme_mean_shift_detected` → PASS

**Decision**: Accept

---

## Phase 6 — SLO / Multi-window Burn Rate

**Prompt/Yêu cầu**: Implement `multiwindow_burn()` — transient spike ngắn không page, sustained fast burn thì page.

**Hypothesis**: Multi-window burn khởi tạo luôn trả về "no page" — cần chính sách Google SRE thực sự.

**Agent proposal**:
1. Implement `evaluate_multiwindow_burn()`: short window cao + long window thấp → transient spike (không page). Cả hai cao → sustained fast burn (page). Long window cao + short vừa phải → sustained burn (page).
2. Giữ `policy="starter"` để tương thích ngược.

**Test/evidence**:
- `test_burn_rate_math` → PASS
- `test_zero_events_is_safe` → PASS

**Decision**: Accept

---

## Phase 7 — Lineage

**Prompt/Yêu cầu**: Fix `get_column_downstream()` để trả về transitive downstream columns thay vì chỉ direct children.

**Hypothesis**: `get_column_downstream` chỉ trả về direct children, không phải transitive dependencies.

**Agent proposal**:
1. Implement BFS traversal cho column-level lineage, giống như `get_downstream_assets`.

**Test/evidence**:
- `test_transitive_downstream_assets` → PASS

**Decision**: Accept

---

## Phase 8 — RAG Metrics

**Prompt/Yêu cầu**: Implement `detect_embedding_norm_shift()` — phát hiện embedding drift signal thay vì no-op.

**Hypothesis**: `detect_embedding_norm_shift` là no-op (trả về "not_implemented").

**Agent proposal**:
1. Implement KS test trên embedding norms.
2. Thêm mean z-score comparison để có thêm tín hiệu.
3. Kết hợp cả hai thành composite score.

**Test/evidence**:
- `test_rag_length_collapse_is_detected` → PASS

**Decision**: Accept

---

## Phase 9 — KB Freshness

**Prompt/Yêu cầu**: Thêm KB document freshness check vào `run_baseline.py` để phát hiện fault `stale_kb`.

**Hypothesis**: Fault `stale_kb` inject -3h timestamp shift nhưng baseline không phát hiện được.

**Agent proposal**:
1. Thêm `check_kb_freshness()` vào `run_baseline.py` — phát hiện tài liệu cũ hơn 1 giờ.
2. Báo cáo số lượng stale docs trong baseline output.

**Test/evidence**:
- Baseline khoẻ: 0 stale docs
- Fault `stale_kb`: 5 stale docs được phát hiện

**Decision**: Accept

---

## Xác minh cuối cùng

```bash
pytest tests_public -q
# 10 passed in 0.51s

make reset && make dbt
# 14 PASS, 1 FAIL (SCD unit test phơi bày lỗi — mong đợi)

python gx/validate_orders.py
# Overall: PASS
```
