-- ============================================================
-- 04_queries.sql — 应用查询（DWS 直查，不建 ADS）
--
-- 【分层说明】本项目只有一个消费方（trend API），过滤条件均为通用筛选
-- （tag_status / 日期区间 / 平台），因此跳过 ADS 层，直接查 dws_sales_daily。
-- ADS 的触发条件：出现第二个消费方且口径分叉，或 QPS 高到需要按接口预物化。
-- Q4 例外：商品榜需要 title_norm 明细字段，DWS 无此维度，回查 DWD（已在注释说明理由）。
--
-- 口径说明：
--   * 聚合一律用 dt_local（Asia/Shanghai），UTC→本地跨天的记录归属会变，已在设计文档声明
--   * gray_zone（long dress）默认不计入主趋势，按 include_gray_zone 参数可选计入
--   * 日期过滤用 [start, end] 闭区间，作用于 dt_local::DATE
-- ============================================================

-- Q1 ｜日销量趋势：maxi dress（core）主口径 + gray_zone 对照列，按日分组
--    → API /api/v1/sales/trend 的主查询（读 DWS）
--    gray_zone 不进主口径，只作为对照列暴露：WHERE 同时纳入 core 与 gray_zone，
--    一次扫描里 total_sales / records 只累加 core，gray_zone_sales 累加 gray_zone。
--    （旧版 WHERE 只留 core 又 CASE gray_zone，那一列恒为 0，是一列假指标。）
SELECT
    a.dt_local                                   AS dt_local,
    SUM(CASE WHEN a.tag_status = 'core'
             THEN a.total_sales ELSE 0 END)        AS total_sales,
    SUM(CASE WHEN a.tag_status = 'core'
             THEN a.record_count ELSE 0 END)       AS records,
    SUM(CASE WHEN a.tag_status = 'gray_zone'
             THEN a.total_sales ELSE 0 END)        AS gray_zone_sales
FROM dws_sales_daily a
WHERE a.tag_status IN ('core', 'gray_zone')
  AND a.dt_local BETWEEN DATE '2024-01-01' AND DATE '2024-03-13'
  -- 可选平台过滤（如需）：AND a.platform IN ('website')
  -- 默认全平台：gray_zone 只在 app 平台出现，加 website 会让对照列重新变成 0
GROUP BY 1
ORDER BY 1;

-- Q2 ｜同一趋势，但平台拆分（前端画多系列折线用）—— 读 DWS
SELECT
    a.dt_local,
    a.platform,
    SUM(a.total_sales) AS total_sales
FROM dws_sales_daily a
WHERE a.tag_status = 'core'
  AND a.dt_local BETWEEN DATE '2024-01-01' AND DATE '2024-03-13'
GROUP BY 1, 2
ORDER BY 1, 2;

-- Q3 ｜日期范围 × 平台 汇总（不给日粒度，仅看区间总量）—— 读 DWS
SELECT
    a.platform,
    SUM(a.total_sales)   AS total_sales,
    SUM(a.record_count)  AS records,
    ROUND(SUM(a.total_sales) / SUM(a.record_count), 2) AS avg_per_record
FROM dws_sales_daily a
WHERE a.tag_status = 'core'
  AND a.dt_local BETWEEN DATE '2024-01-01' AND DATE '2024-03-13'
GROUP BY 1
ORDER BY total_sales DESC;

-- Q4 ｜区间内 maxi dress 商品榜
--    【为何回查 DWD】榜单需要 product_id + title_norm 的明细粒度，DWS 只到
--    (日期 × 平台 × 标签) 粒度、不含商品维度；榜单只有 12 个商品、扫描量极小，
--    回查 dwd_fact_sales 的代价远低于为此再建一张 ADS 商品粒度汇总表。
SELECT
    p.product_id,
    p.title_norm,
    SUM(f.sales_count)  AS total_sales,
    COUNT(*)            AS records
FROM dwd_fact_sales f
JOIN dim_product p USING (product_id)
WHERE p.tag_status = 'core'
  AND CAST(f.dt_local AS DATE) BETWEEN DATE '2024-01-01' AND DATE '2024-03-13'
GROUP BY 1, 2
ORDER BY total_sales DESC
LIMIT 10;

-- Q5 ｜日/周环比（MoM/WoW）：7 日滚动合计 + 日环比，全部用窗口函数
--    【为什么用窗口函数而不是自关联】自关联要对每个日期再扫一次明细（N 次扫描、O(N^2)），
--    LAG() 与 SUM() OVER (ORDER BY ... ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
--    在单次有序扫描里同时算出「前一日值 / 日环比 / 7 日滚动」，扫描次数恒为 1。
--    这也是笔试题「查询优化 / 深入使用数据库」的落点：窗口函数是数据库能力，不是应用层循环。
WITH daily AS (
    SELECT a.dt_local,
           SUM(a.total_sales) AS total_sales
    FROM dws_sales_daily a
    WHERE a.tag_status = 'core'
      AND a.dt_local BETWEEN DATE '2024-01-01' AND DATE '2024-03-13'
    GROUP BY 1
),
lagged AS (
    SELECT dt_local, total_sales,
           LAG(total_sales, 1) OVER (ORDER BY dt_local) AS prev_day_sales
    FROM daily
)
SELECT
    dt_local,
    total_sales,
    prev_day_sales,
    ROUND(100.0 * (total_sales - prev_day_sales) / NULLIF(prev_day_sales, 0), 1) AS dod_pct,
    SUM(total_sales) OVER (ORDER BY dt_local ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS rolling_7d
FROM lagged
ORDER BY 1;
