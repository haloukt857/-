"""
模板工具函数
强制使用数据库动态模板，无降级处理
"""

import logging
import sqlite3
import os
from pathmanager import PathManager

logger = logging.getLogger(__name__)

def get_template_sync(template_key: str, **format_args) -> str:
    """
    同步获取模板内容（直接查询数据库）
    
    Args:
        template_key: 模板键名
        **format_args: 格式化参数
        
    Returns:
        格式化后的模板内容
    """
    try:
        # 使用项目统一的数据库路径，确保与db_manager一致
        db_path = PathManager.get_database_path()
        
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT content FROM templates WHERE key = ?', (template_key,))
            result = cursor.fetchone()
            
            if not result:
                logger.error(f"模板 {template_key} 在数据库中不存在")
                raise RuntimeError(f"模板 {template_key} 不存在")
            
            template_content = result['content']
            # 兼容：迁移脚本中写入的字符串若包含字面"\n"，转换为真实换行
            if isinstance(template_content, str):
                if "\\n" in template_content:
                    template_content = template_content.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")
            
            # 格式化模板
            if format_args:
                return template_content.format(**format_args)
            else:
                return template_content
        
    except KeyError as e:
        logger.error(f"模板格式化缺少参数 {template_key}: {e}")
        raise
    except Exception as e:
        logger.error(f"获取模板失败 {template_key}: {e}")
        raise

async def get_template_async(template_key: str, **format_args) -> str:
    """
    异步获取模板内容（调用同步版本）
    
    Args:
        template_key: 模板键名  
        **format_args: 格式化参数
        
    Returns:
        格式化后的模板内容
    """
    return get_template_sync(template_key, **format_args)

def ensure_template_manager():
    """
    确保TemplateManager已初始化
    """
    try:
        from template_manager import TemplateManager
        
        if not TemplateManager.is_initialized():
            logger.info("模板管理器未初始化，尝试初始化...")
            import asyncio
            
            # 在事件循环中初始化
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已有事件循环，创建任务
                asyncio.create_task(TemplateManager.initialize())
            else:
                # 否则运行完整初始化
                asyncio.run(TemplateManager.initialize())
                
            logger.info("模板管理器初始化完成")
            
    except Exception as e:
        logger.error(f"初始化模板管理器失败: {e}")

# 为向后兼容性提供的快捷函数
def get_binding_code_request(admin_username: str = "管理员") -> str:
    """获取绑定码请求消息"""
    return get_template("binding_code_request", admin_username=admin_username)

def get_merchant_info_template(**kwargs) -> str:
    """获取商户信息模板"""
    return get_template("merchant_info_template", **kwargs)
