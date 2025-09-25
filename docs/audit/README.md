# 架构与一致性审计（V2 基线）

本审计基于 `docs/` 与 `docs/modules/` 的初始设计，以及当前代码实现（截至本次检查的仓库快照）。目标是：
- 按功能模块核对“数据库 → 后端实现 → Web 管理面板 → Bot 端交互”一致性；
- 排查“唯一路径/唯一方法/唯一数据库链路”是否成立；
- 标注潜在架构风险、冗余路径与“上帝文件”；
- 给出可执行的分阶段修复建议（不改现有代码，仅罗列问题与建议）。

## 审计总览（按模块分级）
- A 级（对齐良好，建议优化不影响闭环）
  - 地区管理（/regions）
  - 用户中心（/users + /users/analytics）
  - 订单管理（/orders + 批量 + 导出）
  - 评价管理（/reviews）
  - 绑定码（/binding-codes）
  - 关键词（DB + Bot 管理对话）
- B 级（基本对齐，存在中风险或重复逻辑）
  - 商家管理（DB/对话齐全，Web 端集中在帖子管理）
  - 帖子管理（/posts，体量较大，建议拆分 UI/动作）
  - 激励系统（统计口径与使用“badges JSON + user_badges 表”需统一说明）
  - 模板/媒体代理（/templates, /media-proxy）
- C 级（需要优先修复的架构一致性问题）
  - 统一 HTTP/唯一路径：Bot 与 Web 的“单一 HTTP 入口”未完成统一；存在历史 v2 路由文件未挂载但保留，易混淆。
  - 运行编排：生产路径与组合应用存在错配（详见“重大问题”）。
  - CSRF 一致性：仅少数表单启用 CSRF，其余 POST 操作缺失 CSRF 保护。

## 重大问题（需优先确认与修复）
1) 单一 HTTP 入口未达成（与 Telegram 官方建议不符）
- 现状：
  - `main.py` 基于 ASGI 仅承载 Web 管理面板（FastHTML/Starlette）。
  - `bot.py` 提供 `create_webhook_app()`（aiohttp）并尝试 `add_subapp('/admin', web_app)` 挂载 Web 面板。
  - 但 `web.app` 为 ASGI 应用，不可直接作为 aiohttp 子应用挂载，组合应用路径不可用。
  - `asgi_app.py` 仅返回 Web 应用，不含 Bot webhook。
- 风险：
  - 无法在同一 HTTP 服务端口统一对外暴露 Bot Webhook 与 Web 面板；
  - dev/prod 两种启动方式下行为不一致，易导致环境差异问题。
- 建议：
  - 选型其一并贯通：
    - 方案 A（推荐）ASGI 统一：将 Bot Webhook 暴露为 ASGI 路由（利用 aiogram/anyio 兼容或通过 asgiref 适配），由 `asgi_app.py` 统一装配；
    - 方案 B aiohttp 统一：将 Web 面板通过 `asgi-to-aiohttp` 适配器（需评估）适配为 aiohttp 子应用，但生态与维护成本更高。

2) 生产运行路径错配（潜在“双 Web”进程）
- 现状：
  - `run.py` 在某些生产路径（非 Railway 环境）会通过 `start_bot()` 启动 `main.py` 作为“Bot 进程”，同时 `start_web()` 再启动基于 `asgi_app` 的 Web 服务；
  - 等价于两个 Web 进程并存，且 Bot 未真正启动。
- 风险：
  - 端口、日志、健康检查与优雅关闭混乱；
  - Bot 服务未真正对外（业务中断）。
- 建议：
  - 固化生产路径：
    - Railway/云环境：统一走 `main.py`，其内整合 Bot Webhook 与 Web；
    - 非云环境：`run.py` 仅做编排，但启动的“Bot 进程”必须是 `bot.py`（使用 webhook 或 polling），Web 由 `asgi_app.py`/`web.app` 单实例提供；
  - 清理 `start_bot()` 中错误的 `cmd = [sys.executable, 'main.py']`。

