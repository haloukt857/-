# Web 装配与合规性审计

结论：总体符合《AGENTS 指南》强制约定；个别历史文件需归档。

## 唯一装配点
- 现状：`web/app.py` 统一注册路由，`asgi_app.py` 仅导入 `web.app`。
- 检查项：未发现路由在其他位置挂载或通过 Starlette `Mount` 再次装配页面（仅静态文件挂载，合理）。

## 唯一布局来源
- 现状：所有路由仅从 `web/layout.py` 导入 `create_layout/require_auth/okx_*`；
- 检查项：未发现路由从 `web.app` 反向导入上述内容。

## 唯一路径
- 现状：每个 URL 在 `web/app.py` 注册一次；出现“重复路径”为 GET/POST 配对（编辑页面），符合预期；
- 建议：将仍在仓库中的 `*_v2.py`、`*_analytics.py` 标记为 `.old` 或移入 `docs/archive/`，以消除装配歧义。

## 其他合规项
- 认证：`@require_auth` 已覆盖管理端路由；
- 三层架构：Route 仅做参数解析与调用 Service；Service 调 DB；UI 纯渲染（大体符合）。

## 待改进
- CSRF：除 `/regions` 外，其余 POST 动作建议统一接入 CSRF；
- 统计口径：集中在 `web/services/analytics_service.py`，减少跨端重复实现。

