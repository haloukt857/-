# 商家管理（Bot 绑定 + 资料收集 + Web 帖子）审计

结论分级：B（实现完整；文件体量大，多职责；建议分层与解耦）

## 数据库对齐
- 表：`merchants`（V2 字段齐全，包括地区、价格、生命周期状态等）、`media`（Telegram file_id，排序）、`merchant_scores`（评分聚合）。
- 绑定码：`binding_codes` 使用统一字段 `merchant_id`（符合 V2 统一标准）。

## Bot 端实现对齐
- 绑定流程：`handlers/merchant.py`（体量大）+ `database/db_merchants.py`；
  - 通过绑定码创建永久商户 ID；
  - FSM 引导资料收集（文本/媒体/地区/价格等）；
  - 最终提交置为 `pending_approval`；
  - 管理员通知/审核入口（与 Web 配合）。

## Web 面板对齐
- 帖子/商家管理集中在 `web/routes/posts.py`（体量 ~1000 行）与对应 services；
- 具备列表/详情/状态流转/审核/发布/过期/延长等动作。

## 唯一路径/唯一方法/唯一链路
- 唯一装配：是（Web 路由集中 `web/app.py`）；
- DB 链路：是（`db_manager`）；
- 冗余与重复：
  - 业务与 UI/格式化耦合在 `handlers/merchant.py`、`web/routes/posts.py` 等大文件；
  - 建议将“资料校验/状态机/媒体处理/通知”拆分为独立服务模块，Web 与 Bot 共用。

## 风险与建议
- 文件拆分：`handlers/merchant.py`、`database/db_merchants.py` 过大，建议拆分为（商家基础/媒体/状态流转/审批）子模块；
- 资料一致性：“地区/价格/媒体”等字段的校验规则集中到服务层单处；
- 媒体代理：`/media-proxy/{id}` 注意鉴权与防滥用；建议在响应头设置 Cache-Control 与限速。

