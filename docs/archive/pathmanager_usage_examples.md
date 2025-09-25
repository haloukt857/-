# PathManager 使用指南

PathManager是一个集中化的路径管理系统，用于统一管理项目中所有文件和目录路径，支持开发/生产环境自动切换。

## 主要特性

- **环境自动切换**: 根据 `NODE_ENV` 环境变量自动切换开发/生产环境路径
- **目录自动创建**: 所有路径方法都会自动确保目录存在
- **Railway部署优化**: 特别优化了Railway等云平台的部署场景
- **向后兼容**: 提供与现有代码的兼容性支持
- **类型安全**: 使用Python类型提示确保代码安全

## 基本用法

### 导入和基本使用

```python
from pathmanager import PathManager

# 获取数据库路径 (自动根据环境切换)
db_path = PathManager.get_database_path()
print(f"数据库路径: {db_path}")

# 获取日志文件路径
log_path = PathManager.get_log_file_path("app")
print(f"应用日志: {log_path}")

# 获取静态文件路径
css_path = PathManager.get_css_file_path("okx-theme.css")
print(f"CSS文件: {css_path}")
```

### 环境信息查询

```python
# 查看当前环境信息
env_info = PathManager.get_environment_info()
print(f"环境信息: {env_info}")

# 检查是否为生产环境
if env_info['is_production']:
    print("运行在生产环境")
else:
    print("运行在开发环境")
```

## 在项目中的应用示例

### 1. 数据库配置 (config.py)

**原有代码：**
```python
def get_db_path() -> str:
    import os
    if os.getenv("NODE_ENV") == "production":
        return "data/lanyangyang.db"
    else:
        return "data/lanyangyang_dev.db"
```

**使用PathManager：**
```python
from pathmanager import PathManager

def get_db_path() -> str:
    return PathManager.get_database_path()

# 或直接使用便捷函数
from pathmanager import get_db_path  # 向后兼容
```

### 2. 数据库初始化 (database/db_init.py)

**原有代码：**
```python
schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
```

**使用PathManager：**
```python
from pathmanager import PathManager

schema_path = PathManager.get_database_schema_path('schema.sql')
migrations_dir = PathManager.get_migration_directory()
```

### 3. Web应用静态文件 (web/app.py)

**原有代码：**
```python
app.mount("/static", StaticFiles(directory="static"), name="static")
```

**使用PathManager：**
```python
from pathmanager import PathManager

static_dir = PathManager.get_static_directory()
app.mount("/static", StaticFiles(directory=static_dir), name="static")
```

### 4. 日志配置

**原有代码：**
```python
LOGGING_CONFIG = {
    "handlers": {
        "file": {
            "filename": "logs/bot.log",
        }
    }
}
```

**使用PathManager：**
```python
from pathmanager import PathManager

LOGGING_CONFIG = {
    "handlers": {
        "file": {
            "filename": PathManager.get_log_file_path("bot"),
        }
    }
}
```

### 5. 备份功能

```python
from pathmanager import PathManager
from datetime import datetime

def backup_database():
    """备份数据库"""
    source_db = PathManager.get_database_path()
    backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    backup_path = PathManager.get_backup_database_path(backup_name)
    
    import shutil
    shutil.copy2(source_db, backup_path)
    print(f"数据库已备份到: {backup_path}")
```

### 6. 文件上传处理

```python
from pathmanager import PathManager

async def save_uploaded_file(file_content: bytes, filename: str):
    """保存上传的文件"""
    upload_path = PathManager.get_uploads_directory()
    file_path = Path(upload_path) / filename
    
    with open(file_path, 'wb') as f:
        f.write(file_content)
    
    return str(file_path)
```

## 环境配置

### 开发环境
```bash
export NODE_ENV=development
# 自动使用: data/lanyangyang_dev.db
```

### 生产环境 (Railway)
```bash
export NODE_ENV=production
# 自动使用: data/lanyangyang.db
```

## 路径API参考

### 数据库相关
- `get_database_path()` - 主数据库路径
- `get_backup_database_path()` - 备份数据库路径
- `get_database_schema_path()` - Schema文件路径
- `get_migration_directory()` - 迁移文件目录

### 日志相关
- `get_logs_directory()` - 日志目录
- `get_log_file_path(log_type)` - 特定类型日志文件路径

### 配置相关
- `get_config_directory()` - 配置目录
- `get_env_file_path()` - 环境变量文件路径
- `get_requirements_path()` - requirements文件路径

