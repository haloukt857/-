-- Telegram商户机器人数据库架构 V2.0
-- 完全基于scripts/migrate_to_v2.py迁移脚本同步
-- 注意：本文件仅作为结构参考，实际部署请使用migrate_to_v2.py确保数据完整性

-- ==========================================
-- V2.0 核心表结构
-- ==========================================

-- 商户表（V2.0规范）
CREATE TABLE IF NOT EXISTS merchants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_chat_id BIGINT UNIQUE NOT NULL,  -- V2统一字段名
    name TEXT NOT NULL,
    contact_info TEXT,
    profile_data TEXT,
    -- V2.0状态生命周期
    status TEXT DEFAULT 'pending_submission' CHECK (status IN ('pending_submission', 'pending_approval', 'approved', 'published', 'expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 结构化字段（唯一真源）
    merchant_type TEXT DEFAULT 'teacher',     -- 商户类型
    city_id INTEGER,                          -- 城市ID（来自 cities）
    district_id INTEGER REFERENCES districts(id), -- 区县ID（来自 districts）
    p_price INTEGER,
    pp_price INTEGER,
    custom_description TEXT,
    adv_sentence TEXT,
    user_info TEXT,
    channel_link TEXT,
    channel_chat_id TEXT,                     -- 发布频道（用户名或ID）
    show_in_region_search INTEGER DEFAULT 0,
    publish_time DATETIME,
    expiration_time DATETIME,
    post_url TEXT                             -- 最近一次发布的频道贴文链接（用于后续编辑/删除）
);

-- 订单表（V2.0统一字段名）
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id INTEGER NOT NULL,
    customer_user_id BIGINT NOT NULL,         -- V2统一字段名
    customer_username TEXT,                   -- V2统一字段名
    course_type TEXT CHECK (course_type IN ('P','PP')), -- 课程类型
    price INTEGER NOT NULL,
    appointment_time DATETIME,
    completion_time DATETIME,
    status TEXT NOT NULL DEFAULT '尝试预约' CHECK (status IN ('尝试预约', '已完成', '已评价', '双方评价', '单方评价')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
);

-- 用户激励系统表
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    xp INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    order_count INTEGER DEFAULT 0,
    level_name TEXT DEFAULT '新手',
    badges TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 双向评价系统表
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL UNIQUE,
    merchant_id INTEGER NOT NULL,
    customer_user_id BIGINT NOT NULL,
    rating_appearance INTEGER,
    rating_figure INTEGER,
    rating_service INTEGER,
    rating_attitude INTEGER,
    rating_environment INTEGER,
    text_review_by_user TEXT,
    is_confirmed_by_merchant BOOLEAN DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'pending_user_review',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    report_message_id INTEGER
);

-- 商户评分统计表
CREATE TABLE IF NOT EXISTS merchant_scores (
    merchant_id INTEGER PRIMARY KEY,
    avg_appearance REAL,
    avg_figure REAL,
    avg_service REAL,
    avg_attitude REAL,
    avg_environment REAL,
    total_reviews_count INTEGER DEFAULT 0,
    updated_at DATETIME,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
);

-- 地区管理（V2双层结构）
CREATE TABLE IF NOT EXISTS cities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS districts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    city_id INTEGER NOT NULL,
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE CASCADE,
    UNIQUE(name, city_id)
);

-- V1兼容表已废弃，采用唯一方案：cities/districts
-- provinces 和 regions 表在迁移过程中会被删除

-- 用户等级系统
CREATE TABLE IF NOT EXISTS user_levels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level_name TEXT NOT NULL UNIQUE,
    xp_required INTEGER NOT NULL UNIQUE
);

-- 勋章系统
CREATE TABLE IF NOT EXISTS badges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    badge_name TEXT NOT NULL UNIQUE,
    badge_icon TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS user_badges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id BIGINT NOT NULL,
    badge_id INTEGER NOT NULL,
    earned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (badge_id) REFERENCES badges(id),
    UNIQUE(user_id, badge_id)
);

CREATE TABLE IF NOT EXISTS badge_triggers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    badge_id INTEGER NOT NULL,
    trigger_type TEXT NOT NULL,
    trigger_value INTEGER NOT NULL,
    FOREIGN KEY (badge_id) REFERENCES badges(id) ON DELETE CASCADE
);

