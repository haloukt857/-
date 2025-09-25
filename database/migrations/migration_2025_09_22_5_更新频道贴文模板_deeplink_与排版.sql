-- migration_2025_09_22_5_更新频道贴文模板_deeplink_与排版.sql
-- 描述: 按最新规范更新频道贴文模板：首行显示优势句，课费使用可点击的 {price_p_html}/{price_pp_html}，
--       地区仅显示区名并带deeplink，昵称/标签/报告均为deeplink；保持与调度器生成参数完全一致。

BEGIN TRANSACTION;

UPDATE templates 
SET content = '{adv_html}\n\n💃🏻昵称：{nickname_html}\n🌈地区：{district_html}\n🎫课费：{price_p_html}      {price_pp_html}\n🏷️标签：{tags_html}\n✍️评价：「{report_html}」\n\n🎉优惠：{offer_html}'
WHERE key = 'channel_post_template';

COMMIT;

INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2025.09.22.5', '更新频道贴文模板(adv/价格deeplink/排版)');

