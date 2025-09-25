# 关键词模块审计

结论分级：A（V2 管理器落地，Bot 管理对话对齐）

## 数据库对齐
- 表：`keywords`、`merchant_keywords`；
- 索引：`keywords.name` 唯一/状态索引、`merchant_keywords` 关联索引齐全。

## 后端实现对齐
- DB：`database/db_keywords.py`（V2，统一走 `db_manager`）。
- 扩展：`KeywordManagerExtended` 提供分页/启用禁用/热门关键词等，供管理员对话使用。

## Web/ Bot 对齐
- Web：暂未提供独立页面（在商家对话内选择使用）；
- Bot：`dialogs/admin_keyword_management.py` 完整的 CRUD/分页/统计对话流。

## 唯一路径/唯一方法/唯一链路
- 唯一链路：是；历史 `.old` 文件已隔离且未被引用。

## 风险与建议
- 分类：当前返回“未分类”，如需分类可扩展表结构与 UI；
- 业务耦合：与商家标签的呈现建议统一由服务层合成，避免在多处重复拼装文本。

