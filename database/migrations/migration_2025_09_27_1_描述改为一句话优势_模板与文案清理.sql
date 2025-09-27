-- migration_2025_09_27_1_描述改为一句话优势_模板与文案清理.sql
-- 描述: 将“描述”统一替换为“一句话优势”，更新模板占位符与文案；新增 adv_sentence_input 模板键。
-- 前置版本: 2025.09.25.1 或更早
-- 目标版本: 2025.09.27.1

-- 更新 merchant_info_template：用 adv_sentence 替换 custom_description
UPDATE templates SET content = '📋 {name} ({merchant_type})\n\n📍 地区: {province} - {region}\n💰 价格: P{p_price} | PP{pp_price}\n\n📝 一句话优势: {adv_sentence}\n\n🏷️ 特色标签: {keywords}\n\n📞 联系方式: {contact_info}'
WHERE key = 'merchant_info_template';

-- 更新 binding_confirmation：用 “一句话优势: {adv_sentence}” 替换 “描述: {description}”
UPDATE templates SET content = '✅ 注册信息确认\n\n请确认以下信息是否正确：\n\n👤 商户类型: {merchant_type}\n📍 地区: {province} - {region}\n💰 P价格: ¥{p_price}\n💎 PP价格: ¥{pp_price}\n📝 一句话优势: {adv_sentence}\n🏷️ 关键词: {keywords}\n\n🔍 用户检测结果: {user_analysis}\n\n确认无误请点击"确认注册"，需要修改请点击"重新填写"。'
WHERE key = 'binding_confirmation';

-- 将 custom_description_input 内容替换为“一句话优势”提示（兼容保留旧键）
UPDATE templates SET content = '📝 步骤 6/7: 一句话优势\n\n请输入你的一句话优势（建议≤30字）：\n\n💡 填写建议：\n• 用简短话语突出核心优势\n• 避免长段落与联系方式\n• 不超过30字\n• 将在频道贴文首行展示'
WHERE key = 'custom_description_input';

-- 新增 adv_sentence_input 键（若不存在）
INSERT OR IGNORE INTO templates (key, content) VALUES (
  'adv_sentence_input',
  '📝 步骤 6/7: 一句话优势\n\n请输入你的一句话优势（建议≤30字）：\n\n💡 填写建议：\n• 用简短话语突出核心优势\n• 避免长段落与联系方式\n• 不超过30字\n• 将在频道贴文首行展示'
);

-- 写入 schema 版本
INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2025.09.27.1', '描述改为一句话优势：模板与文案清理');

