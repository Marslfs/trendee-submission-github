# 数据质量报告（dq_report）

> 数据源：`样例销售数据.xlsx`（300 行，2024-01~03）
> 报告由 `src/ingest.py` 的 `run_dq_checks()` 在每次摄取时自动生成，落 `dq_report` 表（带 `ingest_batch` 批次号，可追溯历史）。
> 本文档为最新批次 `20261121T084326Z` 的快照。

## 摄取统计

| 指标 | 数值 | 说明 |
|---|---|---|
| 输入行数 | 300 | 原始记录 |
| 过滤重复 | 12 | 12 组完全重复（5 字段全同），`row_hash` 幂等键 anti-join 过滤 |
| 落库行数 | 288 | `dwd_fact_sales` |
| 预聚合行数 | 111 | `dws_sales_daily`（日期 × 平台 × tag） |
| 商品打标 | core 12 / gray_zone 1 / excluded 17 | 按商品维度（30 个去重商品） |

**幂等验证**：同源重跑 `inserted=0`，事实表行数保持 288 不变（`row_hash` 主键 + 插入前 anti-join）。

## 5 条质量规则（最新批次结果）

| 检查项 | 级别 | 结果 | 详情 |
|---|---|---|---|
| `uniqueness_row_hash` | error | ✅ 通过 | 288 行 / 288 个 distinct hash，主键级唯一 |
| `completeness_not_null` | error | ✅ 通过 | 核心字段（product_id/platform/sales_count/dt_utc）无空值 |
| `tag_glossary_consistency` | error | ✅ 通过 | DWS 聚合表无非法 tag_status（excluded 不进汇总） |
| `anomaly_sales_range` | warn | ✅ 通过 | sales_count ∈ [1, 18]，无 ≤0 或 >10000 异常值 |
| `timeliness_coverage` | info | ✅ 通过 | dt_utc 覆盖 2024-01-01 07:00 → 2024-03-13 09:45；输入重复过滤 12 条 |

## 关键口径说明（面试必答）

### 1. 重复数据：删，但留痕

- 12 组完全重复（product_id/title/sales_count/timestamp/user_id/source 五字段全同）判定为**采集重复**，按 `row_hash` 去重
- 「为什么销量少 12 条」可回答：`dq_report.timeliness_coverage.detail` 里记录了 `input duplicates filtered = 12`，且源 xlsx 原样保留在 `data_raw/`，可复算
- 幂等：重跑不会二次入库，也不会丢数据

### 2. 时区口径：双列保留，聚合用 dt_local

- 源 `timestamp` 声明为 **UTC**；业务口径统一为 **Asia/Shanghai（+8h，无夏令时）**
- 300 条原始记录中 **132 条** UTC ≥ 16:00，+8h 后落到次日（如 `01-01 16:33 UTC` 的销量计入本地 `01-02`）；去重后事实表中跨天记录为 **126 条**
- `dwd_fact_sales` 同时保留 `dt_utc` / `dt_local` 双列（均为 naive TIMESTAMP，墙钟各按本时区），**聚合一律用 `dt_local`**——不声明口径的话趋势图会整体右移一天
- 已知坑：DuckDB Python binding 会把 aware datetime 按会话时区换算后剥 tz 存储，双列若直接绑定 aware 值会坍缩成同一时间——`build_rows` 已在入库前显式剥 tz 规避

### 3. 异常值：本题藏在时间和重复里

`sales_count` 本身干净（1–18 整数，无缺失/负数/离群），题目所称"异常记录"实际由**重复行**与**跨天时间边界**两处构成，分别由幂等去重和时区口径处理。

### 4. 覆盖度提醒

3 月数据只到 13 日（46 条），月度趋势图需注明"3 月不完整"，避免误读为下滑。
