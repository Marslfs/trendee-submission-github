# Task 1：销售数据查询与 API（DuckDB + FastAPI）

maxi dress 日销量趋势查询服务。设计细节见 `docs/design.md`，大数据量/高并发推演见 `docs/perf.md`。

## 快速开始

```bash
# 1) 摄取（xlsx → DuckDB，幂等可重跑）
python -m src.ingest

# 2) 启动 API
uvicorn src.api:app --reload
# 打开 http://127.0.0.1:8000/docs 即 Swagger UI

# 3) 查询示例
curl "http://127.0.0.1:8000/api/v1/sales/trend?start_date=2024-01-01&end_date=2024-01-31&platforms=website"

# 4) 测试（17 个用例）
python -m pytest tests/ -v
```

## 关键口径（面试必答）

| 问题 | 答案 |
|---|---|
| maxi dress 怎么识别？ | title 归一化后词级三段式：core=maxi∧dress∧¬mini∧¬midi；maxi skirt 类排除；long dress 打灰区标记可开关 |
| 重复数据怎么办？ | row_hash 幂等键，摄取前 anti-join；300→288（12 条重复留痕于 dq_report） |
| 时区？ | 源数据声明为 UTC，dt_local=Asia/Shanghai(+8h)；132 条跨天记录归属随口径变化，聚合一律用 dt_local |
| 数据到 1 亿行？ | 在线只打预聚合表（行数与明细量无关）；排序键/分区迁移 ClickHouse 只改 DDL |
| 高并发？ | TTL 缓存（key 设计不变可换 Redis）+ 无状态水平扩 + 读写路径隔离 |

## 目录

```
sql/       01_schema / 02_tag / 03_agg / queries（4 条核心查询）
src/       normalize · timeutil · ingest · dq_checks(并入ingest) · cache · api
tests/     pytest 17 用例（归一化/时区/API/缓存/错误分支）
data/      sales.duckdb（摄取产物，不入 git）
docs/      design.md · perf.md
```

## 实测数字

- 输入 300 行 → 过滤 12 条重复 → 落库 288 行；幂等重跑 inserted=0
- 商品打标：core 12 / gray_zone 1 / excluded 17（按商品维度）
- 预聚合 111 行（日期 × 平台 × tag）；API 全链路毫秒级
