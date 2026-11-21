-- ============================================================
-- 02_tag.sql — maxi dress 打标规则（SQL 版，与 src/normalize.py 交叉验证）
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
FROM (SELECT DISTINCT product_id, title FROM fact_seed);  -- fact_seed = 摄取前的原始行
