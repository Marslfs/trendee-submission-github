-- ============================================================
-- 02_dwd_tag.sql — ODS → DIM 打标加工（DWD 层加工逻辑）
-- 产出：dim_product.tag_status（core / gray_zone / excluded）与 tag_rule（R1~R6）
-- 定位：这不是查询脚本，而是「贴源行 → 维度打标」的加工步骤，
--       因此归属 DWD 加工层，而不是应用查询层。
-- 与 src/normalize.py 交叉验证（Python 版为准，tests/test_tag_rule.py 对 30 个商品逐条断言一致）
--
-- 词级匹配：用 regexp_matches(tn, '(^| )词( |$)')，不用 LIKE '%词%' 子串，
--   避免 dress 误匹配 address、maxi 误匹配 maxim —— 与 design.md §4 口径一致。
-- 规则编号（与 normalize.tag_product 一一对应）：
--   R1 主档位 mini/midi（非属性修饰）→ excluded；R2 maxi 无 dress → excluded；
--   R3 maxi∧dress → core；R4 dress∧long（或 floor length）无 maxi → gray_zone；
--   R5 其余 → excluded；R6 档位冲突（mini/midi 与 maxi 同时为主档位）→ gray_zone 待人工确认
-- 归一化链（与 Python 版同序，SQL 侧能力所限的差异写在最后）：
--   小写 → 所有格（women's→women s）→ 分隔符（- _ / | ;）→ 压空白 → 去首尾
--   → 复数还原（dresses→dress / skirts→skirt / maxis→maxi）→ 组合词切分（maxidress→maxi dress）
--   → 已知拼写变体（maxy→maxi / dres|dresss→dress）
--   SQL 侧不做的两件事（Python 为权威口径）：
--     ① NFKC 全角归一（DuckDB 无内置 NFKC，全角标题由 Python 侧处理）
--     ② 任意 DL≤1 容错（SQL 只映射已知变体表，避免把 maxim/address 误纠成档位词）
-- ============================================================

WITH s1 AS (
    SELECT DISTINCT product_id, title
    FROM ods_sales_seed
),
s1b AS (  -- 全角字母/表意空格折成半角（DuckDB 无 NFKC，这里做等价的最小映射）
    SELECT product_id, title,
           replace(translate(lower(title),
                   'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
                   'abcdefghijklmnopqrstuvwxyz'), chr(12288), ' ') AS t0
    FROM s1
),
s2 AS (   -- 所有格 + 分隔符 + 压空白
    SELECT product_id, title,
           trim(regexp_replace(regexp_replace(
               regexp_replace(t0, '(\w+)''s', '\1 s', 'g'),
               '[-_/|;]+', ' ', 'g'), ' +', ' ', 'g')) AS s
    FROM s1b
),
s3 AS (   -- 复数还原（只对核心词做，避免把 address 还原成 addres）
    SELECT product_id, title,
           regexp_replace(regexp_replace(s,
               '(^| )(dress|skirt|maxi|mini|midi|long)es( |$)', '\1\2\3', 'g'),
               '(^| )(dress|skirt|maxi|mini|midi|long)s( |$)', '\1\2\3', 'g') AS s
    FROM s2
),
s4 AS (   -- 组合词切分
    SELECT product_id, title,
           regexp_replace(s, '(maxi|mini|midi|long)(dress|skirt)', '\1 \2', 'g') AS s
    FROM s3
),
s5 AS (   -- 已知拼写变体（不做通用编辑距离：maxim/address 不能被纠成档位词）
    SELECT product_id, title,
           regexp_replace(regexp_replace(regexp_replace(regexp_replace(s,
               '(^| )maxy( |$)', '\1maxi\2', 'g'),
               '(^| )dres( |$)', '\1dress\2', 'g'),
               '(^| )dresss( |$)', '\1dress\2', 'g'),
               '(^| )minii( |$)', '\1mini\2', 'g') AS title_norm
    FROM s4
),
feat AS (  -- 先把谓词算成布尔列，CASE 只读列，避免重复书写长正则
    SELECT product_id, title_norm,
           regexp_matches(title_norm, '(^| )maxi( |$)')  AS has_maxi,
           regexp_matches(title_norm, '(^| )dress( |$)') AS has_dress,
           regexp_matches(title_norm, '(^| )long( |$)')  AS has_long,
           regexp_matches(title_norm, '(^| )floor( |$)')
             AND regexp_matches(title_norm, '(^| )length( |$)') AS has_floor_len,
           -- 主档位 mini/midi：紧跟属性词（print/length/sleeve…）时是修饰语，不算档位
           (regexp_matches(title_norm, '(^| )(mini|midi)( |$)')
            AND NOT regexp_matches(title_norm,
                 '(^| )(mini|midi) (print|prints|length|sleeve|sleeves|hem|cut|pleat|pleats|slit|waist|fit|rise|size|petite|pattern|floral|dot|dots|stripe|stripes|logo|neck|collar|button|buttons|pocket|pockets|belt|tie|trim|detail|details|panel|yoke|ruffle|ruffles|edition|series|collection|line)( |$)')
           ) AS tier_minimidi
    FROM s5
),
ruled AS (
    SELECT product_id, title_norm,
           CASE
               WHEN tier_minimidi AND has_maxi                                         THEN 'R6'
               WHEN tier_minimidi                                                      THEN 'R1'
               WHEN has_maxi AND NOT has_dress                                         THEN 'R2'
               WHEN has_maxi AND has_dress                                             THEN 'R3'
               WHEN has_dress AND (has_long OR has_floor_len)                          THEN 'R4'
               ELSE 'R5'
           END AS tag_rule
    FROM feat
)
SELECT product_id, title_norm,
       CASE tag_rule
           WHEN 'R3' THEN 'core'
           WHEN 'R4' THEN 'gray_zone'
           WHEN 'R6' THEN 'gray_zone'
           ELSE 'excluded'
       END AS tag_status,
       tag_rule
FROM ruled
ORDER BY product_id;