-- 绑定码表
CREATE TABLE IF NOT EXISTS binding_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    merchant_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    used_at DATETIME,
    bound_telegram_username TEXT,
    bound_telegram_name TEXT,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE SET NULL
);

-- 发布频道配置表
CREATE TABLE IF NOT EXISTS posting_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT,
    channel_chat_id TEXT,
    channel_link TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 按钮配置表
CREATE TABLE IF NOT EXISTS button_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    message_text TEXT,
    message_image TEXT,
    buttons TEXT,
    created_by INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 活动日志表
CREATE TABLE IF NOT EXISTS activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action_type TEXT NOT NULL,
    details TEXT,
    button_id TEXT,
    merchant_id INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE SET NULL
);

-- FSM状态表
CREATE TABLE IF NOT EXISTS fsm_states (
    user_id INTEGER PRIMARY KEY,
    state TEXT,
    data TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 系统配置表
CREATE TABLE IF NOT EXISTS system_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key TEXT UNIQUE NOT NULL,
    config_value TEXT,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 模板表
CREATE TABLE IF NOT EXISTS templates (
    key TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 媒体文件表（仅保存Telegram file_id）
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id INTEGER NOT NULL,
    telegram_file_id TEXT NOT NULL,
    media_type TEXT NOT NULL CHECK (media_type IN ('photo','video')),
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
);

-- ==========================================
-- 自动回复与关键词模块（V2.0）
-- ==========================================

-- 自动回复：触发词表
CREATE TABLE IF NOT EXISTS auto_reply_triggers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER,
    trigger_text TEXT NOT NULL,
    match_type TEXT NOT NULL CHECK (match_type IN ('exact','contains')),
    is_active BOOLEAN DEFAULT TRUE,
    priority_order INTEGER DEFAULT 0,
    trigger_count INTEGER DEFAULT 0,
    last_triggered_at TIMESTAMP,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(trigger_text, match_type)
);

-- 自动回复：消息表
CREATE TABLE IF NOT EXISTS auto_reply_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger_id INTEGER NOT NULL,
    message_content TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    display_order INTEGER DEFAULT 0,
    send_count INTEGER DEFAULT 0,
    last_sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trigger_id) REFERENCES auto_reply_triggers(id) ON DELETE CASCADE
);

-- 自动回复：每日统计
CREATE TABLE IF NOT EXISTS auto_reply_daily_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger_id INTEGER NOT NULL,
    stat_date DATE NOT NULL,
    trigger_count INTEGER DEFAULT 0,
    unique_users_count INTEGER DEFAULT 0,
    total_messages_sent INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trigger_id) REFERENCES auto_reply_triggers(id) ON DELETE CASCADE,
    UNIQUE(trigger_id, stat_date)
);

-- 关键词表
CREATE TABLE IF NOT EXISTS keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 商户-关键词关联表
CREATE TABLE IF NOT EXISTS merchant_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id INTEGER NOT NULL,
    keyword_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(merchant_id, keyword_id),
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE,
    FOREIGN KEY (keyword_id) REFERENCES keywords(id) ON DELETE CASCADE
);

-- ==========================================
-- 索引创建
-- ==========================================

-- 商户表索引
CREATE INDEX IF NOT EXISTS idx_merchants_telegram_chat_id ON merchants(telegram_chat_id);
CREATE INDEX IF NOT EXISTS idx_merchants_status ON merchants(status);
CREATE INDEX IF NOT EXISTS idx_merchants_channel_chat_id ON merchants(channel_chat_id);
CREATE INDEX IF NOT EXISTS idx_merchants_publish_time ON merchants(publish_time);
CREATE INDEX IF NOT EXISTS idx_merchants_expiration_time ON merchants(expiration_time);

-- 订单表索引
CREATE INDEX IF NOT EXISTS idx_orders_customer_user_id ON orders(customer_user_id);
CREATE INDEX IF NOT EXISTS idx_orders_merchant_id ON orders(merchant_id);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);

-- 用户表索引
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_level_name ON users(level_name);
CREATE INDEX IF NOT EXISTS idx_users_xp ON users(xp);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- 评价表索引
CREATE INDEX IF NOT EXISTS idx_reviews_customer_user_id ON reviews(customer_user_id);
CREATE INDEX IF NOT EXISTS idx_reviews_merchant_id ON reviews(merchant_id);
CREATE INDEX IF NOT EXISTS idx_reviews_created_at ON reviews(created_at);

