-- ============================================================
-- 03_dws_agg.sql — DWD → DWS 汇总加工（全量重算，可重复执行）
-- 输入：dwd_fact_sales（明细） + dim_product（打标）
-- 输出：dws_sales_daily（日期 × 平台 × 标签档位）
-- 幂等策略：先删后插（全量重算），300 行规模毫秒级；
-- 生产形态：改增量 upsert（Watermark = DWS 表 max(dt_local)），由调度器日跑
-- ============================================================

DELETE FROM dws_sales_daily;

INSERT INTO dws_sales_daily
SELECT
    CAST(dt_local AS DATE)          AS dt_local,
    platform,
    p.tag_status                    AS tag_status,
    SUM(f.sales_count)              AS total_sales,
    COUNT(*)                        AS record_count
FROM dwd_fact_sales f
JOIN dim_product p USING (product_id)
WHERE p.tag_status IN ('core', 'gray_zone')   -- excluded 不进汇总
GROUP BY 1, 2, 3;
