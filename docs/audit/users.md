# 用户中心（/users, /users/analytics）审计

结论分级：A（实现与文档一致，统计口径清晰；有轻微一致性建议）

## 数据库对齐
- 表：`users`, `user_levels`, `badges`, `user_badges`, `badge_triggers`。
- 说明：采用“users.badges JSON + user_badges 关联表”双轨设计；统计与明细可分别取数。

## 后端实现对齐
- DB 层：`database/db_users.py: UserManager` 使用 `db_manager`；
  - 分页/筛选/搜索、统计、详情（含订单/评价聚合）。
- Service：`web/services/user_mgmt_service.py` 汇总 `users`、`levels`、统计和分页，供路由使用。

## Web 面板对齐
- 装配：`web/app.py` 注册 `/users`、`/users/analytics`、`/users/analytics-data`；
- 视图：`web/routes/users.py`, `web/routes/user_analytics.py`；
  - 列表：等级/搜索/每页筛选、导出、分页信息、表格含“订单数/勋章数/详情链接”；
  - 详情：基本信息、勋章、统计卡片；
  - 分析：图表与 JSON API（与旧版对齐）。

## Bot 端对齐
- 相关统计在 `handlers/statistics.py` 另有实现（用于管理员对话输出）。

## 唯一路径/唯一方法/唯一链路
- 唯一装配：是。
- DB 链路：是（`db_manager`）。
- 重复逻辑：统计口径在 Web service 与 Bot statistics 有并行实现（建议后续合并为统一统计服务）。

## 风险与建议
- 统计统一：将核心统计口径（活跃、积分、等级分布）抽到 `web/services/analytics_service.py`，Bot 与 Web 复用，避免口径漂移。
- 导出安全：CSV 导出当前使用 UTF-8 BOM 友好 Excel，注意大规模导出限流与鉴权（已 @require_auth）。

