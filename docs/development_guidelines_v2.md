# V2.0开发指南：唯一接口标准与架构原则

**文档状态**: 当前启用 (202509181800)  
**最后更新**: 2025年9月18日 18:00  
**版本**: V2.0 正式版

## 核心原则

本指南确保所有开发活动严格遵循"**唯一方法、唯一接口、唯一路径、与数据库精准匹配、无冗余**"的架构标准。

---

## 1. 数据库字段命名标准

### ✅ 必须遵循
- **统一字段名**: 全项目使用 `merchant_id` 关联商户
- **精准匹配**: 代码中的字段名必须与数据库schema完全一致
- **无别名混用**: 禁止在不同文件中使用不同的字段名指向同一数据

### ❌ 严格禁止
- 使用 `used_by_merchant_id` 字段名（已废弃）
- 在查询中使用字段别名但在代码中使用原字段名
- 字段名不一致导致的隐式类型转换

### 实施标准
```python
# ✅ 正确：使用统一的 merchant_id
query = """
    SELECT bc.*, m.name as merchant_name, bc.merchant_id
    FROM binding_codes bc
    LEFT JOIN merchants m ON bc.merchant_id = m.id
"""

# ❌ 错误：使用废弃字段名
query = """
    SELECT bc.*, bc.used_by_merchant_id
    FROM binding_codes bc
"""
```

---

## 2. 路由参数类型标准

### ✅ 必须遵循
- **字符串参数**: 路由参数统一使用 `{param}` 格式
- **安全获取**: 使用 `request.path_params.get("param")` 方法
- **无类型强制**: 避免在路由层进行类型转换

### ❌ 严格禁止
- 使用 `{param_id:int}` 整型路由参数
- 直接字典访问 `request.path_params["param"]`
- 在路由层执行 `int()` 等类型转换操作

### 实施标准
```python
# ✅ 正确：字符串参数 + 安全获取
@app.get("/binding-codes/{code}/detail")
async def binding_code_detail(request: Request):
    code = request.path_params.get("code")
    return await binding_codes_manager.get_binding_code_info(code)

# ❌ 错误：整型参数 + 直接访问
@app.get("/binding-codes/{code_id:int}/detail")
async def binding_code_detail(request: Request):
    code_id = request.path_params["code_id"]  # 不安全
    code = str(code_id)  # 不必要的转换
```

---

## 3. 调用链路架构标准

### ✅ 唯一调用链路
```
Route Function → DB Manager → Database
```

### ❌ 禁止的冗余模式
```
Route Function → Service Layer → DB Manager → Database
Route Function → Multiple Managers → Database
```

### 实施标准
```python
# ✅ 正确：直接调用DB Manager
async def binding_codes_list(request: Request):
    codes = await binding_codes_manager.get_all_binding_codes()
    return render_template("binding_codes_list.html", codes=codes)

# ❌ 错误：引入Service层冗余
async def binding_codes_list(request: Request):
    codes = await binding_service.get_all_codes()  # 多余的中间层
    return render_template("binding_codes_list.html", codes=codes)
```

---

## 4. 导入与依赖管理标准

### ✅ 必须遵循
- **最小导入**: 只导入实际使用的模块和函数
- **单一来源**: 每个功能只从一个模块导入
- **及时清理**: 删除未使用的导入语句

### ❌ 严格禁止
- 导入未使用的Service类或模块
- 同时导入多个提供相同功能的模块
- 保留历史遗留的导入语句

### 实施标准
```python
# ✅ 正确：只导入实际使用的Manager
from database.db_binding_codes import binding_codes_manager

# ❌ 错误：导入未使用的Service
from web.services.binding_mgmt_service import BindingMgmtService  # 未使用
from database.db_binding_codes import binding_codes_manager
```

---

## 5. 错误处理标准

### ✅ 必须遵循
- **参数验证**: 使用 `.get()` 方法安全获取参数
- **异常处理**: 明确捕获和处理可能的异常
- **错误信息**: 返回清晰的错误信息给用户

### ❌ 严格禁止
- 假设参数一定存在而直接访问
- 忽略数据库操作可能的异常
- 返回技术性错误信息给最终用户

### 实施标准
```python
# ✅ 正确：安全的参数获取和错误处理
async def binding_code_detail(request: Request):
    code = request.path_params.get("code")
    if not code:
        return error_response("绑定码参数缺失")
    
    try:
        binding_info = await binding_codes_manager.get_binding_code_info(code)
        if not binding_info:
            return error_response("绑定码不存在")
        return render_template("detail.html", binding=binding_info)
    except Exception as e:
        logger.error(f"获取绑定码详情失败: {e}")
        return error_response("系统错误，请稍后重试")

# ❌ 错误：直接访问 + 无错误处理
async def binding_code_detail(request: Request):
    code = request.path_params["code"]  # 可能KeyError
    binding_info = await binding_codes_manager.get_binding_code_info(code)  # 可能抛异常
    return render_template("detail.html", binding=binding_info)  # binding_info可能为None
```

---

## 6. 文件组织与模块标准

