# “上帝文件”清单与拆分建议

目标：降低单文件职责与复杂度，提升可测试性与演进效率。

## 清单（行数统计 Top）
- handlers/statistics.py（~1600）
- database/db_merchants.py（~1500）
- handlers/merchant.py（~1400）
- handlers/admin.py（~1300）
- web/routes/posts.py（~1000）
- database/db_init.py（~1000）
- database/db_orders.py（~900）

## 拆分策略（示例）
- 按“查询/命令”拆分 DB 层：
  - db_merchants_query.py（只读，列表/详情/聚合）；
  - db_merchants_command.py（写入，创建/更新/状态流转）。
- 按“领域用例”拆分 Service 层：
  - merchant_profile_service.py、merchant_media_service.py、merchant_status_service.py；
- 将统计/分析统一到 analytics_service：
  - Web 与 Bot 共用，Bot 端仅做格式化；
- 路由与 UI 拆分：
  - posts_list_view.py、posts_actions.py、posts_components.py（表单/卡片组件）。
- 初始化器拆分：
  - db_init_core.py（核心表）、db_init_auto_reply.py（自动回复）、db_init_regions.py（地区）…

## 优先级建议
1) 运行路径问题修复（统一 HTTP 与 run.py 错配）后，优先拆 `handlers/statistics.py` 与 `web/routes/posts.py`；
2) 将订单/评价/用户核心统计上移至 `web/services/analytics_service.py`；
3) 分期为每个拆分单元补最小必要测试（遵循现有 pytest 结构）。

