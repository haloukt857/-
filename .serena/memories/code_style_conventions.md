# 代码风格和约定

## 编程语言和版本
- Python 3.12+
- 异步编程模式（async/await）
- 类型提示（typing模块）

## 代码格式化工具
- **Black** - 代码格式化标准
- **Flake8** - 代码风格检查
- **MyPy** - 静态类型检查

## 命名约定
- **文件名**: 小写字母+下划线（如 `db_merchants.py`）
- **类名**: PascalCase（如 `MerchantManager`）
- **函数名**: 小写字母+下划线（如 `get_merchant`）
- **变量名**: 小写字母+下划线（如 `merchant_id`）
- **常量**: 大写字母+下划线（如 `MERCHANT_STATUS`）

## 文件组织模式
- 每个模块都有对应的管理器类（如 `merchant_manager`）
- 数据库操作集中在 `database/` 目录下
- Web路由分模块组织在 `web/routes/` 下
- 配置集中在 `config.py` 文件中

## 异常处理模式
```python
try:
    # 业务逻辑
    result = await manager.some_operation()
    return result
except Exception as e:
    logger.error(f"操作失败: {e}")
    # 适当的错误处理
```

## 日志记录
- 使用Python标准logging模块
- 日志级别：DEBUG、INFO、WARNING、ERROR
- 格式：`logger.info(f"描述性消息: {变量}")`

## 数据库操作规范
- 所有数据库操作都是异步的
- 使用连接池管理数据库连接
- 通过专门的Manager类封装数据库操作
- **重要**: 只能通过迁移脚本修改数据库结构

## Web组件规范
- 使用FastHTML + TailwindCSS + DaisyUI
- 统一的组件函数（如 `okx_input`, `okx_button`）
- 认证装饰器 `@require_auth` 保护管理页面
- 统一的布局函数 `create_layout`

## 文档字符串
```python
async def some_function(param: str) -> Dict[str, Any]:
    """
    函数的简短描述
    
    Args:
        param: 参数描述
        
    Returns:
        返回值描述
    """
```