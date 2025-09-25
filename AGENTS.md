# AGENTS 指南（中文版）

## 作用与范围
- 目的：为在本仓库内工作的代理（AI 助手与人类协作者）提供统一的工作约定、代码规范与执行流程。
- 适用范围：本文件所在目录为根，作用于整个仓库的目录树。
- 优先级：直接的系统/开发者/用户指令 > 更深层目录的 AGENTS.md > 本文件。
- 约束：本文件对代码风格、结构与流程的要求仅适用于本仓库。

## 项目结构
- 入口文件：`run.py`（开发编排）、`main.py`（生产 ASGI 入口）、`asgi_app.py`（ASGI 应用）、`scheduler.py`（任务/worker）。
- 核心模块：`handlers/`、`database/`、`middleware/`、`dialogs/`、`utils/`、`config/`。
- Web 与资源：`web/`（路由/UI）、`static/`。
- 测试：`tests/{unit,integration,load}/`，共享 fixtures 在 `tests/conftest.py`。
- 文档与数据：`docs/`、`data/`（SQLite、构建产物）。依赖在 `config/requirements.txt`。

## 开发与运行
- 环境初始化：`python -m venv venv && source venv/bin/activate && pip install -r config/requirements.txt`
- 运行：
  - 开发：`python run.py` 或 `RUN_MODE=dev python run.py`
  - 生产（类似）：`RUN_MODE=prod python run.py` 或 `python main.py`
  - Worker：`python scheduler.py`
- 测试：
  - 单测：`pytest tests/unit -v`
  - 集成：`pytest tests/integration -v`
  - 覆盖率：`pytest --cov=. --cov-report=html`
  - 助手脚本：`python tools/run_tests.py`

## 代码风格与命名
- 版本与风格：Python 3.12+；4 空格缩进；公共 API 加类型标注。
- 格式化：`black .`；Lint：`flake8 .`；类型：`mypy .`。
- 命名：
  - 文件/模块：`lower_snake_case.py`
  - 类：`PascalCase`
  - 函数/变量：`lower_snake_case`
  - 常量：`UPPER_SNAKE_CASE`
- 设计偏好：函数聚焦单一职责；在 `handlers/` 与 `database/` 优先使用 async 模式。

## 测试规范
- 框架：`pytest` + `pytest-asyncio`；异步测试需 `@pytest.mark.asyncio`。
- 目录与命名：`tests/{unit,integration,load}/`；文件名 `test_*.py`；测试函数名 `test_*`。
- 标记：`unit`、`integration`、`slow`、`database`、`network`（见 `config/pytest.ini`）。
- 快速检查：`pytest --maxfail=1 -q`；保证有意义的覆盖率。

## 代理工作方式（适配 Codex CLI）
- 沟通风格：简洁、直接、友好。优先可执行指导与下一步行动。
- 语言策略（强制）：内部思考/检索/分析一律使用英文；对用户的所有可见回复一律使用简体中文（含计划、进度更新、变更说明、错误信息等）。无论用户使用何种语言输入，回复都保持中文，除非用户明确要求改用其他语言。
- Preamble（工具调用前简述）：运行一组相关命令前，用 1–2 句说明要做什么与目的。
- 计划工具 `update_plan`：用于多步骤/阶段性任务；保持唯一一个 `in_progress`；变更计划时说明原因；完成后标记为 `completed`。
- 文件编辑：使用 `apply_patch` 修改或新增文件；尽量小改动、聚焦任务；遵循本文件风格与结构；避免无关重构。
- Shell 使用：搜索优先 `rg`；读取文件分块，单次不超过 250 行；注意终端输出截断（约 256 行/10KB）。
- 沙箱与审批：
  - 文件系统可能为只读；写文件/安装依赖需请求升级审批。
  - 网络默认受限；涉及网络访问先确认或请求审批。
  - 重要但失败的命令可按“先 sandbox 运行，失败再申请升级”的流程。
- 不做的事：不添加版权/许可证头（除非要求）；不擅自更名/迁移文件（除非任务明确需要）；不修无关问题或破测（可在交付说明中指出）。

## 任务执行与质量
- 优先修复根因，而非表层补丁。
- 解决方案保持最小必要改动，契合现有代码风格。
- 如需历史上下文，优先用 `git log`/`git blame` 聚焦相关改动。
- 必要时更新相关文档与简短使用说明。

## 验证与自检
- 若可运行或存在测试，尽量本地验证修改是否完整。
- 先运行最贴近改动的窄范围检查，再逐步扩大范围。
- 若无现成测试、且项目有明确测试模式，可按现有模式补充最小必要测试；不向无测试项目强行添加测试框架。
- 格式检查：在仓库已有格式化工具的前提下使用；不新引入 Formatter。

## 提交与评审
- Commit 规范：
  - 主题行：简洁祈使、带 scope（如 `db:`、`handlers:`、`web:`）。
  - 正文：说明动机、关键变更，必要时关联 issue。
- PR 要求：
  - 清晰描述与关联 issue；Web/UI 改动附截图。
  - 提供测试计划（命令与结果）。
  - 提交前本地通过 `black`、`flake8`、`mypy` 与相关 `pytest` 套件。
- 变更说明：交付时简述做了什么、为什么、如何验证、后续建议。

## 安全与配置
- 机密保存在 `.env`（参考 `.env.example`）；不要提交令牌或 `data/` 下的本地 DB 文件。
- 依赖统一放在 `config/requirements.txt`；若脚本需要解析当前生效依赖，使用 `pathmanager.py`。
- 注意不要在日志、报错或测试快照中泄露敏感信息。

