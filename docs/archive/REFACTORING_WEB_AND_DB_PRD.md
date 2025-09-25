# PRD: Web面板与数据库重置计划

**版本**: 1.0
**状态**: `待开始 (Not Started)`

---

## 1. 背景与目标 (Background & Goal)

### 1.1 背景
当前项目后端代码已完成现代化重构（V2.0），但前端和数据库仍处于遗留状态：
- **前端**: 同时存在一个旧的、功能完整的 `web/` 面板和一个不完整的、未适配新后端的面板。代码结构混乱。
- **数据库**: 开发数据库的表结构可能与最新的V2.0代码模型不完全同步。
- **项目阶段**: 系统尚未正式上线，无真实用户和生产数据。

### 1.2 核心目标
彻底移除所有遗留的Web面板代码和开发数据库文件，为全新的、与V2.0后端API完全匹配的前端开发，奠定一个**纯净、无技术负债**的基础。

---

## 2. 项目范围 (Scope)

### 2.1 范围内 (In Scope)
- **删除** 旧的Web面板核心逻辑目录 (`web/`)。
- **删除** 旧的Web面板静态资源目录 (`static/`)。
- **重构** 应用入口文件 (`asgi_app.py`)，移除所有Web面板的集成代码。
- **删除** 开发环境的数据库文件 (`*.db`)。
- **创建** 一个全新的前端项目脚手架（placeholder）。

### 2.2 范围外 (Out of Scope)
- 新前端项目的具体页面或功能实现。
- 对已完成的后端V2.0代码进行任何修改。
- 任何形式的数据迁移（因为我们将直接删除旧数据库）。

### 2.5 技术栈与架构回顾 (Tech Stack & Architecture Review)
为了确保新建的前端项目与现有后端保持技术一致性，此处重申V2.0系统的核心技术栈与架构。

**核心技术栈**
| 技术组件 | 版本 | 角色定位 |
|---|---|---|
| Python | 3.12+ | 主要编程语言 |
| aiogram | 3.x | Telegram Bot 框架 |
| FastHTML | 0.6.0+ | Web管理面板框架 (重建沿用) |
| SQLite | 内置 | 数据持久化 |
| Uvicorn | 0.25.0+ | ASGI 服务器 |
| APScheduler | 3.x | 后台定时任务 |

**系统架构**
项目采用双进程模式，通过 `railway.toml` 进行部署：
1.  **Web 进程 (`main.py`)**: 运行一个ASGI应用，该应用同时承载 `aiogram` Bot交互和 Web服务。
2.  **Worker 进程 (`scheduler.py`)**: 独立运行 `APScheduler`，负责处理所有定时任务（如帖子发布、状态更新等），与主应用解耦。

**前端重建技术选型**
根据计划，新的Web管理面板将**沿用现有技术栈**，即在Python环境内，通过 `FastHTML` 或类似的服务器端渲染（SSR）模式进行重建。这确保了与后端API的最大兼容性，无需引入新的语言或框架。

---

## 3. 执行计划 (Execution Plan)

本次重构将分三阶段执行，全部采用**非破坏性**的“归档式”修改，确保所有操作均可回滚。

### Phase 1: 归档旧代码并创建样板骨架 (Atomize: 3 Steps)
此阶段旨在安全归档旧代码，并为“原地重建”创建一个包含最小化样板代码的、可直接运行的文件框架。

- **Step 1.1**: **归档**核心逻辑目录，将 `web/` 重命名为 `archive-web/`。
- **Step 1.2**: **归档**静态资源目录，将 `static/` 重命名为 `archive-static/`。
- **Step 1.3**: **重建骨架**: 重新创建 `web/` 和 `static/` 的内部目录结构，并创建所有同名文件。关键的路由文件（如 `web/routes/merchants.py`）将包含空的路由列表定义（如 `merchants_routes = []`），以满足 `asgi_app.py` 的导入需求。

