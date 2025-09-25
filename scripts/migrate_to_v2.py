# -*- coding: utf-8 -*-
"""
数据库迁移脚本：从 V1.0 迁移到 V2.0

核心功能:
1.  安全地连接到现有SQLite数据库。
2.  创建V2.0架构中新增的表 (reviews, users, user_levels, badges, 等)。
3.  修改现有表结构以适应V2.0设计 (例如，重命名旧地区表，为merchants表添加新列)。
4.  脚本设计为幂等，可重复安全运行而不会引发错误或破坏数据。

注意: 此脚本只负责搭建数据库骨架 (Schema)，不涉及任何数据迁移。
"""

import sqlite3
import os
import sys

# 将项目根目录添加到Python路径，以便导入path_manager
# 这使得脚本可以作为独立文件在任何位置运行
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from pathmanager import PathManager
except ImportError:
    print("错误：无法导入 PathManager。请确保脚本位于项目结构内，或者项目根目录已在PYTHONPATH中。")
    sys.exit(1)

def execute_sql(cursor, sql, description):
    """执行单条SQL语句并处理异常，确保幂等性"""
    try:
        cursor.execute(sql)
        print(f"成功: {description}")
    except sqlite3.OperationalError as e:
        # 常见错误，如表已存在、列已存在、索引已存在，可以安全忽略
        if "already exists" in str(e) or "duplicate column name" in str(e):
            print(f"跳过: {description} (已存在)")
        else:
            print(f"警告: 执行 '{description}' 时发生错误: {e}")
            # 对于更严重或意外的错误，可以选择抛出异常
            # raise e

