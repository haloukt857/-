-- 添加 orders.course_type 字段，用于标记 P / PP 课程类型

-- 向前迁移 (UP)
ALTER TABLE orders ADD COLUMN course_type TEXT CHECK (course_type IN ('P','PP'));

-- 为老数据设置默认空值，不强制回填

-- 向后迁移 (DOWN)
-- SQLite 不支持直接 DROP COLUMN，如需回滚需重建表结构，此处留空

