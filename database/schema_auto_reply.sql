-- 自动回复功能数据库架构
-- 创建自动回复相关的表结构

-- 自动回复触发词表
-- 存储管理员配置的触发词信息
CREATE TABLE IF NOT EXISTS auto_reply_triggers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger_text TEXT NOT NULL,                -- 触发词内容
    match_type TEXT DEFAULT 'contains' CHECK (match_type IN ('exact', 'contains')), -- 匹配类型
    is_active BOOLEAN DEFAULT TRUE,            -- 是否启用
    priority_order INTEGER DEFAULT 0,          -- 优先级排序（数字越小优先级越高）
    trigger_count INTEGER DEFAULT 0,           -- 触发次数统计
    last_triggered_at TIMESTAMP,               -- 最后触发时间
    created_by INTEGER NOT NULL,               -- 创建者管理员ID
    admin_id INTEGER NOT NULL,                 -- 管理员ID（与created_by相同，用于兼容性）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 自动回复消息表
-- 存储每个触发词对应的回复消息
CREATE TABLE IF NOT EXISTS auto_reply_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger_id INTEGER NOT NULL,               -- 关联的触发词ID
    message_content TEXT NOT NULL,             -- 消息内容（支持变量函数）
    is_active BOOLEAN DEFAULT TRUE,            -- 是否启用
    display_order INTEGER DEFAULT 0,           -- 显示顺序
    send_count INTEGER DEFAULT 0,              -- 发送次数统计
    last_sent_at TIMESTAMP,                    -- 最后发送时间
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trigger_id) REFERENCES auto_reply_triggers(id) ON DELETE CASCADE
);

-- 自动回复统计表（日统计）
-- 按日统计自动回复的使用情况
CREATE TABLE IF NOT EXISTS auto_reply_daily_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger_id INTEGER NOT NULL,               -- 触发词ID
    stat_date DATE NOT NULL,                   -- 统计日期
    trigger_count INTEGER DEFAULT 0,           -- 当日触发次数
    unique_users_count INTEGER DEFAULT 0,      -- 当日唯一用户数
    total_messages_sent INTEGER DEFAULT 0,     -- 当日发送消息总数
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trigger_id) REFERENCES auto_reply_triggers(id) ON DELETE CASCADE
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_auto_reply_triggers_active ON auto_reply_triggers(is_active);
CREATE INDEX IF NOT EXISTS idx_auto_reply_triggers_priority ON auto_reply_triggers(priority_order);
CREATE INDEX IF NOT EXISTS idx_auto_reply_triggers_text ON auto_reply_triggers(trigger_text);
CREATE INDEX IF NOT EXISTS idx_auto_reply_triggers_created_by ON auto_reply_triggers(created_by);

CREATE INDEX IF NOT EXISTS idx_auto_reply_messages_trigger_id ON auto_reply_messages(trigger_id);
CREATE INDEX IF NOT EXISTS idx_auto_reply_messages_active ON auto_reply_messages(is_active);
CREATE INDEX IF NOT EXISTS idx_auto_reply_messages_order ON auto_reply_messages(display_order);

CREATE INDEX IF NOT EXISTS idx_auto_reply_stats_trigger_date ON auto_reply_daily_stats(trigger_id, stat_date);
CREATE INDEX IF NOT EXISTS idx_auto_reply_stats_date ON auto_reply_daily_stats(stat_date);

-- 创建触发器自动更新updated_at字段
CREATE TRIGGER IF NOT EXISTS update_auto_reply_triggers_timestamp 
    AFTER UPDATE ON auto_reply_triggers
    FOR EACH ROW
    BEGIN
        UPDATE auto_reply_triggers SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_auto_reply_messages_timestamp 
    AFTER UPDATE ON auto_reply_messages
    FOR EACH ROW
    BEGIN
        UPDATE auto_reply_messages SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

-- 创建触发器自动更新触发词的统计信息
CREATE TRIGGER IF NOT EXISTS update_trigger_stats_on_message_send
    AFTER UPDATE OF send_count ON auto_reply_messages
    FOR EACH ROW
    WHEN NEW.send_count > OLD.send_count
    BEGIN
        UPDATE auto_reply_triggers 
        SET trigger_count = trigger_count + (NEW.send_count - OLD.send_count),
            last_triggered_at = CURRENT_TIMESTAMP
        WHERE id = NEW.trigger_id;
    END;

-- 插入默认配置
INSERT OR IGNORE INTO system_config (config_key, config_value, description) VALUES
('auto_reply_enabled', 'true', '自动回复功能是否启用'),
('auto_reply_max_triggers_per_admin', '100', '每个管理员最大触发词数量'),
('auto_reply_max_messages_per_trigger', '20', '每个触发词最大消息数量'),
('auto_reply_cache_expiry_hours', '24', '触发词缓存过期时间（小时）'),
('auto_reply_stats_update_interval', '3600', '统计数据更新间隔（秒）');