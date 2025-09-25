# Bot 架构与统一 HTTP 审计

结论分级：C（统一 HTTP 入口未完成；生产编排存在错配）

## 现状
- 机器人：`bot.py`（aiogram，支持 webhook 与 polling，两者二选一）。
- 组合应用：`create_webhook_app()` 试图用 aiohttp 同时承载 Bot Webhook 与 Web 面板，但将 ASGI 的 `web.app` 作为 aiohttp 子应用挂载，这是不兼容的。
- 生产入口：`main.py` 为 ASGI Web 入口（仅 Web）；`run.py` 在某些分支会以“Bot 进程”方式启动 `main.py`（错误）。

## 风险
- 无法在同一端口统一对外；不同环境与模式下行为不一致；
- 误把 Web 进程当作 Bot 进程启动，导致 Bot 未对外服务。

## 建议（两条路线，择一落地）
1) ASGI 统一（推荐）
- 将 Bot Webhook 以 ASGI 端点形式暴露（可采用 aiogram v3 的 webhooks + Starlette/ASGI 集成，或通过 `asgiref.wsgi_to_asgi`/适配层）
- 在 `asgi_app.py` 中统一装配：`/bot{token}` → Bot Webhook，`/` → Web 管理面板。
- 优点：栈统一，部署简单，`uvicorn` 单进程即可承载。

2) aiohttp 统一
- 将 Web 面板通过适配器转换为 aiohttp 子应用（需选型稳定的 ASGI→aiohttp 适配库，维护成本高）。
- 不推荐，生态与调试成本较大。

## 运行编排修正
- `run.py`：
  - 生产：只保留一种启动方式（建议直接调用 `main.py`，其内启动统一 ASGI 应用）；
  - 非生产：`start_bot()` 应启动 `bot.py`（而非 `main.py`）。

## 其他
- 错误处理/限流/日志：`middleware` 已接入，建议在 Webhook 模式下补健康检查统一路由 `/health`。

