# 帖子管理（/posts）审计

结论分级：B（功能完整但文件体量大；建议拆分与加强安全）

## 数据库对齐
- 主要依赖 `merchants` 与 `media`，结合状态流转（pending_approval/approved/published/expired）。

## 后端实现对齐
- Service：`web/services/post_mgmt_service.py`；
- 路由：`web/routes/posts.py`（~1000 行，含大量 UI 与动作处理）。

## Web 面板对齐
- 列表/详情/编辑/审核/发布/驳回/删除/延长/过期 多动作俱全；
- 多数 POST 暂缺 CSRF 校验（建议补齐）。

## 唯一路径/唯一方法/唯一链路
- 唯一装配：是；
- DB 链路：是（经 services→db_*→db_manager）。

## 风险与建议
- 文件拆分：将 UI 构建、动作处理、查询封装拆分为多个小模块；
- 权限校验：管理动作统一使用 `@require_auth`（已覆盖），并在服务层做细粒度检查；
- 媒体代理：对 `/media-proxy/{media_id}` 增加权限/速率限制与缓存头；
- CSRF：为所有 POST 表单与 fetch 动作增加 CSRF。

