# Public Rubric

Tổng: **100 điểm + tối đa 15 bonus**.

| Hạng mục | Điểm |
|---|---:|
| Baseline & system understanding | 5 |
| Data contract / deterministic validation | 10 |
| Great Expectations hoặc equivalent validation flow | 10 |
| dbt data tests + transformation correctness | 10 |
| Anomaly detection | 15 |
| Lineage + blast radius | 15 |
| SLI/SLO/error budget | 10 |
| Mystery incident RCA | 15 |
| Incident report | 5 |
| Giải thích/defend solution | 5 |

## Bonus gợi ý

- MAD/same-weekday anomaly: +3
- dbt native unit test: +3
- GX severity/actions: +3
- automatic quarantine: +3
- Soda Data Contract: +5
- Elementary OSS: +5
- OpenLineage dataset lineage: +5
- column lineage: +7
- multi-window burn-rate: +7
- RAG embedding/token drift: +7

Bonus chỉ tính nếu có evidence kỹ thuật cho thấy giải pháp bắt được failure mà baseline không bắt được.
