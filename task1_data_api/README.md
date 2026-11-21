# Task 1：销售数据查询与 API（DuckDB + FastAPI）

maxi dress 日销量趋势查询服务。数仓分 **DIM / DWD / DWS 三层（刻意不建 ADS）**，关系图与分层理由见 `docs/design.md` §1；大数据量/高并发推演见 `docs/perf.md`。

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
| maxi dress 怎么识别？ | title 归一化后词级三段式：core=maxi∧dress∧¬mini∧¬midi；maxi skirt 类排除；long dress 打灰区标记可开关（`sql/02_dwd_tag.sql` 产出 `dim_product`） |
| 重复数据怎么办？ | row_hash 幂等键，摄取前 anti-join；300→288（12 条重复留痕于 dq_report） |
| 时区？ | 源数据声明为 UTC，dt_local=Asia/Shanghai(+8h)；132 条跨天记录归属随口径变化，聚合一律用 dt_local |
| 数仓分层？ | DIM（dim_* 维表）/ DWD（dwd_fact_sales 明细）/ DWS（dws_sales_daily 通用汇总）；不建 ADS，理由见 design.md §1.3 |
| 数据到 1 亿行？ | 在线只打 DWS 表（行数与明细量无关）；排序键/分区迁移 ClickHouse 只改 DDL |
| 高并发？ | TTL 缓存（key 设计不变可换 Redis）+ 无状态水平扩 + 读写路径隔离 |

## 目录

```
sql/       01_dwd_schema（DDL）· 02_dwd_tag（ODS→DIM 打标）
           03_dws_agg（DWD→DWS 汇总）· 04_queries（4 条核心查询）
src/       normalize · timeutil · ingest · dq_checks(并入ingest) · cache · api
tests/     pytest 17 用例（归一化/时区/API/缓存/错误分支）
data/      sales.duckdb（摄取产物，不入 git）
docs/      design.md（含分层关系图）· perf.md · checklist.md · dq_report.md（质量报告落盘）
           mapping.xlsx（字段映射 / 归一化规则 / 质量报告，三 Sheet）
           layering-er.svg（分层关系图矢量版：表为节点、SQL 为连线）
examples/  6 个真实响应快照（trend / gray-on / products / healthz / 400 / 422）
```

## 分层与表的对应

| 层 | 表 | 生产它的脚本 | 消费方 |
|---|---|---|---|
| DIM | `dim_product` / `dim_platform` / `dim_title_alias` | `02_dwd_tag.sql` + `src/ingest.py` | `/api/v1/products`、DWS 聚合 |
| DWD | `dwd_fact_sales` | `src/ingest.py` | Q4 商品榜、`/healthz`、质量检查 |
| DWS | `dws_sales_daily` | `03_dws_agg.sql` | `/api/v1/sales/trend`、Q1~Q3 |

## 实测数字

- 输入 300 行 → 过滤 12 条重复 → 落库 288 行；幂等重跑 inserted=0
- 商品打标：core 12 / gray_zone 1 / excluded 17（按商品维度）
- 预聚合 111 行（日期 × 平台 × tag）；API 全链路毫秒级
