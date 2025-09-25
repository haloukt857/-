# 订单管理（/orders）审计

结论分级：A（实现与文档一致，批量/导出齐全；建议补齐 CSRF）

## 数据库对齐
- 表：`orders`（V2 五态：尝试预约/已完成/已评价/双方评价/单方评价）。
- 外键：`merchant_id` → `merchants(id)`；索引 `customer_user_id/merchant_id/created_at` 已建。

## 后端实现对齐
- DB 层：`database/db_orders.py: OrderManager`
  - 创建/查询（按商户/按用户/时间范围）/分页统计/收入统计。
- Service：`web/services/order_mgmt_service.py`
  - 汇总筛选（状态/商户/用户/日期/搜索）、分页、统计（含今日）、TOP 商户等。

## Web 面板对齐
- 装配：`web/app.py` 注册列表/详情/状态更新/批量操作/导出。
- 视图：`web/routes/orders.py`：
  - 筛选：状态/商户/用户/日期、分页；
  - 批量：完成/标记评价/取消/导出；
  - 导出：CSV（含商户名、用户、时间戳）。
- 安全：多数 POST 暂未覆盖 CSRF（建议补齐）。

## Bot 端对齐
- 订单创建/通知流程在 Bot 端已实现；商户侧状态更新对接 Web 管理端。

## 唯一路径/唯一方法/唯一链路
- 唯一装配：是。
- DB 链路：是（`db_manager`）。
- 重复逻辑：订单分析在 `handlers/statistics.py` 与 Web service 并行存在（建议合并）。

## 风险与建议
- CSRF：对 `/orders/{id}/update_status`、`/orders/batch` 等 POST 加 CSRF；
- 状态字典：`STATUS_DISPLAY_MAP` 与 DB 校验列表保持一处来源（单一常量/枚举）。

