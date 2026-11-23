# Task1 性能实测（scripts/bench.py 自动生成）

> 源库 `data/sales.duckdb`（288 行明细）；放大库写在系统临时目录，不污染交付库。
> 每组查询 warmup 1 次后计时 20 次，单位 ms；EXPLAIN ANALYZE 取自 300 万行档。

| 明细行数 | DWS 行数 | 明细 GROUP BY P50 / P95 (ms) | DWS 直查 P50 / P95 (ms) | 前缀过滤明细 P50 / P95 (ms) |
|---|---|---|---|---|
| 288 | 111 | 1.72 / 2.31 | 1.50 / 2.45 | 1.82 / 2.45 |
| 299,808 | 111 | 3.65 / 4.38 | 1.42 / 2.07 | 4.43 / 4.88 |
| 2,999,808 | 111 | 8.22 / 10.86 | 1.98 / 2.28 | 6.49 / 7.18 |

## EXPLAIN ANALYZE 片段（300 万行）

**明细 GROUP BY**：
```text
Summary
Total Time: 0.0079s
72 rows                       0µs
72 rows                       0µs
72 rows                       0µs
Perfect Hash Group By
72 rows                    50.0ms
2,999,808 rows                0µs
Table Scan
2,999,808 rows                0µs
```

**DWS 直查**：
```text
Summary
Total Time: 0.0018s
67 rows                       0µs
67 rows                       0µs
67 rows                       0µs
Perfect Hash Group By
67 rows                       0µs
111 rows                      0µs
Table Scan
111 rows                      0µs
```
