# 地区管理（/regions）审计

结论分级：A（实现与文档高度一致，细节建议不影响闭环）

## 数据库对齐
- 表：`cities`, `districts`（与 docs/modules/11-地区管理模块.md、database/schema.sql 完全一致）。
- 约束：`districts` 唯一键 `(name, city_id)`、外键 ON DELETE CASCADE 已体现在 schema。

## 后端实现对齐
- DB 层：`web/services/region_mgmt_service.py` 统一封装查询/增删改；使用 `db_manager`（唯一数据库链路）。
- 关键方法：列表加载（含缓存）、新增/编辑/删除、状态 toggle、显示顺序。

## Web 面板对齐
- 装配：`web/app.py` 注册唯一路由集；
- 视图：`web/routes/regions.py`
  - 列表页：城市/区县层级展示，统计卡片；
  - 新增/编辑（GET+POST）/删除：与文档一致；
  - 状态切换：`/regions/city/{id}/toggle`、`/regions/district/{id}/toggle`；
  - 反馈：通过 URL 参数 `city_added`/`district_updated` 等。
- 安全：已引入 `get_or_create_csrf_token/validate_csrf`，表单含 CSRF（正向样例）。

## Bot 端对齐
- 地区数据用于商家资料/帖子管理的地区选择（来源统一）。

## 唯一路径/唯一方法/唯一链路
- 唯一装配：是（集中在 `web/app.py`）。
- GET/POST 配对：是（编辑页配对，不重复实现）。
- DB 链路：是（仅经 `db_manager`）。

## 风险与建议
- CSRF 一致性：本模块已做；建议将其作为全站 POST 的统一做法。
- 可观测性：列表大时分页/筛选性能可继续通过服务层缓存优化（已有基础）。

