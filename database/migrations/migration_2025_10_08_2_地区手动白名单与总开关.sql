-- 地区手动白名单表
CREATE TABLE IF NOT EXISTS region_manual_whitelist (
    merchant_id INTEGER PRIMARY KEY,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
);

-- 开关写入（默认关闭）
INSERT OR IGNORE INTO system_config (config_key, config_value, description)
VALUES ('manual_region_gate_enabled', 'false', '启用机器人地区搜索白名单');

-- 版本更新
INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2025.10.08.2', '新增地区手动白名单与总开关');

