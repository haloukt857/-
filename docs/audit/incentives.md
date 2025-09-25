# 激励/等级/勋章审计

结论分级：B（实现完整；双轨存储需明示口径；统计共用建议上移）

## 数据库对齐
- 表：`user_levels`, `badges`, `user_badges`, `badge_triggers`；
- `users.badges` JSON 作快速读取缓存，与 `user_badges` 并存（设计允许）。

## 后端实现对齐
- DB 层：`database/db_incentives.py` 提供勋章/触发器 CRUD、统计口径（基于 `user_badges`）。
- 与用户/评价联动：
  - 订单完成/评价确认后触发积分/经验与勋章检查（分散在相关服务内）。

## Web/ Bot 对齐
- Web：统计卡片/分析使用 `web/services/analytics_service.py` 汇总；
- Bot：管理员统计在 `handlers/statistics.py` 内亦有口径实现。

## 唯一路径/唯一方法/唯一链路
- 唯一装配：是；
- DB 链路：是；
- 重复：统计口径在 Web 与 Bot 各自实现（建议合并为单一 Analytics 服务）。

## 风险与建议
- 口径统一：明确“用户是否拥有勋章”的判定以 `user_badges` 为准，`users.badges` 作为展示缓存并提供修复任务；
- 异步一致性：在订单/评价事件后触发的勋章检查建议集中到单一 UseCase/Service；
- 可观测性：增加统一的勋章触发日志，便于排查。

