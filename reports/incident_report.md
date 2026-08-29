# Báo Cáo Sự Cố — Data Reliability Game Day

## Tổng Quan

- **Mã sự cố**: INC-2026-08-29-001
- **Phát hiện lúc**: 2026-08-29
- **Báo cáo bởi**: Đội Data/AI Reliability
- **Mức độ nghiêm trọng**: Critical

---

## 1. Chuyện gì đã xảy ra?

CEO báo cáo doanh thu giảm trên dashboard trong khi pipeline của chúng ta báo `SUCCESS`. Đồng thời, Support Agent bị phát hiện đang áp dụng chính sách hoàn tiền cũ, dẫn đến số tiền hoàn lại không chính xác.

Ba lỗi riêng biệt đã được xác định:

| Lỗi | Phương pháp phát hiện | Tác động |
|-----|----------------------|----------|
| Trùng khoá chính trong `orders` | Contract validator (unique check) | Doanh thu bị inflate trong `fct_daily_revenue` |
| Sụt giảm khối lượng `orders` | Anomaly detector (z-score: 7.18) | Báo cáo doanh thu hàng ngày không đầy đủ |
| Tài liệu KB bị cũ | KB freshness check (5 tài liệu cũ) | Support Agent dùng chính sách lỗi thời |

---

## 2. Khi nào bắt đầu?

- **Duplicate PK**: Được inject sau khi baseline khoẻ được thiết lập.
- **Volume drop**: Được inject — 75% số dòng bị mất (150/600 dòng được nạp).
- **Stale KB**: Tài liệu knowledge-base có `published_at` bị lùi lại 3 giờ, vượt quá ngưỡng freshness.

---

## 3. Nguyên nhân gốc rễ

| Lỗi | Nguyên nhân |
|-----|-------------|
| **Duplicate PK** | Pipeline nạp dữ liệu cho phép `order_id` trùng lặp. Không có ràng buộc uniqueness tại nguồn. |
| **Volume drop** | Lỗi nạp dữ liệu một phần: chỉ 25% số dòng nguồn được tải. Không có monitoring row-count. |
| **Stale KB** | Quy trình cập nhật KB không làm mới tài liệu. Tài liệu cũ >1 giờ mà không có cảnh báo. |

**Vấn đề hệ thống tiềm ẩn:**
- Không có data contracts với type/freshness validation được enforce tại thời điểm ingest.
- dbt models thiếu test SCD-handling (dimension customer có thể inflate doanh thu).
- Không có multi-window SLO burn-rate alerting (sẽ phát hiện suy thoái kéo dài).
- Không có KB freshness SLO — tài liệu cũ được phục vụ cho Support Agent mà không ai biết.

---

## 4. Phạm vi ảnh hưởng (Blast radius)

Sử dụng dataset lineage graph:

```
stg_orders (lỗi) → fct_daily_revenue → ceo_revenue_dashboard
```

**Tài sản bị ảnh hưởng:**
- `fct_daily_revenue` — doanh thu bị inflate do join với duplicate PK
- `ceo_revenue_dashboard` — hiển thị số liệu doanh thu sai
- `kb_documents` → `kb_active_docs` → `rag_index` → `support_agent` — chính sách cũ được phục vụ cho khách hàng

**Người dùng hạ nguồn bị ảnh hưởng:**
- CEO dashboard (doanh thu sai)
- Support Agent / RAG system (chính sách hoàn tiền sai)
- Bộ phận tài chính (báo cáo doanh thu hàng ngày không chính xác)

---

## 5. Giảm thiểu (Mitigation)

| Lỗi | Giảm thiểu tức thì |
|-----|-------------------|
| Duplicate PK | Loại bỏ duplicates qua `DISTINCT` trên `order_id`; thêm unique constraint |
| Volume drop | Chạy lại ingestion với đầy đủ dữ liệu; thêm row-count alert |
| Stale KB | Force-refresh tài liệu KB; publish timestamps đã sửa |

**Các bản vá cấp pipeline đã được áp dụng:**
- Contract validator hiện kiểm tra: type compliance, uniqueness, freshness (wall-clock), và đề xuất action dựa trên severity (block/quarantine/warn).
- Anomaly detector được nâng cấp với EWMA, MAD, rolling z-score, và seasonal weekday-aware detection.
- dbt tests được thêm: singular tests cho revenue integrity, SCD inflation exposure qua unit test.
- KB freshness monitoring được thêm vào baseline.
- Multi-window SLO burn-rate policy được implement (phân biệt transient spike vs sustained burn).

---

## 6. Xác minh phục hồi

1. **Chạy `make reset`** — khôi phục dữ liệu baseline khoẻ.
2. **Chạy `make baseline`** — tất cả contract checks pass, 0 stale KB docs, anomaly score trong ngưỡng bình thường.
3. **Chạy `pytest tests_public -q`** — tất cả 10 public tests pass.
4. **Chạy `make dbt`** — tất cả dbt models build, data tests pass (SCD unit test cố tình fail để phơi bày lỗi revenue inflation cho mục đích tài liệu).
5. **Chạy `make gx`** — Great Expectations Suite validate tất cả columns, tất cả expectations pass.

---

## 7. Phòng ngừa

| Lĩnh vực | Đề xuất | Ưu tiên |
|----------|---------|---------|
| **Data Contracts** | Enforce contracts tại thời điểm ingestion với action `block` cho critical severity failures | P0 |
| **Freshness SLO** | Đặt SLO target (ví dụ 99.5%) cho data freshness; cảnh báo khi burn rate vượt ngưỡng | P0 |
| **dbt Tests** | Thêm SCD-handling unit tests cho tất cả dimension joins; thêm singular tests cho business logic | P1 |
| **Anomaly Detection** | Sử dụng seasonality-aware baselines (same-weekday, EWMA); cấu hình per-metric thresholds | P1 |
| **KB Freshness** | Monitor KB document publication lag; cảnh báo nếu bất kỳ tài liệu nào vượt quá 1 giờ | P1 |
| **Multi-window Burn** | Implement multi-window burn-rate alerting để phân biệt transient spikes với sustained degradation | P2 |
| **Lineage** | Sử dụng column-level lineage để phân tích blast radius chính xác; tích hợp OpenLineage | P2 |

---

## Timeline

| Thời gian | Sự kiện |
|-----------|---------|
| T+0 | Baseline khoẻ được thiết lập (600 orders, 0 contract failures) |
| T+1 | Duplicate PK được inject (603 rows, 3 duplicates) |
| T+2 | **Phát hiện**: Contract validator gắn cờ 1 critical failure |
| T+3 | Volume drop được inject (150 rows, mất 75%) |
| T+4 | **Phát hiện**: Anomaly detector gắn cờ volume drop (z-score 7.18) |
| T+5 | Stale KB được inject (5 docs, lùi 3 giờ) |
| T+6 | **Phát hiện**: KB freshness check gắn cờ 5 tài liệu cũ |
| T+7 | Cả ba lỗi được triage, giảm thiểu và xác minh |
