-- ============================================================
-- 03_agg.sql — 从 fact_sales 重建日预聚合（全量重算，可重复执行）
-- 幂等策略：先删后插（全量重算），300 行规模毫秒级；
-- 生产形态：改增量 upsert（Watermark = agg 表 max(dt_local)），由调度器日跑
-- ============================================================

DELETE FROM agg_sales_daily;

INSERT INTO agg_sales_daily
SELECT
    CAST(dt_local AS DATE)          AS dt_local,
    platform,
    p.tag_status                    AS tag_status,
    SUM(f.sales_count)              AS total_sales,
    COUNT(*)                        AS record_count
FROM fact_sales f
JOIN dim_product p USING (product_id)
WHERE p.tag_status IN ('core', 'gray_zone')   -- excluded 不进聚合
GROUP BY 1, 2, 3;
