# 双向评价（/reviews）审计

结论分级：A（与文档一致，口径清晰；建议补齐 CSRF）

## 数据库对齐
- 表：`reviews`（一单一评，用户→商家五维评分，商家确认 `is_confirmed_by_merchant`）、`merchant_scores` 聚合表。
- 触发与统计：日更或按需计算聚合分数（由定时任务/服务触发）。

## 后端实现对齐
- DB 层：`database/db_reviews.py: ReviewManager`（创建、查询、确认、聚合刷新）。
- Service：`web/services/review_mgmt_service.py`（从旧版抽取，供 Web 端使用）。

## Web 面板对齐
- 装配：`web/app.py` 注册列表/详情/导出；
- 视图：`web/routes/reviews.py`（筛选：状态/商户/确认/日期/每页/搜索；分页/导出）。
- 安全：POST/导出缺少 CSRF（建议补齐）。

## Bot 端对齐
- 用户评价交互与商家确认在 Bot 端已实现；确认成功后触发激励发放与聚合更新。

## 唯一路径/唯一方法/唯一链路
- 唯一装配：是。
- DB 链路：是（`db_manager`）。
- 旧版 v2 文件：`reviews_v2.py` 存在但未挂载（建议归档为 `.old`）。

## 风险与建议
- 分数口径：聚合维度与权重如有调整，应集中在单处常量/服务；
- CSRF：详情页内的动作（如确认/撤销）走 POST 的统一校验。

