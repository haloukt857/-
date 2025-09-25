-- 清理历史模板键（统一采用 user_* 标准）
-- 说明：删除已淘汰的 welcome_private，避免与新标准并存

DELETE FROM templates WHERE key = 'welcome_private';