**重要说明**: `asgi_app.py` 和 `path_manager.py` 将**不会**被修改。

### Phase 2: 备份并重置数据库 (Atomize: 2 Steps)
此阶段旨在确保数据库与V2.0代码模型完全同步，同时保留旧数据以备查询。

- **Step 2.1**: **备份**开发数据库文件，例如将 `data/marketing_bot_dev.db` 重命名为 `data/marketing_bot_dev.db.backup`。
- **Step 2.2**: 验证数据库自动重建机制。通过启动主应用，确认新的、干净的数据库文件及表结构是否被代码自动创建。



---

## 4. 进度与状态追踪 (Progress & Status Tracking)

| 状态 | 阶段 | 步骤 | 描述 | 变更文件/目录 |
|:---:|:---:|:---|:---|:---|
| `[x]` | **Phase 1** | - | **归档旧代码并创建样板骨架** | |
| `[x]` | | **Step 1.1** | 将 `web/` 重命名为 `archive-web/` | `RENAME: .../web/ -> .../archive-web/` |
| `[x]` | | **Step 1.2** | 将 `static/` 重命名为 `archive-static/` | `RENAME: .../static/ -> .../archive-static/` |
| `[x]` | | **Step 1.3** | 重建 `web/` 和 `static/` 的样板骨架 | `CREATE: Boilerplate files in web/ & static/` |
| `[x]` | **Phase 2** | - | **备份并重置数据库** | |
| `[x]` | | **Step 2.1** | 备份开发数据库文件 | `RENAME: .../data/marketing_bot_dev.db -> .../data/marketing_bot_dev.db.backup` (路径待确认) |
| `[x]` | | **Step 2.2** | 验证数据库自动重建 | `VERIFY: 启动应用后新DB文件生成` |

---

## 附录A: 系统函数、方法与接口总览

本附录旨在索引项目中的主要功能点、公开接口和核心业务逻辑实现，作为后续开发的参考。列表基于对核心应用目录（`database/`, `handlers/`, `dialogs/`, `web/`, `scripts/`等）的分析。

### A.1 Web Admin API 接口

这些接口是为Web管理后台定义的，基于FastHTML和Starlette，直接返回HTML页面或处理表单提交。

#### 登录与授权
- `GET /login`: 显示登录页面。
- `POST /login`: 处理登录表单提交。
- `GET /logout`: 处理登出操作。

#### 核心管理路由
- `GET /`: 仪表板页面，显示核心统计数据。
- `GET /merchants`: 显示商户/帖子列表，支持按状态和名称搜索。
- `GET /merchants/{id}/edit`: 显示用于编辑特定商户/帖子信息的表单。
- `POST /merchants/{id}/edit`: 更新特定商户/帖子的信息。
- `POST /merchants/{id}/approve`: **核心操作**，批准帖子，使其进入待发布队列。
- `POST /merchants/{id}/delete`: 删除商户/帖子。
- `GET /orders`: 显示订单列表，支持按商户、状态、日期筛选。
- `GET /regions`: 显示城市和地区管理页面。
- `POST /regions/city/add`: 添加新城市。
- `POST /regions/district/add`: 在城市下添加新地区。
- `GET /incentives`: 显示用户激励系统（等级、勋章）的管理页面。
- `POST /incentives/level/add`: 添加新等级。
- `POST /incentives/badge/add`: 添加新勋章。
- `GET /media-proxy/{media_id}`: **核心接口**，用于在Web后台安全地显示Telegram服务器上的图片/视频。

---

### A.2 Telegram Bot 接口 (Handlers & Dialogs)

这些接口是机器人响应用户输入（命令、按钮点击等）的入口点，主要定义在 `handlers/` 和 `dialogs/` 目录中。

