# Task 1 性能说明：大数据量与高并发（实测 + EXPLAIN + 推演）

> **实测结论（先看这里）**：在线热路径只打 `dws_sales_daily`（**恒 111 行**）。
> 明细从 288 行放大到 **300 万行（×10416）**，DWS 直查 P50 仍在 **1.4~2.3 ms** 区间不动；
> 而明细 `GROUP BY` 从 1.7 ms 涨到 **8.2 ms**、前缀过滤明细扫描涨到 6.5 ms。
> `EXPLAIN ANALYZE` 直接给出原因：明细路径 `Table Scan 2,999,808 rows / Total Time 0.0079s`，
> DWS 路径 `Table Scan 111 rows / Total Time 0.0018s`。
> **结论：数据量增长打在离线聚合层，在线延迟与明细量解耦。** 全部数字由 `scripts/bench.py` 一条命令复跑，
> 原始输出见 `docs/bench_result.md`。

## 1. 实测：288 / 30 万 / 300 万行 × 明细 vs 预聚合

复跑命令（< 2 分钟，不联网、不改交付库）：

```bash
cd task1_data_api && python scripts/bench.py
```

脚本把现有 `dwd_fact_sales` 交叉放大到 30 万 / 300 万行，写在系统临时目录的临时库里
（**不污染 `data/sales.duckdb`**），每组查询 warmup 1 次后计时 20 次取 P50 / P95。

| 明细行数 | DWS 行数 | 明细 GROUP BY P50 / P95 (ms) | DWS 直查 P50 / P95 (ms) | 前缀过滤明细 P50 / P95 (ms) |
|---|---|---|---|---|
| 288 | 111 | 1.72 / 2.31 | 1.50 / 2.45 | 1.82 / 2.45 |
| 299,808 | 111 | 3.65 / 4.38 | 1.42 / 2.07 | 4.43 / 4.88 |
| 2,999,808 | 111 | **8.22 / 10.86** | **1.98 / 2.28** | 6.49 / 7.18 |

（`bench.py` 每次重跑会有 ±1 ms 抖动；完整输出以 `docs/bench_result.md` 为准，结论不受影响。）

### EXPLAIN ANALYZE 片段（300 万行档）

```text
# 明细 GROUP BY
Summary
Total Time: 0.0079s
Perfect Hash Group By          72 rows        50.0ms
2,999,808 rows                0µs
Table Scan                   2,999,808 rows

# DWS 直查
Summary
Total Time: 0.0018s
Perfect Hash Group By          67 rows         0µs
111 rows                       0µs
Table Scan                   111 rows
```

扫描行数差 **2.7 万倍**，这就是「在线只打 DWS」的全部依据，而不是一句口头推演。

### 回答面试题「数据到 1 亿行、QPS 到 2000 时第一处崩在哪」

1. **第一处崩的不是 DWS 查询**：DWS 行数 = 天数 × 平台 × 档位，1 亿行明细下仍是千级行数，
   单次 ~2 ms。**真正先崩的是「任何回退到明细的在线路径」**——300 万行明细聚合已 8 ms，
   1 亿行按线性外推约 200~300 ms/次，QPS 2000 在单实例上需要数百核，直接打爆。
2. **第二处是缓存击穿 + 单实例进程内缓存**：`cachetools TTLCache` 是进程内 1024 条目 / TTL 60s，
   多 worker 各自一份，命中率随实例数下降；QPS 2000 且 key 分散时大量请求穿透到 DB。
   换 Redis 共享缓存（`trend:{start}:{end}:{platforms}:{gray}`）只改 `cache.py`，接口不动。
3. **第三处是写路径**：DuckDB 单文件单写连接，摄取/回填是离线批任务，与在线读隔离；
   1 亿行时这一侧要迁 ClickHouse（`ORDER BY (platform, dt_local)` + 按月分区）并改增量 upsert。

**生产化顺序**：Redis 共享缓存 → 无状态多 worker + 负载均衡 → 明细侧迁 ClickHouse 分区 → DWS 改物化视图增量刷新。
每一步都不改 API 语义，改的是实现与 DDL。

## 2. 数据量分级推演（实测之上的外推）

| 数据量 | 存储形态 | 查询路径 | 瓶颈判断 |
|---|---|---|---|
| ≤ 10 万行 | 单文件 DuckDB | DWS 直查（明细扫描也够） | 无 |
| 10 万 ~ 5000 万行 | 保留预聚合表；明细加分区 | API 只打 `dws_sales_daily` | 在线路径不变，靠**聚合表与明细表解耦** |
| > 5000 万行 / 1 亿行 | 迁 ClickHouse | 排序键 + 按月分区 + 物化视图 | 迁移只改 DDL，SQL 方言几乎不动 |

`dws_sales_daily` 的行数由时间跨度决定（3 年 ≈ 1.5 万行），与原始销量行数无关。

## 3. 高并发推演（读多写少，QPS 100 → 10000）

1. **缓存（已实现）**：cachetools TTLCache（1024 条目 / TTL 60s），key = 参数排序后 md5（含 `fill_missing_dates` 等新参数）。命中直接返回，不打 DB。
2. **生产换 Redis（key 设计不变）**：多 worker 共享缓存；TTL 60s 内的趋势查询不穿透。⚠️ 明确取舍：缓存以 60s 数据新鲜度换吞吐，日粒度趋势完全可接受。
3. **无状态水平扩展**：API 进程不持有状态（缓存可外置），uvicorn workers × N + Nginx/LB 线性扩；DuckDB `read_only=True` 支持多读连接。
4. **写路径隔离**：摄取与聚合是离线批任务（可日调度），与在线查询物理隔离——并发压力不会传导到写侧。

## 4. 冷热数据与分区

- 热数据（最近 90 天）与冷数据分区存放：ClickHouse 按月分区天然支持；查询带日期谓词时分区裁剪避免扫冷分区。
- 冷数据归档：按月导出 Parquet，需要时 DuckDB 可直接 `read_parquet` 查询——不需要回灌数据库。

## 5. 明确不做的（取舍）

- **不引入 Redis / ES / ClickHouse 到 demo**：本机演示无这些依赖；但 schema / 接口按其生产形态设计，迁移是改 DDL 而非重写。
- **不做实时聚合**：日趋势业务下，T+1 预聚合 + 60s 缓存足够；"实时"需求出现时再上流式。
- **不在 288 行上做 QPS 压测**：那个量级上的 QPS/P95 数字没有容量规划意义，所以本文件改为「放大到 300 万行 + EXPLAIN ANALYZE」给出可外推的实测。¹

---
¹ 288 行上压测没意义，是脚本里仍保留 288 行这一个对照档的原因；真正用于结论的是 30 万 / 300 万行两档。
