-- 迁移：更新 user_profile_card 模板为纵向信息卡样式

UPDATE templates
SET content = '👤 {username}    {level_name}\n═══════════════════════════\n\n    📊 成长值\n    🔥 XP: {xp}    💰 积分: {points}\n\n    🏆 战绩: {order_count} 胜\n\n    🏅 勋章: {badges_text}\n\n═══════════════════════════'
WHERE key = 'user_profile_card';

