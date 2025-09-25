-- 扩展数据库架构 - 支持新上榜流程
-- 在现有schema.sql基础上添加新表和字段（以城市/区县为唯一标准）

-- 城市表
CREATE TABLE IF NOT EXISTS cities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,        -- 城市名称
    code TEXT DEFAULT '',             -- 城市代码
    display_order INTEGER DEFAULT 0,  -- 显示顺序
    is_active BOOLEAN DEFAULT TRUE,   -- 是否激活
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 区县表
CREATE TABLE IF NOT EXISTS districts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,               -- 区县名称
    city_id INTEGER NOT NULL,         -- 所属城市ID
    code TEXT DEFAULT '',             -- 区县代码
    display_order INTEGER DEFAULT 0,  -- 显示顺序
    is_active BOOLEAN DEFAULT TRUE,   -- 是否激活
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE CASCADE,
    UNIQUE(name, city_id)             -- 同一城市内区县名不重复
);

-- 关键词表
CREATE TABLE IF NOT EXISTS keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,        -- 关键词名称（2字）
    display_order INTEGER DEFAULT 0,  -- 显示顺序
    is_active BOOLEAN DEFAULT TRUE,   -- 是否激活
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 商家关键词关联表（多对多关系）
CREATE TABLE IF NOT EXISTS merchant_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id INTEGER NOT NULL,     -- 商家ID
    keyword_id INTEGER NOT NULL,      -- 关键词ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE,
    FOREIGN KEY (keyword_id) REFERENCES keywords(id) ON DELETE CASCADE,
    UNIQUE(merchant_id, keyword_id)   -- 避免重复关联
);

-- 扩展商户表字段（使用ALTER TABLE添加新字段）
-- 注意：每个ALTER TABLE语句只能添加一个字段

-- 添加商户类型字段
ALTER TABLE merchants ADD COLUMN merchant_type TEXT DEFAULT 'teacher';

-- 添加城市与区县外键字段
ALTER TABLE merchants ADD COLUMN city_id INTEGER;
ALTER TABLE merchants ADD COLUMN district_id INTEGER;

-- 添加p价格字段
ALTER TABLE merchants ADD COLUMN p_price INTEGER;

-- 添加pp价格字段
ALTER TABLE merchants ADD COLUMN pp_price INTEGER;

-- 添加自定义资料字段
ALTER TABLE merchants ADD COLUMN custom_description TEXT;

-- 添加“优势一句话”字段（≤30字，由业务层校验）
ALTER TABLE merchants ADD COLUMN adv_sentence TEXT;

-- 添加用户检测信息字段（JSON格式存储从Telegram API获取的用户信息）
ALTER TABLE merchants ADD COLUMN user_info TEXT;

-- 添加频道链接字段
ALTER TABLE merchants ADD COLUMN channel_link TEXT;

-- 添加频道用户名字段（@username），用于公开频道标识
ALTER TABLE merchants ADD COLUMN channel_chat_id TEXT;

-- 帖子生命周期字段
ALTER TABLE merchants ADD COLUMN publish_time DATETIME;        -- 期望发布时间
ALTER TABLE merchants ADD COLUMN expiration_time DATETIME;     -- 服务到期时间

-- 添加cities表code字段（用于城市代码存储）
ALTER TABLE cities ADD COLUMN code TEXT DEFAULT '';

-- 创建新索引
CREATE INDEX IF NOT EXISTS idx_cities_name ON cities(name);
CREATE INDEX IF NOT EXISTS idx_cities_display_order ON cities(display_order);
CREATE INDEX IF NOT EXISTS idx_districts_city_id ON districts(city_id);
CREATE INDEX IF NOT EXISTS idx_districts_name ON districts(name);
CREATE INDEX IF NOT EXISTS idx_districts_display_order ON districts(display_order);
CREATE INDEX IF NOT EXISTS idx_keywords_name ON keywords(name);
CREATE INDEX IF NOT EXISTS idx_keywords_display_order ON keywords(display_order);
CREATE INDEX IF NOT EXISTS idx_merchant_keywords_merchant_id ON merchant_keywords(merchant_id);
CREATE INDEX IF NOT EXISTS idx_merchant_keywords_keyword_id ON merchant_keywords(keyword_id);
CREATE INDEX IF NOT EXISTS idx_merchants_city_id ON merchants(city_id);
CREATE INDEX IF NOT EXISTS idx_merchants_district_id ON merchants(district_id);
CREATE INDEX IF NOT EXISTS idx_merchants_merchant_type ON merchants(merchant_type);
CREATE INDEX IF NOT EXISTS idx_merchants_channel_chat_id ON merchants(channel_chat_id);
CREATE INDEX IF NOT EXISTS idx_merchants_publish_time ON merchants(publish_time);
CREATE INDEX IF NOT EXISTS idx_merchants_expiration_time ON merchants(expiration_time);

-- 创建触发器以自动更新updated_at字段
CREATE TRIGGER IF NOT EXISTS update_cities_timestamp 
    AFTER UPDATE ON cities
    FOR EACH ROW
    BEGIN
        UPDATE cities SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_districts_timestamp 
    AFTER UPDATE ON districts
    FOR EACH ROW
    BEGIN
        UPDATE districts SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_keywords_timestamp 
    AFTER UPDATE ON keywords
    FOR EACH ROW
    BEGIN
        UPDATE keywords SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

-- 触发器：当城市名称更新时，同步更新所有关联商户的地区显示
-- 已移除所有基于 merchants.region 的同步触发器；地区仅使用结构化字段（city_id/district_id）

-- 注意：已移除硬编码的测试数据
-- 用户需要通过管理界面手动添加省份、区域和关键词数据

-- 更新系统配置版本
UPDATE system_config SET config_value = '2025.09.16.2' WHERE config_key = 'schema_version';
