# 频道订阅验证（/subscription）审计

结论分级：B（功能完整；存在历史 v2 文件冲突风险）

## 数据库/配置对齐
- 配置：`system_config.subscription_verification_config`（JSON），包含 `enabled` 与 `required_subscriptions` 列表。

## 后端实现对齐
- 中间件：`handlers/subscription_guard.py`（Bot 端强制校验，管理员豁免）；
- Web：`web/routes/subscription.py` 提供后台配置面板；
- 存在历史：`web/routes/subscription_v2.py` 与 `subscription_analytics.py` 未挂载但保留。

## 唯一路径/唯一方法/唯一链路
- 唯一装配：是（仅 `/subscription` 挂载）；
- 冗余：`*_v2.py` 建议归档为 `.old` 以避免误导。

## 风险与建议
- 配置缓存：可通过 `web/services/subscription_mgmt_service.py` 统一缓存/刷新策略；
- 统计：订阅分析口径建议沉淀至 analytics service，Bot/Web 共用。