#### 核心命令
- `Command("start")`: `cmd_start` - 处理用户初次启动或常规启动命令，显示主菜单。
- `Command("bind")`: `handle_bind_command` - **核心流程起点**，处理用户发送的绑定码，启动商户绑定流程。
- `Command("panel")`: `show_merchant_panel` - 已绑定商户查看自己的管理面板。
- `Command("profile")`: `show_user_profile` - 普通用户查看自己的等级、积分和勋章。
- `Command("admin")`: `admin_panel` - 管理员获取后台管理命令菜单。

#### 核心回调 (Callback Queries)
- `F.data == "search_start"`: `handle_location_search_start` - 用户点击“地区搜索”按钮，启动地区筛选流程。
- `F.data.startswith("city_")`: `handle_city_selection` - 用户选择了城市。
- `F.data.startswith("district_")`: `handle_district_selection` - 用户选择了地区。
- `F.data.startswith("merchant_dist_")`: `handle_merchant_district_selection` - 用户在地区搜索结果中选择了一个商户。
- `F.data.startswith("create_order_")`: `create_order_callback` - **核心流程**，用户点击帖子上的“立即预约”按钮。
- `F.data.startswith("confirm_order_")`: `confirm_order_callback` - 用户最终确认订单。
- `F.data.startswith("rating_")`: `process_rating_callback` - **核心流程**，用户在评价流程中点击分数按钮。
- `F.data == "submit_review"`: `submit_review_callback` - 用户提交评价。
- `F.data.startswith("confirm_review_")`: `confirm_review_validity` - **核心流程**，商户确认评价的有效性。

#### 对话流/状态机 (FSM)
- **Binding Flow (`dialogs/binding_flow_new.py`)**: 一个基于FSM的对话流，用于引导新商户逐步填写名称、地区、价格、优点、缺点、上传媒体文件等。
- **Review Flow (`dialogs/review_flow.py`)**: 一个FSM对话流，用于引导用户完成对商家的多维度评分和文字评价。

---

### A.3 数据库管理器 (Database Managers)

这些类封装了所有对数据库的异步操作，是数据持久化的核心。它们主要定义在 `database/` 目录中。

- **`MerchantManager` (`db_merchants.py`)**:
  - `create_merchant`, `get_merchant_by_id`, `update_merchant_status`, `get_merchants_for_publishing`, `get_published_merchants_by_district` 等。
- **`OrdersManager` (`db_orders.py`)**:
  - `create_order`, `get_order_by_id`, `get_orders`, `update_order_status` 等。
- **`BindingCodesManager` (`db_binding_codes.py`)**:
  - `create_code`, `verify_code`, `use_code`, `get_all_codes` 等。
- **`ReviewsManager` (`db_reviews.py`)**:
  - `create_review`, `confirm_review`, `get_reviews_for_merchant`, `calculate_merchant_scores` 等。
- **`UserManager` (`db_users.py`)**:
  - `get_or_create_user`, `update_user_xp_points`, `get_user_profile` 等。
- **`IncentivesManager` (`db_incentives.py`)**:
  - `get_levels`, `get_badges`, `get_badge_triggers`, `add_user_badge` 等。
- **`RegionsManager` (`db_regions.py`)**:
  - `get_cities`, `get_districts_by_city`, `add_city`, `add_district` 等。
- **`MediaManager` (`db_media.py`)**:
  - `add_media`, `get_media_for_merchant` 等。
- **`TemplateManager` (`db_templates.py`)**:
  - `get_template`, `update_template`, `get_all_templates` 等。
- **`SystemConfigManager` (`db_system_config.py`)**:
  - `get_config`, `set_config` 等。

---

### A.4 核心后台服务

- **`scheduler.py`**:
  - `publish_pending_posts()`: 定时任务，扫描数据库中状态为 `approved` 且到达发布时间的帖子，并将其发布到频道。
  - `update_expired_posts()`: 定时任务，检查已发布帖子的到期时间，并进行相应处理。
  - `update_merchant_scores_job()`: 定时任务，聚合有效评价，更新商家的平均分。
