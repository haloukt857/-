-- 为评价报告记录 message_id 字段（频道消息ID）
-- 说明：本迁移不使用事务/PRAGMA，允许分句执行并忽略“duplicate column name”错误

ALTER TABLE reviews ADD COLUMN report_message_id INTEGER;
ALTER TABLE merchant_reviews ADD COLUMN report_message_id INTEGER;
