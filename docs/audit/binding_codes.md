# 绑定码（/binding-codes）审计

结论分级：A（V2 唯一链路落地良好；建议补齐 CSRF）

## 数据库对齐
- 表：`binding_codes`（统一 `merchant_id` 字段；唯一 `code`；过期时间/使用标记/使用者信息）。

## 后端实现对齐
- DB 层：`database/db_binding_codes.py: binding_codes_manager`（唯一标准接口）。
- 路由：`web/routes/binding_codes.py` 明确遵循“Route → DB Manager”，不引入 Service 层（与文档一致）。

## Web 面板对齐
- 列表/详情/生成/删除/导出齐全；
- Ajax 删除/生成等 POST 操作当前未含 CSRF（建议补齐）。

## Bot 端对齐
- 管理员命令可生成绑定码；商家通过 `/bind` 使用绑定码进入资料流程。

## 唯一路径/唯一方法/唯一链路
- 唯一装配：是；
- 唯一链路：是（Route → DB Manager）。

## 风险与建议
- 安全：对 POST 加 CSRF；生成接口加最小频率限制（管理员侧节流）。
- 一致性：导出字段与 DB 命名（`merchant_id`）已统一，保持此标准。