-- 频道贴文记录（每条频道消息一行，用于后续编辑/删除）
CREATE TABLE IF NOT EXISTS merchant_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id INTEGER NOT NULL,
    chat_id TEXT NOT NULL,              -- '@username' 或 '-100xxxxxxxxx'
    message_id INTEGER NOT NULL,
    post_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_merchant_posts_mid ON merchant_posts(merchant_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_merchant_posts_unique ON merchant_posts(merchant_id, chat_id, message_id);

-- 绑定码表索引
CREATE INDEX IF NOT EXISTS idx_binding_codes_code ON binding_codes(code);
CREATE INDEX IF NOT EXISTS idx_binding_codes_expires_at ON binding_codes(expires_at);

-- 活动日志索引
CREATE INDEX IF NOT EXISTS idx_activity_logs_user_id ON activity_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_logs_timestamp ON activity_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_activity_logs_action_type ON activity_logs(action_type);

-- FSM状态索引
CREATE INDEX IF NOT EXISTS idx_fsm_states_user_id ON fsm_states(user_id);

-- 模板索引
CREATE INDEX IF NOT EXISTS idx_templates_key ON templates(key);
-- 媒体索引
CREATE INDEX IF NOT EXISTS idx_media_merchant ON media(merchant_id);
CREATE INDEX IF NOT EXISTS idx_media_sort ON media(sort_order);

-- 自动回复索引
CREATE INDEX IF NOT EXISTS idx_auto_triggers_active ON auto_reply_triggers(is_active);
CREATE INDEX IF NOT EXISTS idx_auto_triggers_text ON auto_reply_triggers(trigger_text);
CREATE INDEX IF NOT EXISTS idx_auto_msgs_trigger ON auto_reply_messages(trigger_id);
CREATE INDEX IF NOT EXISTS idx_auto_stats_date ON auto_reply_daily_stats(stat_date);

-- ==========================================
-- 触发器创建
-- ==========================================

-- 商户表时间戳触发器
CREATE TRIGGER IF NOT EXISTS update_merchants_timestamp 
    AFTER UPDATE ON merchants
    FOR EACH ROW
    BEGIN
        UPDATE merchants SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

-- 用户表时间戳触发器
CREATE TRIGGER IF NOT EXISTS update_users_timestamp 
    AFTER UPDATE ON users
    FOR EACH ROW
    BEGIN
        UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE user_id = NEW.user_id;
    END;

-- 区县表时间戳触发器
CREATE TRIGGER IF NOT EXISTS update_districts_timestamp 
    AFTER UPDATE ON districts
    FOR EACH ROW
    BEGIN
        UPDATE districts SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

-- 按钮配置表时间戳触发器
CREATE TRIGGER IF NOT EXISTS update_button_configs_timestamp 
    AFTER UPDATE ON button_configs
    FOR EACH ROW
    BEGIN
        UPDATE button_configs SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

-- FSM状态表时间戳触发器
CREATE TRIGGER IF NOT EXISTS update_fsm_states_timestamp 
    AFTER UPDATE ON fsm_states
    FOR EACH ROW
    BEGIN
        UPDATE fsm_states SET updated_at = CURRENT_TIMESTAMP WHERE user_id = NEW.user_id;
    END;

-- 系统配置表时间戳触发器
CREATE TRIGGER IF NOT EXISTS update_system_config_timestamp 
    AFTER UPDATE ON system_config
    FOR EACH ROW
    BEGIN
        UPDATE system_config SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

-- 模板表时间戳触发器
CREATE TRIGGER IF NOT EXISTS update_templates_timestamp 
    AFTER UPDATE ON templates
    FOR EACH ROW
    BEGIN
        UPDATE templates SET updated_at = CURRENT_TIMESTAMP WHERE key = NEW.key;
    END;

-- ==========================================
-- 默认系统配置
-- ==========================================

INSERT OR IGNORE INTO system_config (config_key, config_value, description) VALUES
('schema_version', '2025.09.22.1', '数据库架构版本（V2.0）'),
('bot_status', 'active', '机器人运行状态'),
('max_binding_code_age_hours', '24', '绑定码有效期（小时）'),
('default_merchant_status', 'pending_submission', '新商户默认状态（V2.0）'),
('enable_activity_logging', 'true', '是否启用活动日志记录');
