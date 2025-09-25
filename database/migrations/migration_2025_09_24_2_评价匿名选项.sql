-- 为评价系统新增匿名选项字段

PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

-- u2m：用户匿名标记
ALTER TABLE reviews ADD COLUMN is_anonymous BOOLEAN NOT NULL DEFAULT 0;

-- m2u：对用户匿名标记（商户匿名不生效，此处统一匿名保护用户）
ALTER TABLE merchant_reviews ADD COLUMN is_user_anonymous BOOLEAN NOT NULL DEFAULT 0;

COMMIT;
PRAGMA foreign_keys=ON;

