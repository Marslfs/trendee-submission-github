-- ============================================================
-- queries.sql — 4 条核心查询（笔试题要求：按日期、平台分组统计销量）
-- 口径说明：
--   * 聚合一律用 dt_local（Asia/Shanghai）， UTC→本地跨天的 132 条记录归属会变，已在设计文档声明
--   * gray_zone（long dress）默认不计入主趋势，按 include_gray_zone 参数可选计入
--   * 日期过滤用 [start, end] 闭区间，作用于 dt_local::DATE
-- ============================================================

-- Q1 ｜日销量趋势：maxi dress（core），按日分组，可按平台过滤
--    → API /api/v1/sales/trend 的主查询
SELECT
    a.dt_local                                   AS dt_local,
    SUM(a.total_sales)                           AS total_sales,
    SUM(a.record_count)                          AS records,
    SUM(CASE WHEN a.tag_status = 'gray_zone'
             THEN a.total_sales ELSE 0 END)      AS gray_zone_sales
FROM agg_sales_daily a
WHERE a.tag_status = 'core'
  AND a.dt_local BETWEEN DATE '2024-01-01' AND DATE '2024-03-13'
  AND a.platform IN ('website')                 -- 可选：去掉此行 = 全平台
GROUP BY 1
ORDER BY 1;

-- Q2 ｜同一趋势，但平台拆分（前端画多系列折线用）
SELECT
    a.dt_local,
    a.platform,
    SUM(a.total_sales) AS total_sales
FROM agg_sales_daily a
WHERE a.tag_status = 'core'
  AND a.dt_local BETWEEN DATE '2024-01-01' AND DATE '2024-03-13'
GROUP BY 1, 2
ORDER BY 1, 2;

-- Q3 ｜日期范围 × 平台 汇总（不给日粒度，仅看区间总量）
SELECT
    a.platform,
    SUM(a.total_sales)   AS total_sales,
    SUM(a.record_count)  AS records,
    ROUND(SUM(a.total_sales) / SUM(a.record_count), 2) AS avg_per_record
FROM agg_sales_daily a
WHERE a.tag_status = 'core'
  AND a.dt_local BETWEEN DATE '2024-01-01' AND DATE '2024-03-13'
GROUP BY 1
ORDER BY total_sales DESC;

-- Q4 ｜区间内 maxi dress 商品榜（明细表直查，展示事实表用法）
SELECT
    p.product_id,
    p.title_norm,
    SUM(f.sales_count)  AS total_sales,
    COUNT(*)            AS records
FROM fact_sales f
JOIN dim_product p USING (product_id)
WHERE p.tag_status = 'core'
  AND CAST(f.dt_local AS DATE) BETWEEN DATE '2024-01-01' AND DATE '2024-03-13'
GROUP BY 1, 2
ORDER BY total_sales DESC
LIMIT 10;