### ✅ 必须遵循
- **单一职责**: 每个文件只负责一个明确的功能域
- **清晰分层**: Route → DB Manager → Database 层次清晰
- **无冗余文件**: 删除或重命名不再使用的文件为 `.old`

### ❌ 严格禁止
- 在同一文件中混合不同功能域的代码
- 保留多个实现相同功能的文件
- 在 `__init__.py` 中定义业务逻辑函数

### 实施标准
```python
# ✅ 正确：web/routes/__init__.py 只做导入导出
from . import (
    auth, dashboard, merchants, users, orders,
    reviews, regions, incentives, subscription,
    binding_codes, posts, debug, media
)

__all__ = [
    'auth', 'dashboard', 'merchants', 'users', 'orders',
    'reviews', 'regions', 'incentives', 'subscription',
    'binding_codes', 'posts', 'debug', 'media'
]

# ❌ 错误：在 __init__.py 中定义业务函数
def register_routes(app):  # 不应该在这里定义
    # 注册路由的逻辑...
    pass
```

---

## 7. 数据库操作标准

### ✅ 必须遵循
- **Manager模式**: 所有数据库操作通过专门的Manager类
- **字段一致性**: 查询结果字段名与数据库schema完全匹配
- **参数化查询**: 使用参数化查询防止SQL注入

### ❌ 严格禁止
- 在Route函数中直接编写SQL语句
- 在查询中使用别名但代码中期望原字段名
- 使用字符串拼接构造SQL查询

### 实施标准
```python
# ✅ 正确：通过Manager + 参数化查询
class BindingCodesManager:
    @staticmethod
    async def get_binding_code_info(code: str):
        query = """
            SELECT bc.*, 
                   m.name as merchant_name, 
                   bc.merchant_id
            FROM binding_codes bc
            LEFT JOIN merchants m ON bc.merchant_id = m.id
            WHERE bc.code = ?
        """
        result = await db.fetch_one(query, (code,))
        return dict(result) if result else None

# ❌ 错误：在Route中直接SQL + 字符串拼接
async def binding_code_detail(request: Request):
    code = request.path_params.get("code")
    query = f"SELECT * FROM binding_codes WHERE code = '{code}'"  # SQL注入风险
    result = await db.fetch_one(query)
```

---

## 8. 开发流程检查清单

### 新增功能开发检查
- [ ] 字段名与数据库schema完全匹配
- [ ] 路由参数使用字符串类型
- [ ] 调用链路为 Route → DB Manager
- [ ] 使用安全的参数获取方法
- [ ] 包含适当的错误处理
- [ ] 删除未使用的导入和代码

### 修改现有功能检查
- [ ] 不破坏现有的字段命名约定
- [ ] 不引入新的Service层或中间层
- [ ] 保持路由参数类型的一致性
- [ ] 验证修改不影响其他模块
- [ ] 更新相关文档

### 代码审查检查
- [ ] 是否存在冗余的调用链路
- [ ] 是否有未使用的导入或函数
- [ ] 字段名是否与数据库一致
- [ ] 错误处理是否完善
- [ ] 是否遵循单一职责原则

---

## 9. 违规行为及修复

### 常见违规模式
1. **字段名不一致**: 代码使用 `used_by_merchant_id`，数据库是 `merchant_id`
2. **类型转换错误**: 路由参数为整型但传递给期望字符串的函数
3. **冗余调用链**: Route → Service → Manager → Database
4. **不安全访问**: 直接使用 `request.path_params["key"]`

### 标准修复流程
1. **识别问题**: 通过错误日志或代码审查发现违规
2. **分析影响**: 确定修复范围和可能影响的其他模块
3. **执行修复**: 按照本指南的标准进行修复
4. **验证结果**: 确保修复后功能正常且符合标准
5. **更新文档**: 更新相关文档反映修复内容

---

## 10. 架构演进原则

### 向后兼容性
- 修改必须保持API接口的稳定性
- 数据库字段重命名需要迁移脚本支持
- 废弃功能采用标记 `.old` 后缀的方式

### 性能考虑
- 直接调用DB Manager减少调用层次
- 统一字段名避免不必要的数据转换
- 字符串路由参数减少类型转换开销

### 可维护性
- 单一调用链路降低代码复杂度
- 统一标准减少开发者认知负担
- 清晰的错误处理提高系统稳定性

---

## 附录：快速参考

### 检查命令
```bash
# 检查未使用的导入
grep -r "from.*import" web/routes/ | grep -v "__pycache__"

# 检查字段名一致性
grep -r "used_by_merchant_id" . | grep -v ".old"

# 检查路由参数类型
grep -r "{.*:int}" web/routes/
```

### 常用模式
```python
# 路由函数标准模板
async def route_function(request: Request):
    param = request.path_params.get("param")
    if not param:
        return error_response("参数缺失")
    
    try:
        result = await manager.method(param)
        if not result:
            return error_response("数据不存在")
        return render_template("template.html", data=result)
    except Exception as e:
        logger.error(f"操作失败: {e}")
        return error_response("系统错误")
```

**开发铁律**: 遵循本指南是确保系统架构稳定性和可维护性的强制要求，任何偏离都必须经过架构组审核批准。