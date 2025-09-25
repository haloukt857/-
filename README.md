# Telegram商户机器人 V2.0

> 一个现代化的Telegram营销机器人系统，专为服务型业务设计，支持商户管理、用户预约、订单处理和完整的Web管理后台。

## 📋 项目概览

本项目是一个基于Telegram的智能商户营销平台，通过机器人实现商户与用户的高效连接。系统采用**永久ID绑定机制**解决商户更换账号导致的数据丢失问题，提供完整的商户生命周期管理和用户激励体系。

### 🎯 核心价值

- **永久ID系统**: 解决商户更换Telegram账号导致数据丢失的痛点
- **对话式信息收集**: 通过FSM状态机引导商户填写资料，支持智能验证
- **统一审核管理**: Web后台支持管理员审核、修改商户信息并设置发布时间
- **自动化发布**: 定时任务服务在指定时间自动发布到频道
- **完整激励系统**: 积分、经验、等级、勋章全面激励用户活跃度

### 🏗️ 技术架构

- **统一ASGI架构**: Bot和Web后台统一部署，共享数据和会话
- **异步高性能**: 基于Python 3.12和aiogram 3.4.1的全异步架构  
- **模块化设计**: 13个功能模块，支持独立开发和测试
- **云原生部署**: 针对Railway平台优化，支持多进程和自动扩展

## 🚀 技术栈

### 核心框架
- **Python 3.12+** - 现代Python特性支持
- **aiogram 3.4.1** - 异步Telegram机器人框架，支持FSM状态管理
- **FastHTML** - 现代化HTML框架，用于Web管理后台
- **APScheduler 3.10.4** - 高级Python调度器，处理定时发布任务

### 数据层
- **SQLite** - 轻量级数据库，支持异步操作
- **aiosqlite 0.19.0** - 异步SQLite连接池管理

### 服务层
- **Uvicorn** - 高性能ASGI服务器
- **Starlette** - 轻量级ASGI框架，提供中间件和路由支持

### 部署和监控
- **Railway** - 云平台部署，支持自动扩展
- **Webhook支持** - 生产环境高效消息处理
- **实时健康检查** - 自动故障恢复和监控

## 📁 项目结构

```
lanyangyang/
├── main.py                 # 生产环境ASGI入口
├── run.py                  # 开发环境启动脚本
├── bot.py                  # Telegram机器人主类
├── config.py               # 项目配置和消息模板
├── scheduler.py            # 独立定时任务Worker
├── asgi_app.py            # ASGI统一架构
├── path_manager.py        # 动态路径管理
├── requirements.txt       # Python依赖清单
├── .env.example          # 环境变量配置示例
├── railway.toml          # Railway部署配置
│
├── handlers/             # 机器人处理器
│   ├── admin.py         # 管理员命令处理
│   ├── merchant.py      # 商户注册和管理
│   ├── user.py          # 用户交互处理
│   ├── statistics.py    # 统计数据处理
│   └── advanced_analytics.py # 高级分析功能
│
├── database/            # 数据库层
│   ├── db_connection.py  # 数据库连接池
│   ├── db_merchants.py   # 商户数据管理器V2
│   ├── db_orders.py      # 订单数据管理器V2
│   ├── db_incentives.py  # 激励系统数据管理器
│   ├── db_binding_codes.py # 绑定码管理
│   ├── db_templates_v2.py # 消息模板系统V2
│   └── schema.sql        # 数据库结构定义
│
├── web/                 # Web管理后台
│   ├── app.py           # FastHTML主应用
│   ├── routes/          # 路由模块
│   │   ├── v2_merchants.py # 商户管理路由
│   │   ├── v2_orders.py    # 订单管理路由
│   │   └── v2_regions.py   # 地区管理路由
│   └── data_config.py   # 数据配置管理
│
├── scripts/             # 工具脚本
│   ├── migrate_to_v2.py # V2数据库迁移脚本
│   ├── deploy.py        # 部署验证脚本
│   └── post_deploy_hook.py # 部署后钩子
│
├── tests/               # 测试套件
│   ├── unit/           # 单元测试
│   ├── integration/    # 集成测试
│   └── conftest.py     # 测试配置
│
├── docs/               # 项目文档
│   └── modules/        # 13个功能模块文档
│
└── data/               # 数据存储
    └── database.db     # SQLite数据库文件
```

