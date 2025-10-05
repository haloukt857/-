-- 订阅验证提示模板初始化
-- 模板键：subscription_verification_prompt
-- 使用说明：支持 {channels_text} 变量（以换行分隔的频道名称列表）

INSERT OR IGNORE INTO templates (key, content, updated_at)
VALUES (
  'subscription_verification_prompt',
  '❌ 您需要先关注以下频道才能继续：\n\n{channels_text}\n\n关注完成后点击下方“✅ 我已加入”进行验证。',
  CURRENT_TIMESTAMP
);

