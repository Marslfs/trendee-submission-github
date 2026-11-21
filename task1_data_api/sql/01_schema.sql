-- ============================================================
-- 01_schema.sql — DuckDB schema（Task 1）
-- 设计口径：本地 demo 用 DuckDB 单文件；schema 按生产形态设计——
--   迁 ClickHouse：改 DDL 加 ORDER BY (platform, dt_local, tag_status) + 按月分区
--   迁 PostgreSQL：fact_sales 按 dt_local 周分区（pg_partman），agg 表用物化视图
-- 事实表粒度：一行 = 一次销售记录（product × user × 时间点 × 平台）
-- ============================================================

-- ---------- 维表 ----------
CREATE TABLE IF NOT EXISTS dim_platform (
    platform_name VARCHAR PRIMARY KEY   -- website / app / marketplace
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_id    INTEGER PRIMARY KEY,
    title_norm    VARCHAR NOT NULL,     -- 归一化标题（小写、去所有格/连字符、压空格）
    category_raw  VARCHAR NOT NULL,     -- 原始粗粒度类别（dress/pants/...）
    tag_status    VARCHAR NOT NULL,     -- core | gray_zone | excluded
    is_gray_zone  BOOLEAN NOT NULL      -- TRUE 仅当 gray_zone（long dress 无 maxi）
);

-- 标题别名表：记录「归一化标题 → 商品」映射，支撑多标题变体（大小写/语序/所有格差异）
CREATE TABLE IF NOT EXISTS dim_title_alias (
    title_norm    VARCHAR NOT NULL,
    product_id    INTEGER NOT NULL,
    raw_sample    VARCHAR,               -- 原始标题首例，便于审计
    PRIMARY KEY (title_norm, product_id)
);

-- ---------- 事实表 ----------
CREATE TABLE IF NOT EXISTS fact_sales (
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

-- ---------- 日预聚合表（查询主力，避免在线扫明细） ----------
-- 粒度：日期 × 平台 × 标签档位；dt_local 为 Asia/Shanghai 口径
CREATE TABLE IF NOT EXISTS agg_sales_daily (
    dt_local      DATE      NOT NULL,
    platform      VARCHAR   NOT NULL,
    tag_status    VARCHAR   NOT NULL,   -- core / gray_zone
    total_sales   BIGINT    NOT NULL,
    record_count  BIGINT    NOT NULL,
    PRIMARY KEY (dt_local, platform, tag_status)
);

-- ---------- 数据质量报告表 ----------
CREATE TABLE IF NOT EXISTS dq_report (
    check_name    VARCHAR NOT NULL,
    severity      VARCHAR NOT NULL,   -- info / warn / error
    detail        VARCHAR NOT NULL,
    passed        BOOLEAN NOT NULL,
    checked_at    TIMESTAMP NOT NULL,
    ingest_batch  VARCHAR NOT NULL
);
