# 笔试题要求 → 实现对照表（Task 1）

> 对照《万悉科技笔试题》"一、数据工程"的 7 条任务 + 5 项交付物，逐条给出实现位置与验证方式。

## A. 任务 7 条

| # | 题目原文要求 | 实现位置 | 怎么验证（1 分钟） |
|---|---|---|---|
| 1 | 返回 "maxi dress" 日销量趋势，支持 start_date / end_date / 一个或多个平台 | `src/api.py` → `GET /api/v1/sales/trend`；查询打 `agg_sales_daily` | Swagger 里填 `start_date=2024-01-01`、`end_date=2024-03-13`、`platforms=website,app` → Execute，返回按日 + `by_platform` |
| 2 | 自行定义并说明 maxi dress 识别/归一化规则；原始 category 只是 dress 等粗粒度 | `src/normalize.py`（三段式，Python 版为准）<br>`sql/02_tag.sql`（SQL 版，交叉验证）<br>`docs/design.md` §3（规则说明） | `GET /api/v1/products?tag=core` 看 12 个商品；`?tag=excluded` 里能看到 `maxi skirt` 被排除的原因 |
| 3 | 自选存储并设计 schema / mapping / 索引结构 | `sql/01_schema.sql`（3 维表 + fact + agg + dq_report）<br>`docs/design.md` §2（设计意图与生产迁移路径） | 打开 `sql/01_schema.sql` 看注释；或 `python -c "..."` 查 `DESCRIBE` |
| 4 | 提供核心 SQL，结果至少支持按日期、平台分组统计 | `sql/queries.sql` Q1（按日）、Q2（日期×平台）、Q3（区间汇总）、Q4（商品榜） | 4 条都能直接跑（已验证：Q1 34 行 / Q2 100 行 / Q3 3 行 / Q4 10 行） |
| 5 | 设计 RESTful API：路径、参数、典型返回结构、必要错误处理 | `src/api.py`（3 路由）<br>`docs/design.md` §6（API 表 + 返回示例） | Swagger `/docs` 直接点；错误分支见本文 §C |
| 6 | 说明大数据量与高并发优化及取舍（索引/预聚合/缓存/分区/冷热） | `docs/perf.md`（数据量分级推演 + 并发 5 层 + 明确不做什么） | 直接读，每一条都对应到代码/配置 |
| 7 | 说明重复数据、标题归一化、timestamp/时区、异常记录处理 | `src/ingest.py`（row_hash 幂等）<br>`src/timeutil.py`（UTC→CST 双列）<br>`src/ingest.py::run_dq_checks`（5 条规则）<br>`docs/design.md` §4 §5 §7 | 重跑两遍 ingest 看 `inserted: 0`；查 `dq_report` 表 |

## B. 交付物 5 项

| 交付物 | 文件 | 状态 |
|---|---|---|
| 系统/数据设计说明（可附架构图） | `docs/design.md`（含 Mermaid 架构图） | ✅ |
| schema / mapping | `sql/01_schema.sql` + design.md §2 | ✅ |
| 核心查询 | `sql/queries.sql`（4 条，全部实跑通过） | ✅ |
| API 示例 | `docs/design.md` §6 + Swagger `/docs` | ✅ |
| 性能与数据质量说明 | `docs/perf.md` + design.md §7 + `dq_report` 表 | ✅ |
| README | `task1_data_api/README.md` | ✅ |

## C. 错误处理对照（笔试题要求"必要的错误处理"）

| 场景 | 请求 | 期望响应 | 实际 |
|---|---|---|---|
| 日期倒序 | `start_date=2024-03-01&end_date=2024-01-01` | 400 | `{"detail":"start_date (2024-03-01) 晚于 end_date (2024-01-01)"}` ✅ |
| 未知平台 | `platforms=taobao` | 400 | `{"detail":"未知平台 ['taobao']，可选值：['app','marketplace','website']"}` ✅ |
| 缺必填参数 | 只传 `start_date` | 422 | FastAPI 自动校验（Swagger 里 422 段即此项） ✅ |
| 区间超 366 天 | 一年以上区间 | 400 | `{"detail":"日期范围超过 366 天上限"}` ✅ |
| 数据库未初始化 | 未跑 ingest 就请求 | 503 | 提示"请先执行 python -m src.ingest" ✅ |
| 结果为空 | 无数据区间 | 200 + `count:0` | 空是合法业务状态，不用 404 ✅ |

## D. 数据质量的 5 个"可讲点"（面试追问防线）

1. **重复 12 条**：完全重复（7 字段全同），用 `row_hash` 主键 + anti-join 过滤，而不是 DELETE；二次重跑 `inserted=0` 证明幂等。
2. **标题归一化**：`Women's Maxi-Dress Floral` → `women s maxi dress floral`（所有格、连字符、大小写都处理了）。
3. **maxi skirt ≠ maxi dress**：11 条 "Maxi Skirt"（product 2027）被排除——"含 maxi 但无 dress" 单独成一档规则。
4. **灰区**：`Elegant Long Dress` 11 条无 maxi 但够长——计入但打 `is_gray_zone`，API 用 `include_gray_zone` 开关，默认不计。
5. **时区**：源数据声明为 UTC；**132 条** UTC≥16:00 的记录转 +8h 后跨天（如 01-01 16:33 的 10 件销量落到本地 01-02）——所以聚合必须声明口径，`dt_utc`/`dt_local` 双列都保留。
