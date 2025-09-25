# 项目开发常用命令

## 启动命令
```bash
# 开发环境启动（推荐）
python run.py

# 智能多模式启动
RUN_MODE=dev python run.py       # 开发模式（轮询+Web根路径）
RUN_MODE=bot python run.py       # 仅机器人模式
RUN_MODE=web python run.py       # 仅Web管理后台
RUN_MODE=prod python run.py      # 生产模式（Webhook+Web子路径）

# 生产环境
python main.py                   # Railway生产环境ASGI统一架构
```

## 测试命令
```bash
# 运行所有测试
python run_tests.py

# 运行特定类型测试
pytest tests/unit/ -v            # 单元测试
pytest tests/integration/ -v     # 集成测试
pytest --cov=. --cov-report=html # 带覆盖率的测试
```

## 代码质量检查
```bash
black .      # 代码格式化
flake8 .     # 代码风格检查
mypy .       # 静态类型检查
```

## 数据库操作
```bash
# V2数据库迁移（重要：这是修改数据库结构的唯一正确方式）
python scripts/migrate_to_v2.py

# 备份数据库
cp data/database.db data/database.db.backup
```

## Git操作
```bash
git status                       # 检查仓库状态
git add .                        # 添加所有更改
git commit -m "描述性提交信息"    # 提交更改
```

## Web管理后台
- **访问地址**: http://localhost:8000 (开发) 或 http://127.0.0.1:8007
- **管理员账号**: admin
- **密码**: admin123 (或.env中设置的WEB_ADMIN_PASSWORD)

## 重要注意事项
1. **数据库修改铁律**: 只能通过 `scripts/migrate_to_v2.py` 迁移脚本修改数据库结构
2. **环境变量**: 必需配置BOT_TOKEN, ADMIN_IDS, GROUP_CHAT_ID, WEB_ADMIN_PASSWORD
3. **永久ID系统**: 所有业务数据都关联到永久ID，不关联TG账号
4. **媒体文件**: 通过 `/media-proxy/{media_id}` 访问，只存储telegram_file_id