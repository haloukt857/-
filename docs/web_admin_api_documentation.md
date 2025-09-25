# Web管理后台路由功能文档 (V2.0)

**文档状态**: 当前启用 (202509181800)  
**最后更新**: 2025年9月18日 18:00  
**版本**: V2.0 正式版

## 概述

本文档描述了Web管理后台（一个基于FastHTML的整体应用）所暴露的服务器端路由（Endpoints）及其功能。这些路由是浏览器通过GET/POST请求与服务器交互的接口，它们直接返回HTML内容或执行后台操作，而非为独立前端提供JSON数据。

## 技术栈
- **框架**: FastHTML + Starlette
- **数据库**: SQLite + 异步操作
- **认证**: Session基础认证

---

## API接口详细说明

### 1. 认证相关API
(无变化)
- `GET /login`: 登录页面。
- `POST /login`: 登录验证。
- `GET /logout`: 登出。

### 2. 仪表板API

#### GET /
- **描述**: 系统仪表板，展示核心业务指标。
- **功能**: 获取待审批帖子数、今日新增订单、活跃帖子总数等关键统计数据。
- **认证**: 需要认证。

### 3. 订单管理API

#### GET /orders
- **描述**: 获取订单列表，支持多种筛选条件。
- **查询参数**:
  - `merchant_id` (可选): 按商户ID筛选。
  - `status` (可选): 按订单状态 (`pending`, `completed`, etc.) 筛选。
  - `start_date` / `end_date` (可选): 按日期范围筛选。
- **功能**: 提供订单数据的分页、筛选和查看功能。
- **认证**: 需要认证。

### 4. 商户与帖子管理API

#### GET /merchants
- **描述**: 获取商户帖子列表。
- **查询参数**:
  - `status` (可选): 按帖子状态 (`pending_approval`, `approved`, `published`, `expired`) 筛选。
  - `search` (可选): 按商户名称或ID进行模糊搜索。
- **功能**: 展示所有商户帖子的核心信息，是后台管理的主要入口。
- **认证**: 需要认证。

#### GET /merchants/{merchant_id}/edit
- **描述**: 获取指定商户帖子的详细信息，用于编辑。
- **路径参数**: `merchant_id` - 商户的永久ID。
- **功能**: 返回一个包含商户所有已提交信息的表单。
- **认证**: 需要认证。

#### POST /merchants/{merchant_id}/edit
- **描述**: 更新指定商户帖子的信息。
- **路径参数**: `merchant_id` - 商户的永久ID。
- **表单数据**: 包含商户的所有可编辑字段，如：
  - `name`, `username`, `region_id`
  - `price_1`, `price_2`
  - `advantages`, `disadvantages`, `basic_skills`
  - `expiration_time` (管理员可修改的到期时间)
- **认证**: 需要认证。

#### POST /merchants/{merchant_id}/approve
- **描述**: **(核心操作)** 批准一个待审核的帖子。
- **路径参数**: `merchant_id` - 商户的永久ID。
- **功能**: 将帖子的状态从 `pending_approval` 更改为 `approved`，使其进入待发布队列。
- **认证**: 需要认证。

#### POST /merchants/{merchant_id}/delete
- **描述**: 删除一个商户及其所有相关数据（帖子、媒体文件等）。
- **路径参数**: `merchant_id` - 商户的永久ID。
- **认证**: 需要认证。

### 5. 绑定码管理API - **V2.0 唯一接口标准**

**架构特点**: 
- **唯一调用链路**: Route → DB Manager（无Service层冗余）
- **统一字段**: 全链路使用 `merchant_id`，与数据库schema精准匹配
- **字符串参数**: 路由参数统一使用 `{code}` 字符串类型，无类型转换风险

#### GET /binding-codes
- **描述**: 获取绑定码列表，支持多维度筛选和分页。
- **查询参数**:
  - `include_used` (可选): 是否包含已使用的绑定码 (默认: true)
  - `include_expired` (可选): 是否包含已过期的绑定码 (默认: false)
  - `page` (可选): 页码 (默认: 1)
- **路由注册**: `app.get("/binding-codes")(binding_codes.binding_codes_list)`
- **函数**: `binding_codes_list(request: Request)`
- **数据源**: `binding_codes_manager.get_all_binding_codes()`
- **统一字段**: 查询结果使用 `merchant_id` 关联商户信息
- **认证**: Session认证，需要admin权限

#### GET /binding-codes/generate
- **描述**: 绑定码生成表单页面。
- **路由注册**: `app.get("/binding-codes/generate")(binding_codes.binding_codes_generate_page)`
- **函数**: `binding_codes_generate_page(request: Request)`
- **返回**: HTML表单页面
- **认证**: Session认证，需要admin权限

