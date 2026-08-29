# Lab Guide — Data Reliability Game Day (120 phút)

## Mục tiêu

Sau 2 giờ, nhóm cần có khả năng:

1. Chuyển business assumptions thành data contract/rules.
2. Phân biệt data tests và transformation logic tests.
3. Bắt một anomaly chưa có rule viết trước.
4. Trace blast radius bằng lineage.
5. Tính SLO/error budget/burn rate.
6. Điều tra incident bằng evidence thay vì đoán.

---

## Phase 0 — Healthy baseline (0–10')

```bash
make reset
make baseline
pytest tests_public -q
```

Trả lời ngắn:
- Dataset nào critical?
- Downstream consumer nào?
- Metric nào cho biết data không đáng tin?

---

## Phase 1 — Contract + Validation (10–30')

Mở:
- `contracts/orders_contract.yaml`
- `src/contract_validator.py`
- `gx/validate_orders.py`

Starter validator đã có not-null/unique/accepted/range cơ bản.

### Bắt buộc

- Thêm type validation.
- Thêm freshness validation.
- Phân severity: `critical`, `warning`, `info`.
- Xác định action: block / quarantine / warn.
- Chạy public fault `duplicate_pk`.

### Advanced

- Build GX Expectation Suite + ValidationDefinition + Checkpoint.
- Hoặc replace custom contract verification bằng Soda Core và giữ stable API.

---

## Phase 2 — dbt transformation protection (30–50')

```bash
make reset
make dbt
```

Đọc `fct_daily_revenue.sql`.

### Bắt buộc

- Thêm ít nhất 2 generic data tests hợp lý.
- Thêm 1 singular business test.
- Giải thích vì sao `not_null/unique` không phải dbt unit test.

### Strong challenge

Customer dimension có thể có nhiều active version. Viết unit test nhỏ nhất để expose revenue inflation.

Starter có `unit_tests.yml.example` làm gợi ý, không phải đáp án hoàn chỉnh.

---

## Phase 3 — Anomaly detection (50–70')

```bash
make reset
python scripts/inject_fault.py volume_drop
make baseline
```

### Bắt buộc

- Z-score hoặc baseline đơn giản bắt được volume drop.
- Giải thích khi nào Z-score sai.

### Strong challenge

Nâng cấp `method="auto"` để xử lý seasonality/outlier:
- same-weekday baseline,
- median/MAD,
- rolling baseline,
- EWMA,
- hoặc phương pháp khác có lý do rõ ràng.

Không cần ML phức tạp nếu statistical baseline đã giải quyết đúng bài toán.

---

## Phase 4 — Lineage & Blast Radius (70–85')

Starter graph: `data/baseline/lineage_graph.json`.

### Bắt buộc

Trả lời bằng code:

```text
stg_orders bị lỗi -> assets nào bị ảnh hưởng?
```

### Advanced

- Parse `dbt_project/target/manifest.json` sau `dbt build`.
- Implement column-level transitive lineage.
- Optional: emit OpenLineage events/visualize Marquez.

---

## Phase 5 — SLO/Error Budget (85–100')

`observability/slo.py` đã có normalized burn-rate math cơ bản.

### Bắt buộc

Cho SLO = 99.5%, 2 bad checks/100 checks:
- actual bad rate?
- allowed bad rate?
- burn rate?
- breach?

### Advanced

Implement `multiwindow_burn()`:
- transient spike ngắn -> không page,
- sustained fast burn -> page.

---

## Phase 6 — Mystery incident (100–115')

Giảng viên sẽ đưa incoming dataset khác hoặc fault folder riêng.

**Không được xem script tạo fault.**

Chỉ dùng evidence từ:
- contracts/validation,
- dbt tests,
- anomaly metrics,
- lineage,
- SLO,
- raw-data exploration có lý do.

Trả lời:
1. What happened?
2. When did it start?
3. Root cause?
4. Blast radius?
5. Mitigation?
6. Recovery verification?
7. Prevention?

---

## Phase 7 — Report (115–120')

Hoàn thiện:
- `reports/incident_report.md`
- `reports/agent_log.md`

---

# Ba public practice faults

## 1. Duplicate key

```bash
make reset
python scripts/inject_fault.py duplicate_pk
make baseline
```

Kỳ vọng: deterministic contract/test nên bắt được.

## 2. Volume drop

```bash
make reset
python scripts/inject_fault.py volume_drop
make baseline
```

Kỳ vọng: anomaly detector nên bắt được dù không có rule `row_count == ...`.

## 3. Stale KB

```bash
make reset
python scripts/inject_fault.py stale_kb
make baseline
```

Starter baseline hiện chưa hoàn thiện KB freshness/SLO. Đây là một TODO có chủ đích.

---

# Câu hỏi vận hành cần luôn tự hỏi

Không chỉ hỏi:

> “Tool có fail không?”

Hãy hỏi:

- Failure này impact user nào?
- Block pipeline hay warning?
- Alert này có actionable không?
- False positive nào dễ xảy ra?
- Nếu detector này không có, layer nào còn lại có bắt được không?