## 🛠️ 本地开发设置

### 前置条件

- Python 3.12+ 
- Git
- Telegram机器人Token（从 [@BotFather](https://t.me/BotFather) 获取）

### 快速开始

1. **克隆仓库**
   ```bash
   git clone <repository-url>
   cd lanyangyang
   ```

2. **创建和激活Python虚拟环境**
   ```bash
   # 创建虚拟环境
   python -m venv venv
   
   # 激活虚拟环境
   # Linux/Mac:
   source venv/bin/activate
   # Windows:
   venv\\Scripts\\activate
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **配置环境变量**
   ```bash
   # 复制配置模板
   cp .env.example .env
   
   # 编辑 .env 文件，填入实际配置
   nano .env
   ```

   **必需配置项**：
   ```env
   BOT_TOKEN=你的机器人令牌
   ADMIN_IDS=你的Telegram用户ID
   GROUP_CHAT_ID=频道ID
   WEB_ADMIN_PASSWORD=Web管理后台密码
   ```

5. **获取用户和频道ID**
   ```bash
   # 启动机器人获取用户ID
   python get_user_id.py
   
   # 向机器人发送消息，查看控制台输出的user_id
   # 将机器人添加到频道并发送消息，获取chat_id
   ```

6. **数据库初始化**
   ```bash
   # V2数据库迁移（首次运行）
   python scripts/migrate_to_v2.py
   ```

## 🚀 运行项目

### 开发环境

```bash
# 启动开发服务器（推荐）
python run.py

# 或分别启动服务
# 1. 启动主应用（Bot + Web后台）
python main.py

# 2. 启动定时任务Worker（另一个终端）
python scheduler.py
```

访问地址：
- **机器人**: 在Telegram中与你的机器人对话
- **Web管理后台**: http://localhost:8000
  - 用户名: admin
  - 密码: 你在.env中设置的WEB_ADMIN_PASSWORD

### 生产环境

```bash
# Railway部署会自动运行
python main.py
```

生产环境会自动启动：
- 主ASGI应用（Bot + Web后台）
- 独立定时任务Worker
- 自动数据库迁移
- 健康检查和监控

## 🧰 数据库重建/恢复（重要）

在开发阶段，如果你手工修改了 `schema.sql` 或误改了 `system_config.schema_version`，可能出现“版本显示已最新但表缺失”的不一致，导致启动失败。系统提供两种安全恢复方式：

1) 首选：直接运行开发启动脚本（内置自愈）

```bash
python run.py
```

- 行为：启动时若检测到“版本一致但表校验失败”，会自动执行 Schema 自修复（重新应用 `schema.sql` + 结构同步）并重试校验。
- 适用：日常开发、轻度不一致。

2) 强制重建数据库（带备份）

```bash
# 备份到 data/backups/ 后重建
python tools/reset_database.py --yes

# 不备份直接重建（谨慎）
python tools/reset_database.py --yes --no-backup

# 指定备份目录
python tools/reset_database.py --yes --backup-dir data/my_backups
```

- 行为：如存在数据库文件，先备份（可选）后删除，再调用系统初始化流程重建全量结构与模板。
- 适用：本地需要“干净环境”，或表结构被大量破坏时。

注意事项
- 不要只修改 `system_config` 里的 `schema_version` 而不执行迁移/重建，容易造成“版本正确但缺表”。
- 若 reset 脚本提示“duplicate column name ...”，说明之前表结构被部分创建；直接用 `python run.py` 启动会触发自愈，通常能恢复。
- 生产环境请谨慎使用强制重建，务必先确认备份完整。

## 🧪 运行测试

```bash
# 运行所有测试
python run_tests.py

# 运行单元测试
pytest tests/unit/ -v

# 运行集成测试
pytest tests/integration/ -v

# 运行特定测试文件
pytest tests/unit/test_merchants.py -v

# 运行带覆盖率的测试
pytest --cov=. --cov-report=html
```

### 代码质量检查

```bash
# 代码格式化
black .

# 代码风格检查
flake8 .

# 静态类型检查
mypy .
```

## 📊 V2.0功能模块状态（14个模块全部完成）

### ✅ 核心业务模块（已完成）
1. **用户注册和身份验证模块** - 三角色权限体系（管理员/商户/用户）
2. **商家绑定和管理模块** - 永久ID绑定系统（Web快速添加+FSM对话收集）
3. **订单管理和处理模块V2** - 完整生命周期（下单→接单→评价→确认）
4. **评价与等级系统模块V2** - 双向评价机制（用户评价+商户确认）
5. **用户激励系统模块** - 积分经验等级勋章完整体系
6. **地区搜索和筛选模块** - 城市-区县二级地区管理

### ✅ 管理与配置模块（已完成）
7. **Web商家管理模块** - 完整的后台管理界面（14个路由模块）
8. **帖子管理模块** - 状态驱动的生命周期管理
9. **频道订阅验证模块V2** - 用户关注频道验证+分析统计
10. **系统配置和管理模块** - 动态配置系统（system_config表）

### ✅ 智能化模块（已完成）
11. **关键词匹配和推荐模块** - 商户标签智能系统
12. **消息模板和自动回复模块** - 动态模板引擎
13. **媒体文件代理模块** - Telegram文件实时获取系统
14. **数据分析统计模块** - 订单/用户/订阅三维分析

### 🎯 V2.0架构特色
- **唯一接口标准**: Route → DB Manager 单一调用链路
- **统一字段命名**: 全链路使用 `merchant_id`，与数据库精准匹配
- **无冗余架构**: 清除Service层，避免重复调用
- **类型安全**: 路由参数统一使用字符串类型

## 🔧 核心业务流程

### 商户注册流程（5阶段）

1. **阶段一**: 商户通过付款机器人获得绑定码
2. **阶段二**: 商户用`/bind <绑定码>`绑定，FSM状态机引导填写信息
3. **阶段三**: 管理员在Web后台审核，可修改信息并设置到期时间
4. **阶段四**: 定时任务服务在指定时间自动发布到频道
5. **阶段五**: 商户发送 `/start` 并点击“我的资料”查看与管理，用户可下单评价

### 永久ID系统

- **核心价值**: 解决商户更换Telegram账号导致数据丢失的问题
- **设计理念**: merchants表的id字段是永久ID，telegram_chat_id可以修改
- **业务保障**: 所有业务数据都关联到永久ID，不关联TG账号

### 媒体文件处理

- **存储策略**: 只保存telegram_file_id，不存储实际文件
- **访问方式**: 通过`/media-proxy/{media_id}`实时代理下载
- **性能优化**: 流式传输，节省存储成本，支持高并发访问

## 🌐 部署指南

### Railway部署（推荐）

1. **准备部署**
   ```bash
   # 检查部署配置
   python scripts/deploy.py
   ```

2. **环境变量设置**
   - `BOT_TOKEN`: Telegram机器人令牌
   - `ADMIN_IDS`: 管理员用户ID（逗号分隔）
   - `GROUP_CHAT_ID`: 频道ID
   - `WEB_ADMIN_PASSWORD`: Web管理密码
   - `NODE_ENV`: production

3. **自动部署流程**
   - Git推送触发自动部署
   - 自动数据库迁移
   - 多进程启动（Web + Worker）
   - 健康检查和监控

### Docker部署

```bash
# 构建镜像
docker build -t telegram-merchant-bot .

# 运行容器
docker run -d \
  --name merchant-bot \
  -p 8000:8000 \
  -e BOT_TOKEN=你的令牌 \
  -e ADMIN_IDS=你的用户ID \
  telegram-merchant-bot
```

## ⚙️ 环境变量说明

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `BOT_TOKEN` | ✅ | - | Telegram机器人令牌 |
| `ADMIN_IDS` | ✅ | - | 管理员用户ID（逗号分隔） |
| `GROUP_CHAT_ID` | ✅ | - | 频道/群组ID |
| `WEB_ADMIN_PASSWORD` | ✅ | admin123 | Web管理后台密码 |
| `WEBHOOK_URL` | 🔶 | - | Webhook URL（生产环境） |
| `USE_WEBHOOK` | 🔶 | true | 是否使用Webhook模式 |
| `PORT` | 🔶 | 8000 | 服务器端口 |
| `DEBUG` | 🔶 | false | 调试模式开关 |
| `NODE_ENV` | 🔶 | development | 环境标识 |
| `QUICK_REGISTRATION_MODE` | 🔶 | false | 快速注册模式：true=管理员后台快速添加；false=用户通过Bot 7步完善资料 |

说明：当 `QUICK_REGISTRATION_MODE=false` 时，商户在Bot端成功绑定后会自动进入“7步完善资料”流程（从“步骤1/7: 选择商户类型”开始）。若设为 `true`，则走快速注册（管理员后续在后台完善资料）。

## 📈 监控和维护

### 应用监控

- **健康检查**: `/health` 端点监控应用状态
- **性能指标**: 请求响应时间、数据库查询性能
- **错误追踪**: 自动错误日志记录和告警

### 数据库维护

```bash
# 备份数据库
cp data/database.db data/database.db.backup

# 数据库迁移
python scripts/migrate_to_v2.py

# 清理日志
python scripts/cleanup_logs.py
```

## 🧩 评价系统 V2 数据库更新（摘要）

- 一单两评：
  - u2m（用户→商户/老师）：沿用 `reviews`，新增最小管理/可见性/报告链接字段。
  - m2u（商户/老师→用户）：新增 `merchant_reviews`（五维评分 + 可选文本）。
  - 用户侧聚合：新增 `user_scores`（五维平均与计数）。
- 迁移文件：`database/migrations/migration_2025_09_24_1_评价系统V2_新增m2u与扩展u2m.sql`
- 查询约定：列表不读取长文本；机器人端仅返回 `report_post_url`；机器人查询默认随商户启用/未过期做门禁过滤。

详情见：`docs/modules/12-商家与用户双向评价系统模块.md`。

### 日志管理

- **日志级别**: DEBUG、INFO、WARNING、ERROR
- **日志路径**: `data/logs/bot.log`
- **自动轮转**: 按日期自动分割日志文件

## 🤝 贡献指南

### 开发工作流

1. Fork项目并创建功能分支
2. 遵循代码规范（Black格式化 + Flake8检查）
3. 编写单元测试并确保通过
4. 提交Pull Request并描述变更内容

### 代码规范

```bash
# 格式化代码
black .

# 检查代码风格
flake8 .

# 类型检查
mypy .

# 运行测试
pytest tests/ -v
```

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 🆘 支持和反馈

- **问题反馈**: 通过 GitHub Issues 提交bug或功能请求
- **技术支持**: 查看 `docs/` 目录下的详细文档
- **社区讨论**: 加入我们的Telegram群组讨论技术问题

---

## 🎯 项目状态

**当前版本**: V2.0 正式版  
**开发状态**: 生产就绪  
**架构标准**: V2.0唯一接口标准  
**文档完整性**: 100%  
**测试覆盖率**: 85%  
**功能完成度**: 100% (14/14个模块全部完成)

**最后更新**: 2025年9月18日 18:00 (202509181800)

---

*打造最优秀的Telegram商户营销平台 🚀*