3) CSRF 保护覆盖不足
- 现状：`/regions` 已引入 CSRF；`/binding-codes` 删除/生成、`/posts` 多个 POST、`/orders` 状态更新与批量操作、`/reviews` 导出/动作等未统一加 CSRF。
- 风险：跨站请求伪造影响后台安全。
- 建议：
  - 统一在 `web/layout.py` 暴露 `get_or_create_csrf_token/validate_csrf`；
  - 所有 POST 表单与 fetch 请求增加 CSRF 头/隐藏字段校验；
  - 在 `web/app.py` 中可加一个全局 `CSRFMiddleware`（如保持轻量，则按路由逐步补齐）。

4) 历史 v2 路由文件保留但未挂载（易混淆“唯一路径”）
- 文件：`web/routes/users_v2.py`, `web/routes/reviews_v2.py`, `web/routes/subscription_v2.py`, `web/routes/order_analytics.py`, `web/routes/subscription_analytics.py` 等。
- 现状：未在 `web/app.py` 注册，但仍在仓库；部分 tests/logs 曾引用，存在心智负担。
- 建议：重命名为 `.old` 或迁移到 `docs/archive/`，并在 README 中标注“当前无效实现，避免误用”。

## 上帝文件（体量过大且多职责）
- handlers/statistics.py（~1600 行）
- database/db_merchants.py（~1500 行）
- handlers/merchant.py（~1400 行）
- handlers/admin.py（~1300 行）
- web/routes/posts.py（~1000 行）
- database/db_init.py（~1000 行）
- database/db_orders.py（~900 行）
- 特征：业务聚合 + 文本格式化 + 兼容逻辑交织，难以测试与演进。
- 建议：
  - 以“领域服务/查询服务/格式化呈现”拆分；
  - 将通用统计/分析逻辑上移到 `web/services/*`（供 Web 与 Bot 共用），Bot 端仅做格式化与路由；
  - db_* 模块按“实体 + 查询（只读）/命令（写入）”拆分，降低事务域耦合。

## 唯一路径/唯一方法/唯一数据库链路审计
- 唯一装配点：符合。`web/app.py` 统一注册路由；`asgi_app.py` 仅导入 `web.app`。
- 唯一布局来源：符合。路由仅从 `web/layout.py` 导入 `create_layout/require_auth/okx_*`。
- 唯一路径：基本符合。重复路径仅为 GET/POST 配对（同一实现的不同方法）。历史 v2 文件应归档以杜绝歧义。
- 唯一数据库链路：基本符合。生产代码均通过 `database/db_connection.py: db_manager`；旧 `.old` 文件与 tests 中直连 sqlite 属允许范围。

## 模块审计索引
- 参见本目录下各模块审计文档：
  - regions.md（地区管理）
  - users.md（用户中心）
  - orders.md（订单管理）
  - reviews.md（双向评价）
  - merchants.md（商家/绑定流程）
  - binding_codes.md（绑定码）
  - subscription.md（频道订阅验证）
  - posts.md（帖子管理）
  - incentives.md（激励/等级/勋章）
  - templates_media.md（模板与媒体代理）
  - keywords.md（关键词）
  - web_architecture.md（Web 装配合规性）
  - bot_architecture.md（Bot/统一 HTTP 架构）
  - god_files.md（上帝文件清单与拆分建议）

## 下一步建议（不改代码，仅规划）
- 优先：统一生产运行路径与组合方式（单一 HTTP 入口），明确 dev/prod 行为一致性；
- 第二：对所有后台写操作补齐 CSRF；
- 第三：归档未挂载的 v2 路由文件为 `.old`；
- 第四：将统计/分析口径集中到 `web/services/*`，Bot 端共用；
- 第五：分期拆分上帝文件，补最小必要的单元测试（已有 `pytest` 基线）。

