# Dùng AI Coding Agent trong Lab

AI agent được phép. Mục tiêu của lab không phải code bằng tay nhanh hơn, mà là **thiết kế + verify reliability behavior**.

## Workflow đề nghị

```text
Student hypothesis
      ↓
AI proposal
      ↓
run test / experiment
      ↓
inspect evidence
      ↓
accept / reject / revise
```

## Prompt mẫu tốt

### Anomaly

> Implement a MAD-based detector for daily row count. Keep the current z-score function. Add tests for one true 70% drop and one legitimate Saturday pattern. Explain the false-positive trade-off.

### dbt

> Write the smallest dbt unit test that exposes revenue inflation when a customer dimension contains two active rows for the same customer. Do not modify the production model yet.

### Incident investigation

> Do not inspect the fault-injection script. Based only on contract results, dbt tests, anomaly metrics, lineage and SLO output, rank three root-cause hypotheses and list evidence for/against each.

### SLO

> Implement a multi-window burn-rate policy. Add one test for sustained fast burn and one for a short transient spike that should not page.

## Không nên làm

> “Build the whole lab for me.”

Nếu agent làm toàn bộ, bạn rất khó biết detector sai ở đâu khi hidden scenario thay đổi.

## Bắt buộc

Ghi khoảng 3–8 quyết định quan trọng vào `reports/agent_log.md`.
