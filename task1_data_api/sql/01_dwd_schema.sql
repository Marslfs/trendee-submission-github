-- ============================================================
-- 01_dwd_schema.sql — 数仓 DDL（DIM + DWD + DWS 三层）
--
-- 【分层归属】
--   DIM（维度层）  dim_platform / dim_product / dim_title_alias
--   DWD（明细层）  dwd_fact_sales      一行 = 一次销售记录
--   DWS（汇总层）  dws_sales_daily     日期 × 平台 × 标签档位的通用日汇总
--   元数据         dq_report           数据质量审计，不参与业务分层
--   （本 demo 不建 ADS 层：唯一消费方是 trend API，过滤均为通用筛选，DWS 直查即可）
--
-- 【设计口径】本地 demo 用 DuckDB 单文件；schema 按生产形态设计——
--   迁 ClickHouse：改 DDL 加 ORDER BY (platform, dt_local, tag_status) + 按月分区
--   迁 PostgreSQL：dwd_fact_sales 按 dt_local 周分区（pg_partman），DWS 用物化视图
--   DWD 粒度：一行 = 一次销售记录（product × user × 时间点 × 平台）
-- ============================================================

-- ---------- DIM 维度层 ----------
CREATE TABLE IF NOT EXISTS dim_platform (
    platform_name VARCHAR PRIMARY KEY   -- website / app / marketplace
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_id     INTEGER PRIMARY KEY,
    title_norm     VARCHAR NOT NULL,    -- 归一化标题（小写、去所有格/连字符、压空格）
    category_raw   VARCHAR NOT NULL,    -- 原始粗粒度类别（dress/pants/...）
    tag_status     VARCHAR NOT NULL,    -- core | gray_zone | excluded
    tag_rule       VARCHAR NOT NULL,    -- 命中规则编号 R1~R6（可解释打标，见 normalize.tag_product）
    is_gray_zone   BOOLEAN NOT NULL,    -- TRUE 仅当 gray_zone（long dress / 档位冲突）
    -- 打标粒度是「商品级」、证据在「标题级」：同一 product_id 出现互相矛盾的标题时，
    -- 只保留首个标题会静默把另一行的销量算进本商品的档位。这两列把冲突显式暴露出来，
    -- 由 run_dq_checks 的 tag_conflict_detection 告警，不再沉默吞掉。
    title_variants VARCHAR NOT NULL,    -- 该商品在明细里出现过的全部标题变体（去重、按首次出现排序，最多 5 条）
    tag_conflict   BOOLEAN NOT NULL     -- TRUE = 同一商品的多条标题判出了不同 tag_status
);

-- 标题别名表：记录「归一化标题 → 商品」映射，支撑多标题变体（大小写/语序/所有格差异）
CREATE TABLE IF NOT EXISTS dim_title_alias (
    title_norm    VARCHAR NOT NULL,
    product_id    INTEGER NOT NULL,
    raw_sample    VARCHAR,               -- 原始标题首例，便于审计
    PRIMARY KEY (title_norm, product_id)
);

-- ---------- DWD 明细事实层 ----------
CREATE TABLE IF NOT EXISTS dwd_fact_sales (
    row_hash      VARCHAR PRIMARY KEY,  -- md5(全字段拼接)，幂等去重键
    product_id    INTEGER NOT NULL,
    platform      VARCHAR NOT NULL,
    user_id       VARCHAR NOT NULL,
    sales_count   INTEGER NOT NULL,
    dt_utc        TIMESTAMP NOT NULL,   -- 原始时间戳，口径声明为 UTC
    dt_local      TIMESTAMP NOT NULL,   -- Asia/Shanghai (UTC+8)，聚合一律用此列
    -- 生产形态提示：ClickHouse 下追加
    --   ORDER BY (platform, dt_local) PARTITION BY toYYYYMM(dt_local)
    ingest_batch  VARCHAR NOT NULL      -- 摄取批次标识，可审计可回滚
);

-- ---------- DWS 通用汇总层 ----------
-- 粒度：日期 × 平台 × 标签档位；dt_local 为 Asia/Shanghai 口径
-- 这是「通用汇总」而非「应用专属汇总」：不含任何接口私有口径，因此属于 DWS 而非 ADS
CREATE TABLE IF NOT EXISTS dws_sales_daily (
    dt_local      DATE      NOT NULL,
    platform      VARCHAR   NOT NULL,
    tag_status    VARCHAR   NOT NULL,   -- core / gray_zone
    total_sales   BIGINT    NOT NULL,
    record_count  BIGINT    NOT NULL,
    PRIMARY KEY (dt_local, platform, tag_status)
);

-- ---------- 元数据：数据质量报告（不属于 DWD/DIM/DWS 任一层） ----------
CREATE TABLE IF NOT EXISTS dq_report (
    check_name    VARCHAR NOT NULL,
    severity      VARCHAR NOT NULL,   -- info / warn / error
    detail        VARCHAR NOT NULL,
    passed        BOOLEAN NOT NULL,
    checked_at    TIMESTAMP NOT NULL,
    ingest_batch  VARCHAR NOT NULL
);
