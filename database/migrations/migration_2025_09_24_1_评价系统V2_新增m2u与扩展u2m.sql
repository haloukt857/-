-- 评价系统 V2 数据库迁移
-- 内容：
-- 1) 扩展现有 u2m 表 `reviews`（仅新增最小必要字段；不改变现有评分/结构）
-- 2) 新增 m2u 表 `merchant_reviews`
-- 3) 新增用户侧聚合表 `user_scores`
-- 4) 最小必要索引

-- =============== 1) 扩展 u2m：reviews（如果字段已存在请忽略相应 ALTER） ===============
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

-- 管理与可见性
ALTER TABLE reviews ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1;
ALTER TABLE reviews ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0;
ALTER TABLE reviews ADD COLUMN is_confirmed_by_admin BOOLEAN NOT NULL DEFAULT 0;
ALTER TABLE reviews ADD COLUMN confirmed_by_admin_id INTEGER;
ALTER TABLE reviews ADD COLUMN confirmed_at DATETIME;

-- 报告频道链接（唯一贴文直达链接）与发布时间
ALTER TABLE reviews ADD COLUMN report_post_url TEXT;
ALTER TABLE reviews ADD COLUMN published_at DATETIME;

-- 审计
ALTER TABLE reviews ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP;

-- 最小必要索引（SQLite）
CREATE INDEX IF NOT EXISTS idx_reviews_merchant_time ON reviews(merchant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reviews_visible ON reviews(is_confirmed_by_admin, is_active, is_deleted);

COMMIT;
PRAGMA foreign_keys=ON;


-- =============== 2) 新增 m2u：merchant_reviews（商户/老师 → 用户） ===============
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS merchant_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL UNIQUE,
    merchant_id INTEGER NOT NULL,
    user_id BIGINT NOT NULL,

    -- 五维评分（1–10）
    rating_attack_quality   INTEGER NOT NULL CHECK(rating_attack_quality BETWEEN 1 AND 10), -- 出击素质
    rating_length           INTEGER NOT NULL CHECK(rating_length BETWEEN 1 AND 10),         -- 长度
    rating_hardness         INTEGER NOT NULL CHECK(rating_hardness BETWEEN 1 AND 10),       -- 硬度
    rating_duration         INTEGER NOT NULL CHECK(rating_duration BETWEEN 1 AND 10),       -- 时间
    rating_user_temperament INTEGER NOT NULL CHECK(rating_user_temperament BETWEEN 1 AND 10), -- 用户气质

    text_review_by_merchant TEXT,                 -- 文本可为空（Bot 一般仅返回链接）

    -- 管理/可见性/发布
    is_active BOOLEAN NOT NULL DEFAULT 1,
    is_deleted BOOLEAN NOT NULL DEFAULT 0,
    is_confirmed_by_admin BOOLEAN NOT NULL DEFAULT 0,
    confirmed_by_admin_id INTEGER,
    confirmed_at DATETIME,
    report_post_url TEXT,
    published_at DATETIME,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 最小必要索引
CREATE INDEX IF NOT EXISTS idx_mr_merchant_time ON merchant_reviews(merchant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_mr_user_time     ON merchant_reviews(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_mr_visible       ON merchant_reviews(is_confirmed_by_admin, is_active, is_deleted);

COMMIT;
PRAGMA foreign_keys=ON;


-- =============== 3) 新增用户聚合：user_scores（供 Bot 自查与后台查看） ===============
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS user_scores (
    user_id BIGINT PRIMARY KEY,
    avg_attack_quality   REAL,
    avg_length           REAL,
    avg_hardness         REAL,
    avg_duration         REAL,
    avg_user_temperament REAL,
    total_reviews_count INTEGER DEFAULT 0,
    updated_at DATETIME
);

COMMIT;
PRAGMA foreign_keys=ON;