## 结果呈现与交流
- 长任务的阶段更新：用 1–2 句简述当前进度与下一步。
- 最终答复结构（在 CLI 中渲染）：
  - 适度使用小节标题（1–3 词），提升可扫读性。
  - 列表使用 `- ` 开头的单层要点，合并相关点。
  - 命令、路径、标识符使用反引号包裹（如 `pytest`、`handlers/`）。
  - 语气协作、事实化、使用主动语态与现在时。
- 不要输出 ANSI 转义码；不要嵌套过深的层级列表。

## 附加提示
- 若你意识到更合理的“下一步”（如补充最小测试、运行构建、生成覆盖率报告），可简要询问用户是否需要你继续执行。
- 如遇因权限或沙箱限制无法执行的操作，说明受限点并提供可行的替代方案或让用户选择授权升级。

## 数据库重建/恢复（协作须知）
- 默认用 `python run.py` 启动，若检测到“版本一致但缺表/缺字段”，会自动执行 Schema 自愈（重放 `schema.sql` + 结构同步）。
- 需要干净环境：
  - `python tools/reset_database.py --yes` 先备份到 `data/backups/` 再重建；
  - `python tools/reset_database.py --yes --no-backup` 不备份直接重建（谨慎）。
- 不要只改 `system_config.schema_version` 而不迁移/重建，容易导致“版本正确但表缺失”。
- 如 reset 脚本遇到 `duplicate column name ...`，说明历史结构被部分创建；直接运行 `python run.py` 通常会完成自愈并恢复启动。

## Web 架构与装配（强制约定）
- 三个唯一（必须同时满足）：
  - 唯一装配点：所有 Web 路由仅在 `web/app.py` 注册；`asgi_app.py` 只 `from web.app import app`，不得再挂载/扩展 Web 路由。
  - 唯一布局来源：`create_layout`、`require_auth`、`okx_*` 只从 `web/layout.py` 导入；路由文件禁止从 `web.app` 或 `web/components/layouts.py` 导入上述内容。
  - 唯一路径：每个 URL 前缀/端点只绑定一个实现；如存在历史版本（v2/old），一律改名为 `.old`，避免并存生效。

- 禁止与风险控制：
  - 禁止在 FastHTML 应用上再用 Starlette `Mount` 挂载页面路由（会破坏 SSR 渲染、引入循环依赖/冲突）。
  - 路由文件禁止反向从 `web.app` 导入任何工具或对象（只允许从 `web/layout.py`、`web/components/*`、`web/services/*` 导入）。
  - 避免循环依赖：`web/app.py` 只做装配，不被路由反向依赖。

- 三层架构（Service/Route/UI）：
  - Service：封装业务与缓存，返回标准结构（如 `items`、`statistics`、`pagination{page,per_page,total,pages}`、`filters`）。
  - Route：仅解析参数、调用 Service、把数据传给 UI；所有管理端路由必须 `@require_auth`。
  - UI：纯渲染，不含业务判断；读取数据使用 `dict.get('key', 默认值)` 容错。

- 参数归一化规范：
  - 空字符串/无值 → `None`（表示不过滤）；ID 字符串（如 `merchant_id`）转 `int`；日期字符串按 ISO 转换。

- 兼容性与迁移：
  - 历史导入兼容（临时）：如测试仍 `from web.app import AuthManager`，可在 `web/app.py` 做最小 re-export，待测试更新后移除。
  - 任何迁移/重构前先复制备份为 `.old`，新实现落位后逐步切换；确保每一步都可启动与回滚。

- 自检清单（建议执行）：
  - 唯一装配：`rg -n "mount\(|routes\.extend\(" asgi_app.py` 无 Web 面板挂载。
  - 唯一布局：`rg -n "from web\.app import .*create_layout|require_auth|okx_" web/routes` 无结果。
  - 唯一路径：`rg -n "@app\.(get|post)\(\"/subscription" web` 仅出现一次定义。
  - 启动验证：`python run.py` 正常，点击导航各项进入对应页面（非 404/仪表盘）。

## 领域页面对齐（执行基线）
- 地区管理（/regions）：
  - 按旧版实现“城市/区县”新增、编辑（GET+POST）、删除、启用/禁用切换；列表含状态徽章、显示顺序；URL 参数反馈（`city_added` 等）渲染成功/错误提示。
- 用户中心：
  - 用户列表（/users）：等级/搜索/每页筛选、统计卡片、导出按钮（/users/export）、分析入口（/users/analytics）、分页信息与页码、表格含“订单数/勋章数/详情链接”。
  - 用户分析（/users/analytics）：图表与 JSON API（/users/analytics-data）按旧版等价；列表页提供入口。
- 订单管理（/orders）：
  - 列表支持状态/商户/用户/日期筛选与分页；批量操作（完成/评价/取消/导出）；详情页包含商户/用户/评价关联信息与状态更新表单。
- 帖子/评价/订阅等模块：
  - 按旧版字段/路由/呈现对齐；链接到相关详情页保持一致（如帖子 → `/posts/{id}`，用户 → `/users/{id}/detail`）。
  - 评价模块（V2）：一单两评（u2m/m2u 各一条），仅管理员可确认/编辑/删除/暂停-启用；机器人端仅返回 `report_post_url`，列表不读取长文本；机器人查询随商户启用/未过期做门禁过滤。

## 提交流程补充
- 小步提交，逐模块完成：每个模块完成后对照 `.old` 页面/流程进行等价性验证与截图记录。
- Commit 信息包含模块与动作（如 `web: regions add CRUD + csrf`）。