#### POST /binding-codes/generate
- **描述**: 批量生成绑定码。
- **表单数据**:
  - `count`: 生成数量 (必需)
  - `expires_hours` (可选): 过期时间（小时，默认无过期）
- **路由注册**: `app.post("/binding-codes/generate")(binding_codes.binding_codes_generate_action)`
- **函数**: `binding_codes_generate_action(request: Request)`
- **数据源**: `binding_codes_manager.generate_binding_code()`
- **返回**: 重定向到绑定码列表页面，显示生成结果
- **认证**: Session认证，需要admin权限

#### GET /binding-codes/{code}/detail
- **描述**: 获取指定绑定码的详细信息和使用记录。
- **路径参数**: `code` (string) - **V2.0标准**: 绑定码字符串，非整型ID
- **路由注册**: `app.get("/binding-codes/{code}/detail")(binding_codes.binding_code_detail)`
- **函数**: `binding_code_detail(request: Request)`
- **数据源**: `binding_codes_manager.get_binding_code_info(code)`
- **参数处理**: `request.path_params.get("code")` 安全获取
- **返回**: HTML详情页面，包含商户关联信息
- **认证**: Session认证，需要admin权限

#### POST /binding-codes/{code}/delete
- **描述**: 删除指定的绑定码及其关联数据。
- **路径参数**: `code` (string) - **V2.0标准**: 直接使用绑定码字符串
- **路由注册**: `app.post("/binding-codes/{code}/delete")(binding_codes.binding_code_delete)`
- **函数**: `binding_code_delete(request: Request)`
- **数据源**: `binding_codes_manager.delete_binding_code(code)`
- **处理逻辑**: 软删除或硬删除（根据业务需求）
- **返回**: 重定向到绑定码列表页面，显示删除结果
- **认证**: Session认证，需要admin权限

#### GET /binding-codes/export
- **描述**: 导出绑定码数据为CSV文件。
- **路由注册**: `app.get("/binding-codes/export")(binding_codes.binding_codes_export)`
- **函数**: `binding_codes_export(request: Request)`
- **导出字段**: 
  - `id`, `code`, `is_used`, `merchant_id` (统一字段), `merchant_name`
  - `created_at`, `expires_at`, `used_at`, `bound_telegram_username`, `bound_telegram_name`
- **数据源**: `binding_codes_manager.get_all_binding_codes(include_used=True, include_expired=True)`
- **文件格式**: CSV with UTF-8 BOM编码
- **认证**: Session认证，需要admin权限

### V2.0架构核心原则

**字段统一标准**:
- ✅ 全链路使用 `merchant_id` 字段名
- ❌ 禁用 `used_by_merchant_id` 历史字段名

**参数类型标准**:
- ✅ 路由参数使用 `{code}` 字符串类型
- ❌ 禁用 `{code_id:int}` 整型参数

**调用链路标准**:
- ✅ Route → DB Manager 直接调用
- ❌ 禁用中间Service层冗余

**错误处理标准**:
- ✅ 使用 `request.path_params.get("code")` 安全获取
- ❌ 禁用直接字典访问 `request.path_params["code"]`

### 6. 媒体文件代理路由

#### GET /media-proxy/{media_id}
- **描述**: (核心功能) 此路由不返回HTML，而是作为Web后台显示Telegram媒体文件的代理。
- **路径参数**: `media_id` - `media`表中记录的媒体文件ID。
- **功能**: 服务器根据`media_id`查找到对应的`telegram_file_id`，然后实时从Telegram下载该文件，并将文件数据流作为响应直接返回给浏览器。这使得`<img>`等标签可以直接引用此路由来显示图片/视频。
- **认证**: 需要认证。

---

## 数据库管理器 (Data Managers)

为支撑以上API，后端需要实现相应的数据操作类。

### MerchantManager
```python
class MerchantManager:
    @staticmethod
    async def get_merchants(status: str = None, search: str = None) -> list:
        # 获取商户列表，支持按状态和名称搜索

    @staticmethod
    async get_merchant_by_id(merchant_id: int) -> dict:
        # 获取单个商户的详细信息

    @staticmethod
    async update_merchant(merchant_id: int, updates: dict) -> bool:
        # 更新商户信息

    @staticmethod
    async approve_post(merchant_id: int) -> bool:
        # 将帖子状态更新为 'approved'

    @staticmethod
    async get_pending_approval_count() -> int:
        # 获取待审批的帖子数量
```

### OrdersManager
```python
class OrdersManager:
    @staticmethod
    async def get_orders(merchant_id: int = None, status: str = None, start_date: str = None, end_date: str = None) -> list:
        # 获取订单列表，支持多维度筛选

    @staticmethod
    async get_order_by_id(order_id: int) -> dict:
        # 获取单个订单的详细信息
```