-- 评价系统V2：统一口径/匿名统一/排行榜缓存与等级升级积分（2025-09-28）

PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

/* 1) merchant_reviews 去除旧匿名列（is_user_anonymous） */
/* 说明：SQLite 不支持直接 DROP COLUMN，采用重建表的方式 */

CREATE TABLE IF NOT EXISTS merchant_reviews_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL UNIQUE,
    merchant_id INTEGER NOT NULL,
    user_id BIGINT NOT NULL,

    rating_attack_quality   INTEGER NOT NULL CHECK(rating_attack_quality BETWEEN 1 AND 10),
    rating_length           INTEGER NOT NULL CHECK(rating_length BETWEEN 1 AND 10),
    rating_hardness         INTEGER NOT NULL CHECK(rating_hardness BETWEEN 1 AND 10),
    rating_duration         INTEGER NOT NULL CHECK(rating_duration BETWEEN 1 AND 10),
    rating_user_temperament INTEGER NOT NULL CHECK(rating_user_temperament BETWEEN 1 AND 10),

    text_review_by_merchant TEXT,

    is_active BOOLEAN NOT NULL DEFAULT 1,
    is_deleted BOOLEAN NOT NULL DEFAULT 0,
    is_confirmed_by_admin BOOLEAN NOT NULL DEFAULT 0,
    confirmed_by_admin_id INTEGER,
    confirmed_at DATETIME,
    report_post_url TEXT,
    report_message_id INTEGER,
    published_at DATETIME,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO merchant_reviews_new (
    id, order_id, merchant_id, user_id,
    rating_attack_quality, rating_length, rating_hardness, rating_duration, rating_user_temperament,
    text_review_by_merchant,
    is_active, is_deleted, is_confirmed_by_admin, confirmed_by_admin_id, confirmed_at,
    report_post_url, report_message_id, published_at,
    created_at, updated_at
)
SELECT
    id, order_id, merchant_id, user_id,
    rating_attack_quality, rating_length, rating_hardness, rating_duration, rating_user_temperament,
    text_review_by_merchant,
    is_active, is_deleted, is_confirmed_by_admin, confirmed_by_admin_id, confirmed_at,
    report_post_url, report_message_id, published_at,
    created_at, updated_at
FROM merchant_reviews;

DROP TABLE merchant_reviews;
ALTER TABLE merchant_reviews_new RENAME TO merchant_reviews;

-- 还原最小必要索引
CREATE INDEX IF NOT EXISTS idx_mr_merchant_time ON merchant_reviews(merchant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_mr_user_time     ON merchant_reviews(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_mr_visible       ON merchant_reviews(is_confirmed_by_admin, is_active, is_deleted);


/* 2) 新增排行榜缓存表（user_score_leaderboards） */
CREATE TABLE IF NOT EXISTS user_score_leaderboards (
    dimension TEXT NOT NULL,
    user_id   BIGINT NOT NULL,
    avg_score REAL NOT NULL,
    reviews_count INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    updated_at DATETIME,
    PRIMARY KEY (dimension, user_id)
);
CREATE INDEX IF NOT EXISTS idx_leaderboards_dim_rank ON user_score_leaderboards(dimension, rank);


/* 3) user_levels 增加升级奖励积分字段（points_on_level_up） */
ALTER TABLE user_levels ADD COLUMN points_on_level_up INTEGER NOT NULL DEFAULT 0;


/* 4) 写入默认激励规则配置（如不存在） */
INSERT OR IGNORE INTO system_config (config_key, config_value, description) VALUES (
    'points_config',
    '{
      "order_complete": {"points": 10, "xp": 5},
      "u2m_review": {
        "base": {"points": 50, "xp": 20},
        "high_score_bonus": {"min_avg": 8.0, "points": 25, "xp": 10},
        "text_bonus": {"min_len": 10, "points": 15, "xp": 5}
      },
      "m2u_review": {
        "enable_points": false,
        "base": {"xp": 10},
        "high_score_bonus": {"min_avg": 8.0, "xp": 10},
        "text_bonus": {"min_len": 10, "xp": 5}
      }
    }',
    '激励规则配置（动态积分/经验，保存即生效）'
);


/* 5) 同步 schema_version */
INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2025.09.28.1', '评价系统V2 统一口径/匿名统一/排行榜与等级升级积分');

COMMIT;
PRAGMA foreign_keys=ON;