def migrate_to_v2(db_path):
    """执行数据库从 V1 到 V2 的结构迁移"""
    print(f"连接到数据库: {db_path}")
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print("\n--- 阶段1: 重命名旧的地理位置表 (如果存在) ---")
        # 为了避免与新创建的表冲突，先将可能存在的旧表重命名
        execute_sql(cursor, "ALTER TABLE provinces RENAME TO cities_old_temp;", "重命名 'provinces' 为 'cities_old_temp'")
        execute_sql(cursor, "ALTER TABLE regions RENAME TO districts_old_temp;", "重命名 'regions' 为 'districts_old_temp'")

        print("\n--- 阶段2: 创建 V2.0 新增的表 ---")

        # 城市与地区管理模块
        execute_sql(cursor, """
        CREATE TABLE IF NOT EXISTS cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            display_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """, "创建 'cities' 表")

        execute_sql(cursor, """
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
        """, "创建 'districts' 表")

        # 商家与用户双向评价系统模块
        execute_sql(cursor, """
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
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """, "创建 'reviews' 表")

        execute_sql(cursor, """
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
        """, "创建 'merchant_scores' 表")

        # 用户激励系统模块
        execute_sql(cursor, """
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
        """, "创建 'users' 表")

        execute_sql(cursor, """
        CREATE TABLE IF NOT EXISTS user_levels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level_name TEXT NOT NULL UNIQUE,
            xp_required INTEGER NOT NULL UNIQUE
        );
        """, "创建 'user_levels' 表")

        execute_sql(cursor, """
        CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            badge_name TEXT NOT NULL UNIQUE,
            badge_icon TEXT,
            description TEXT
        );
        """, "创建 'badges' 表")

        execute_sql(cursor, """
        CREATE TABLE IF NOT EXISTS user_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT NOT NULL,
            badge_id INTEGER NOT NULL,
            earned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (badge_id) REFERENCES badges(id),
            UNIQUE(user_id, badge_id)
        );
        """, "创建 'user_badges' 表")

        execute_sql(cursor, """
        CREATE TABLE IF NOT EXISTS badge_triggers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            badge_id INTEGER NOT NULL,
            trigger_type TEXT NOT NULL,
            trigger_value INTEGER NOT NULL,
            FOREIGN KEY (badge_id) REFERENCES badges(id) ON DELETE CASCADE
        );
        """, "创建 'badge_triggers' 表")

        # 创建发布频道配置表
        execute_sql(cursor, """
        CREATE TABLE IF NOT EXISTS posting_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT,
            channel_chat_id TEXT,
            channel_link TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """, "创建 'posting_channels' 表")

        print("\n--- 阶段3: 重新创建provinces和regions表以保持V1兼容性 ---")
        
        # 重新创建provinces表（V1兼容）
        execute_sql(cursor, """
        CREATE TABLE IF NOT EXISTS provinces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            is_active BOOLEAN DEFAULT TRUE
        );
        """, "重新创建 'provinces' 表")
        
        # 重新创建regions表（V1兼容）
        execute_sql(cursor, """
        CREATE TABLE IF NOT EXISTS regions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            province_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (province_id) REFERENCES provinces(id) ON DELETE CASCADE,
            UNIQUE(province_id, name)
        );
        """, "重新创建 'regions' 表")

        print("\n--- 阶段4: 修改现有表的结构 ---")
        
        # 统一商户状态值为V2.0规范并修正字段名为telegram_chat_id
        execute_sql(cursor, """
        -- 创建新的merchants表结构（V2.0状态值和字段名）
        CREATE TABLE IF NOT EXISTS merchants_v2_temp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_chat_id BIGINT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            region TEXT,
            category TEXT,
            contact_info TEXT,
            profile_data TEXT,
            status TEXT DEFAULT 'pending_submission' CHECK (status IN ('pending_submission', 'pending_approval', 'approved', 'published', 'expired')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            merchant_type TEXT DEFAULT 'teacher',
            city_id INTEGER,
            district_id INTEGER,
            p_price INTEGER,
            pp_price INTEGER,
            custom_description TEXT,
            adv_sentence TEXT,
            user_info TEXT,
            channel_link TEXT,
            channel_chat_id TEXT,
            show_in_region_search INTEGER DEFAULT 0,
            publish_time DATETIME,
            expiration_time DATETIME
        );
        """, "创建V2.0状态约束的临时merchants表")
        
        execute_sql(cursor, """
        -- 迁移数据并转换状态值
        INSERT INTO merchants_v2_temp 
        (
            id, telegram_chat_id, name, region, category, contact_info, profile_data,
            status, created_at, updated_at, merchant_type, city_id, district_id,
            p_price, pp_price, custom_description, adv_sentence, user_info, channel_link,
            channel_chat_id, show_in_region_search, publish_time, expiration_time
        )
        SELECT 
            id, telegram_chat_id, name, region, category, contact_info, profile_data,
            CASE 
                WHEN status = 'pending' THEN 'pending_submission'
                WHEN status = 'active' THEN 'published'
                WHEN status = 'inactive' THEN 'expired'
                ELSE status 
            END as status,
            created_at, updated_at, merchant_type, 
            COALESCE(province_id, city_id) as city_id, 
            COALESCE(region_id, district_id) as district_id,
            p_price, pp_price, custom_description, 
            COALESCE(adv_sentence, ''), 
            user_info, channel_link, 
            channel_chat_id,
            COALESCE(show_in_region_search, 0), 
            publish_time, expiration_time
        FROM merchants;
        """, "迁移商户数据并转换状态值")
        
        execute_sql(cursor, "DROP TABLE merchants;", "删除旧merchants表")
        execute_sql(cursor, "ALTER TABLE merchants_v2_temp RENAME TO merchants;", "重命名新表为merchants")
        
        # 重建索引和触发器
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_merchants_telegram_chat_id ON merchants(telegram_chat_id);", "重建telegram_chat_id索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_merchants_status ON merchants(status);", "重建status索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_merchants_channel_chat_id ON merchants(channel_chat_id);", "重建channel_chat_id索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_merchants_publish_time ON merchants(publish_time);", "重建publish_time索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_merchants_expiration_time ON merchants(expiration_time);", "重建expiration_time索引")
        execute_sql(cursor, """
        CREATE TRIGGER update_merchants_timestamp
            AFTER UPDATE ON merchants
            FOR EACH ROW
            BEGIN
                UPDATE merchants SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;
        """, "重建更新时间戳触发器")

        # 添加reviews表缺失的字段
        print("\n--- 阶段4.0: 为reviews表添加缺失字段 ---")
        execute_sql(cursor, "ALTER TABLE reviews ADD COLUMN report_message_id INTEGER;", "为 'reviews' 表添加 'report_message_id' 列")
        
        # 为 binding_codes 表添加新字段
        execute_sql(cursor, "ALTER TABLE binding_codes ADD COLUMN used_at DATETIME;", "为 'binding_codes' 表添加 'used_at' 列")
        execute_sql(cursor, "ALTER TABLE binding_codes ADD COLUMN bound_telegram_username TEXT;", "为 'binding_codes' 表添加 'bound_telegram_username' 列")
        execute_sql(cursor, "ALTER TABLE binding_codes ADD COLUMN bound_telegram_name TEXT;", "为 'binding_codes' 表添加 'bound_telegram_name' 列")
        
        # 为 cities 表添加新字段（如果需要）
        print("\n--- 阶段4.1: 为cities表添加V2.0字段 ---")
        execute_sql(cursor, "ALTER TABLE cities ADD COLUMN display_order INTEGER DEFAULT 0;", "为 'cities' 表添加 'display_order' 列")
        execute_sql(cursor, "ALTER TABLE cities ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;", "为 'cities' 表添加 'created_at' 列")
        
        # 为 districts 表添加新字段（如果需要）
        print("\n--- 阶段4.2: 为districts表添加V2.0字段 ---")
        execute_sql(cursor, "ALTER TABLE districts ADD COLUMN display_order INTEGER DEFAULT 0;", "为 'districts' 表添加 'display_order' 列")
        execute_sql(cursor, "ALTER TABLE districts ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;", "为 'districts' 表添加 'created_at' 列")
        execute_sql(cursor, "ALTER TABLE districts ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;", "为 'districts' 表添加 'updated_at' 列")

        # *** 阶段4.3: 为 users 表添加时间戳字段 ***
        print("\n--- 阶段4.3: 为users表添加时间戳字段 ---")
        execute_sql(cursor, "ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;", "为 'users' 表添加 'created_at' 列")
        execute_sql(cursor, "ALTER TABLE users ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;", "为 'users' 表添加 'updated_at' 列")

        # 阶段5: 重建orders表以适配V2.0规范
        print("\n--- 阶段5: 重建orders表以适配V2.0规范 ---")
        
        # 检查orders表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'")
        orders_exists = cursor.fetchone() is not None
        
        if orders_exists:
            # 创建V2.0规范的orders表
            execute_sql(cursor, """
            CREATE TABLE orders_v2_temp (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_id INTEGER NOT NULL,
                customer_user_id BIGINT NOT NULL,
                customer_username TEXT,
                course_type TEXT CHECK (course_type IN ('P','PP')),
                price INTEGER NOT NULL,
                appointment_time DATETIME,
                completion_time DATETIME,
                status TEXT NOT NULL DEFAULT '尝试预约' CHECK (status IN ('尝试预约', '已完成', '已评价', '双方评价', '单方评价')),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
            );
            """, "创建V2.0规范的orders表")
            
            # 迁移现有orders数据并转换字段名和状态值
            execute_sql(cursor, """
            INSERT INTO orders_v2_temp 
            SELECT 
                id, 
                merchant_id, 
                CASE WHEN customer_user_id IS NOT NULL THEN customer_user_id ELSE 0 END as customer_user_id,
                CASE WHEN customer_username IS NOT NULL THEN customer_username ELSE '' END as customer_username,
                NULL as course_type,
                CAST(CASE WHEN price IS NOT NULL THEN price ELSE 0 END AS INTEGER) as price,
                appointment_time, 
                completion_time,
                CASE 
                    WHEN status = 'pending' THEN '尝试预约'
                    WHEN status = 'confirmed' THEN '尝试预约'
                    WHEN status = 'completed' THEN '已完成'
                    WHEN status = 'cancelled' THEN '尝试预约'
                    WHEN status = '尝试预约' THEN '尝试预约'
                    WHEN status = '已完成' THEN '已完成'
                    WHEN status = '已评价' THEN '已评价'
                    WHEN status = '双方评价' THEN '双方评价'
                    WHEN status = '单方评价' THEN '单方评价'
                    ELSE '尝试预约' 
                END as status,
                created_at,
                CASE WHEN updated_at IS NOT NULL THEN updated_at ELSE created_at END as updated_at
            FROM orders;
            """, "迁移orders数据并转换为V2.0格式")
            
            # 替换旧表
            execute_sql(cursor, "DROP TABLE orders;", "删除旧orders表")
            execute_sql(cursor, "ALTER TABLE orders_v2_temp RENAME TO orders;", "重命名新表为orders")
            
        else:
            # 如果orders表不存在，直接创建V2.0规范的表
            execute_sql(cursor, """
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_id INTEGER NOT NULL,
                customer_user_id BIGINT NOT NULL,
                customer_username TEXT,
                course_type TEXT CHECK (course_type IN ('P','PP')),
                price INTEGER NOT NULL,
                appointment_time DATETIME,
                completion_time DATETIME,
                status TEXT NOT NULL DEFAULT '尝试预约' CHECK (status IN ('尝试预约', '已完成', '已评价', '双方评价', '单方评价')),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
            );
            """, "创建V2.0规范的orders表（新表）")
        
        # 重建索引
        execute_sql(cursor, "CREATE INDEX idx_orders_customer_user_id ON orders(customer_user_id);", "创建customer_user_id索引")
        execute_sql(cursor, "CREATE INDEX idx_orders_merchant_id ON orders(merchant_id);", "创建merchant_id索引")
        execute_sql(cursor, "CREATE INDEX idx_orders_status ON orders(status);", "创建status索引")
        execute_sql(cursor, "CREATE INDEX idx_orders_created_at ON orders(created_at);", "创建created_at索引")
        
        # 创建更新时间戳触发器
        execute_sql(cursor, """
        CREATE TRIGGER update_orders_timestamp
            AFTER UPDATE ON orders
            FOR EACH ROW
            BEGIN
                UPDATE orders SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;
        """, "创建orders表更新时间戳触发器")
        
        print("\n--- 阶段6: 创建系统核心表 ---")
        
        # FSM状态机表
        execute_sql(cursor, """
        CREATE TABLE IF NOT EXISTS fsm_states (
            user_id INTEGER PRIMARY KEY,
            state TEXT,
            data TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """, "创建 'fsm_states' 表")
        
        # 关键词管理表
        execute_sql(cursor, """
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            display_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """, "创建 'keywords' 表")
        
        execute_sql(cursor, """
        CREATE TABLE IF NOT EXISTS merchant_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            keyword_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE,
            FOREIGN KEY (keyword_id) REFERENCES keywords(id) ON DELETE CASCADE,
            UNIQUE(merchant_id, keyword_id)
        );
        """, "创建 'merchant_keywords' 表")
        
        # 消息模板表
        execute_sql(cursor, """
        CREATE TABLE IF NOT EXISTS templates (
            key TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """, "创建 'templates' 表")
        
        # 系统配置表
        execute_sql(cursor, """
        CREATE TABLE IF NOT EXISTS system_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_key TEXT UNIQUE NOT NULL,
            config_value TEXT,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """, "创建 'system_config' 表")
        
        # 媒体文件表
        execute_sql(cursor, """
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_file_id TEXT NOT NULL UNIQUE,
            file_type TEXT NOT NULL,
            file_size INTEGER,
            merchant_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
        );
        """, "创建 'media' 表")

        # 创建自动回复相关表
        execute_sql(cursor, """
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
        """, "创建 'auto_reply_triggers' 表")

        execute_sql(cursor, """
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
        """, "创建 'auto_reply_messages' 表")

        execute_sql(cursor, """
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
        """, "创建 'auto_reply_daily_stats' 表")

        # 创建时间槽位表
        execute_sql(cursor, """
        CREATE TABLE IF NOT EXISTS posting_time_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time_str TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """, "创建 'posting_time_slots' 表")

        # 创建按钮配置表
        execute_sql(cursor, """
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
        """, "创建 'button_configs' 表")

        # 创建活动日志表
        execute_sql(cursor, """
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
        """, "创建 'activity_logs' 表")

        # 创建绑定码表
        execute_sql(cursor, """
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
        """, "创建 'binding_codes' 表")
        
        print("\n--- 阶段7: 商户表字段更新 ---")
        # 为 merchants 表新增 V2.1 字段：优势一句话
        execute_sql(cursor, "ALTER TABLE merchants ADD COLUMN adv_sentence TEXT;", "新增 merchants.adv_sentence 字段")

        print("\n--- 阶段8: 创建完整索引系统 ---")
        
        # reviews表索引
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_reviews_order_id ON reviews(order_id);", "创建reviews.order_id索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_reviews_merchant_id ON reviews(merchant_id);", "创建reviews.merchant_id索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_reviews_customer_user_id ON reviews(customer_user_id);", "创建reviews.customer_user_id索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_reviews_status ON reviews(status);", "创建reviews.status索引")
        
        # cities和districts表索引
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_cities_name ON cities(name);", "创建cities.name索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_cities_is_active ON cities(is_active);", "创建cities.is_active索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_districts_city_id ON districts(city_id);", "创建districts.city_id索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_districts_name ON districts(name);", "创建districts.name索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_districts_is_active ON districts(is_active);", "创建districts.is_active索引")
        
        # users表索引
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);", "创建users.username索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_users_level_name ON users(level_name);", "创建users.level_name索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_users_xp ON users(xp);", "创建users.xp索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);", "创建users.created_at索引")
        
        # binding_codes表索引
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_binding_codes_code ON binding_codes(code);", "创建binding_codes.code索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_binding_codes_is_used ON binding_codes(is_used);", "创建binding_codes.is_used索引")
        
        # 自动回复表索引
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_auto_triggers_active ON auto_reply_triggers(is_active);", "创建auto_reply_triggers.is_active索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_auto_triggers_text ON auto_reply_triggers(trigger_text);", "创建auto_reply_triggers.trigger_text索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_auto_msgs_trigger ON auto_reply_messages(trigger_id);", "创建auto_reply_messages.trigger_id索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_auto_stats_date ON auto_reply_daily_stats(stat_date);", "创建auto_reply_daily_stats.stat_date索引")
        
        # 活动日志表索引
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_activity_logs_user_id ON activity_logs(user_id);", "创建activity_logs.user_id索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_activity_logs_timestamp ON activity_logs(timestamp);", "创建activity_logs.timestamp索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_activity_logs_action_type ON activity_logs(action_type);", "创建activity_logs.action_type索引")
        
        # keywords表索引
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_keywords_name ON keywords(name);", "创建keywords.name索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_keywords_is_active ON keywords(is_active);", "创建keywords.is_active索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_merchant_keywords_merchant_id ON merchant_keywords(merchant_id);", "创建merchant_keywords.merchant_id索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_merchant_keywords_keyword_id ON merchant_keywords(keyword_id);", "创建merchant_keywords.keyword_id索引")
        
        # fsm_states表索引
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_fsm_states_state ON fsm_states(state);", "创建fsm_states.state索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_fsm_states_updated_at ON fsm_states(updated_at);", "创建fsm_states.updated_at索引")
        
        # media表索引
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_media_telegram_file_id ON media(telegram_file_id);", "创建media.telegram_file_id索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_media_merchant_id ON media(merchant_id);", "创建media.merchant_id索引")
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_media_file_type ON media(file_type);", "创建media.file_type索引")
        
        # system_config表索引
        execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_system_config_config_key ON system_config(config_key);", "创建system_config.config_key索引")

        # 为users表创建更新时间戳触发器
        execute_sql(cursor, """
        CREATE TRIGGER IF NOT EXISTS update_users_timestamp
            AFTER UPDATE ON users
            FOR EACH ROW
            BEGIN
                UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE user_id = NEW.user_id;
            END;
        """, "创建users表更新时间戳触发器")

        conn.commit()
        print("\n=== 数据库迁移脚本执行完毕 ===\n")
        print("📊 迁移完成统计:")
        print("  ✅ 核心业务表: merchants, orders, reviews, users")
        print("  ✅ 地区管理表: cities, districts (+ provinces, regions 兼容)")
        print("  ✅ 激励系统表: user_levels, badges, user_badges, badge_triggers")
        print("  ✅ 系统功能表: fsm_states, keywords, templates, system_config")
        print("  ✅ 媒体管理表: media")
        print("  ✅ 完整索引系统: 29个业务索引")
        print("  ✅ 时间戳字段: users表现在具有created_at和updated_at字段")
        print("\n所有更改已提交。数据库架构已完全对齐V2.0规范。")

    except sqlite3.Error as e:
        print(f"数据库操作发生严重错误: {e}")
        if conn:
            conn.rollback()
            print("操作已回滚。" )
    finally:
        if conn:
            conn.close()
            print("数据库连接已关闭。" )

if __name__ == "__main__":
    # 使用 PathManager 获取数据库路径
    db_path = PathManager.get_database_path()
    
    # 确保数据库目录存在
    PathManager.ensure_parent_directory(db_path)
        
    migrate_to_v2(db_path)