### 静态资源
- `get_static_directory()` - 静态文件根目录
- `get_static_file_path(relative_path)` - 静态文件路径
- `get_css_file_path(css_file)` - CSS文件路径
- `get_js_file_path(js_file)` - JavaScript文件路径
- `get_images_directory()` - 图片目录

### Web模板
- `get_templates_directory()` - 模板目录
- `get_template_file_path(template_name)` - 模板文件路径

### 存储相关
- `get_uploads_directory()` - 上传文件目录
- `get_temp_directory()` - 临时文件目录
- `get_cache_directory()` - 缓存目录

### 开发工具
- `get_scripts_directory()` - 脚本目录
- `get_tests_directory()` - 测试目录
- `get_docs_directory()` - 文档目录

## 工具方法

### 路径检查
```python
# 检查路径是否存在
exists = PathManager.path_exists("/some/path")

# 检查是否为文件
is_file = PathManager.is_file("/some/file.txt")

# 检查是否为目录
is_dir = PathManager.is_directory("/some/directory")

# 获取文件大小
size = PathManager.get_file_size("/some/file.txt")
```

### 目录结构创建
```python
# 创建完整的项目目录结构
success = PathManager.create_directory_structure()
if success:
    print("目录结构创建成功")
```

### 部署信息
```python
# 获取部署相关信息 (用于Railway等云平台)
deploy_info = PathManager.get_deployment_info()
print(f"部署信息: {deploy_info}")
```

## 最佳实践

### 1. 在模块初始化时导入
```python
# 在模块顶部导入
from pathmanager import PathManager

# 然后在代码中使用
class DatabaseManager:
    def __init__(self):
        self.db_path = PathManager.get_database_path()
```

### 2. 使用类型提示
```python
from pathmanager import PathManager
from pathlib import Path

def process_file(filename: str) -> Path:
    file_path = PathManager.get_temp_file_path(filename)
    return Path(file_path)
```

### 3. 错误处理
```python
try:
    log_path = PathManager.get_log_file_path("error")
    with open(log_path, 'a') as f:
        f.write("Error message\n")
except Exception as e:
    print(f"无法写入日志: {e}")
```

### 4. 配置文件中使用
```python
from pathmanager import PathManager

# 在配置类中使用
class Config:
    DATABASE_PATH = PathManager.get_database_path()
    LOG_DIR = PathManager.get_logs_directory()
    STATIC_DIR = PathManager.get_static_directory()
```

## 迁移指南

### 从硬编码路径迁移

**原有代码：**
```python
db_path = "data/lanyangyang.db"
log_path = "logs/app.log"
static_path = "static/css/style.css"
```

**迁移后：**
```python
from pathmanager import PathManager

db_path = PathManager.get_database_path()
log_path = PathManager.get_log_file_path("app")
static_path = PathManager.get_css_file_path("style.css")
```

### 从相对路径迁移

**原有代码：**
```python
import os
schema_path = os.path.join(os.path.dirname(__file__), '../database/schema.sql')
```

**迁移后：**
```python
from pathmanager import PathManager

schema_path = PathManager.get_database_schema_path('schema.sql')
```

## 注意事项

1. **自动目录创建**: PathManager会自动创建不存在的目录，确保路径可用
2. **绝对路径**: 所有返回的路径都是绝对路径，避免相对路径问题
3. **环境切换**: 根据 `NODE_ENV` 环境变量自动切换路径配置
4. **Railway兼容**: 特别优化了Railway等云平台的部署需求
5. **向后兼容**: 提供了与现有代码的兼容性函数

## 故障排除

### 常见问题

**Q: 路径不正确？**
A: 检查 `NODE_ENV` 环境变量设置，确保开发/生产环境配置正确。

**Q: 目录不存在？**
A: PathManager会自动创建目录，如果还是不存在，检查文件系统权限。

**Q: Railway部署问题？**
A: 使用 `PathManager.get_deployment_info()` 查看部署信息，确保路径配置正确。

### 调试方法
```python
# 打印所有路径信息
if __name__ == "__main__":
    from pathmanager import PathManager
    
    print("=== PathManager 调试信息 ===")
    print(f"根目录: {PathManager.get_root_directory()}")
    print(f"环境信息: {PathManager.get_environment_info()}")
    print(f"数据库路径: {PathManager.get_database_path()}")
    print(f"部署信息: {PathManager.get_deployment_info()}")
```

这样你就可以在整个项目中使用统一的路径管理系统了！