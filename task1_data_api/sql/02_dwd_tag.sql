-- ============================================================
-- 02_dwd_tag.sql — ODS → DIM 打标加工（DWD 层加工逻辑）
-- 产出：dim_product.tag_status（core / gray_zone / excluded）
-- 定位：这不是查询脚本，而是「贴源行 → 维度打标」的加工步骤，
--       因此归属 DWD 加工层，而不是应用查询层。
-- 与 src/normalize.py 交叉验证（Python 版为准，本脚本用于 SQL 侧复核）
--
-- 三段式判定：
--   ① core     ：归一化后同时含 maxi 与 dress，且不含 mini/midi
--   ② excluded ：含 mini 或 midi（长度档位冲突）；或含 maxi 但无 dress（如 maxi skirt）
--   ③ gray_zone：含 dress + long 但无 maxi（Elegant Long Dress 类）——计入但打标，可配置
-- 归一化：小写 → 去所有格（women's→women s）→ 连字符转空格 → 压缩连续空格
-- ============================================================

SELECT
    product_id,
    title                                                AS raw_title,
    lower(regexp_replace(regexp_replace(title, '(\w+)''s', '\1 s'), '[-\s]+', ' ', 'g')) AS title_norm,
    CASE
        WHEN lower(title) LIKE '%mini%' OR lower(title) LIKE '%midi%'
             OR (lower(title) LIKE '%maxi%' AND lower(title) NOT LIKE '%dress%')
            THEN 'excluded'
        WHEN lower(title) LIKE '%maxi%' AND lower(title) LIKE '%dress%'
            THEN 'core'
        WHEN lower(title) LIKE '%dress%' AND lower(title) LIKE '%long%'
            THEN 'gray_zone'
        ELSE 'excluded'
    END AS tag_status
-- ods_sales_seed：贴源层（ODS）临时表，demo 中由 xlsx 直接读入；
-- 生产形态对应 ods.sales_seed（每日落分区，再由 DWD 加工任务消费）
FROM (SELECT DISTINCT product_id, title FROM ods_sales_seed);
