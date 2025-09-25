# -*- coding: utf-8 -*-
"""
消息模板数据库管理器
提供统一的、后台可配置的模板引擎，根除硬编码用户可见文本
"""

import logging
from typing import Dict, Optional, List, Any
from datetime import datetime

# 导入数据库管理器
from database.db_connection import db_manager

logger = logging.getLogger(__name__)


class TemplateManager:
    """模板管理器 - 统一消息模板引擎"""
    
    @staticmethod
    async def get_template(key: str, default: str = None) -> str:
        """
        核心方法：获取模板内容
        
        Args:
            key: 模板键值
            default: 默认值，如果未提供且模板不存在，返回错误提示
            
        Returns:
            模板内容字符串
        """
        try:
            query = "SELECT content FROM templates WHERE key = ?"
            result = await db_manager.fetch_one(query, (key,))
            
            if result:
                return result['content']
            
            # 模板不存在的处理
            if default is not None:
                return default
            else:
                # 返回明确的错误提示
                error_msg = f"[模板缺失: {key}]"
                logger.warning(f"模板键 '{key}' 不存在，返回错误提示")
                return error_msg
                
        except Exception as e:
            logger.error(f"获取模板失败 {key}: {e}")
            return default or f"[模板错误: {key}]"
    
    @staticmethod
    async def add_template(key: str, content: str) -> bool:
        """
        添加新模板
        
        Args:
            key: 模板键值，必须唯一
            content: 模板内容
            
        Returns:
            添加是否成功
        """
        try:
            # 检查键是否已存在
            existing = await TemplateManager.get_template_info(key)
            if existing:
                logger.warning(f"模板键 '{key}' 已存在，无法添加")
                return False
            
            query = """
                INSERT INTO templates (key, content, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """
            
            await db_manager.execute_query(query, (key, content))
            logger.info(f"成功添加模板: {key}")
            return True
            
        except Exception as e:
            logger.error(f"添加模板失败 {key}: {e}")
            return False
    
    @staticmethod
    async def get_all_templates() -> List[Dict[str, Any]]:
        """
        获取所有模板信息（管理后台用）
        
        Returns:
            包含完整模板信息的列表
        """
        try:
            query = """
                SELECT key, content, updated_at 
                FROM templates 
                ORDER BY key
            """
            results = await db_manager.fetch_all(query)
            
            templates = []
            if results:
                for row in results:
                    templates.append(dict(row))
            
            logger.debug(f"获取到 {len(templates)} 个模板")
            return templates
            
        except Exception as e:
            logger.error(f"获取所有模板失败: {e}")
            return []
    
    @staticmethod
    async def get_template_info(key: str) -> Optional[Dict[str, Any]]:
        """
        获取单个模板的完整信息
        
        Args:
            key: 模板键值
            
        Returns:
            模板信息字典或None
        """
        try:
            query = """
                SELECT key, content, updated_at 
                FROM templates 
                WHERE key = ?
            """
            result = await db_manager.fetch_one(query, (key,))
            
            if result:
                return dict(result)
            return None
            
        except Exception as e:
            logger.error(f"获取模板信息失败 {key}: {e}")
            return None
    
    @staticmethod
    async def update_template(key: str, content: str) -> bool:
        """
        更新现有模板内容
        
        Args:
            key: 模板键值
            content: 新的模板内容
            
        Returns:
            更新是否成功
        """
        try:
            # 检查模板是否存在
            existing = await TemplateManager.get_template_info(key)
            if not existing:
                logger.warning(f"模板键 '{key}' 不存在，无法更新")
                return False
            
            query = """
                UPDATE templates 
                SET content = ?
                WHERE key = ?
            """
            
            result = await db_manager.execute_query(query, (content, key))
            
            if result > 0:
                logger.info(f"成功更新模板: {key}")
                return True
            else:
                logger.warning(f"更新模板失败，可能不存在: {key}")
                return False
                
        except Exception as e:
            logger.error(f"更新模板失败 {key}: {e}")
            return False
    
    @staticmethod
    async def delete_template(key: str) -> bool:
        """
        删除模板
        
        Args:
            key: 模板键值
            
        Returns:
            删除是否成功
        """
        try:
            # 检查模板是否存在
            existing = await TemplateManager.get_template_info(key)
            if not existing:
                logger.warning(f"模板键 '{key}' 不存在，无法删除")
                return False
            
            query = "DELETE FROM templates WHERE key = ?"
            result = await db_manager.execute_query(query, (key,))
            
            if result > 0:
                logger.info(f"成功删除模板: {key}")
                return True
            else:
                logger.warning(f"删除模板失败: {key}")
                return False
                
        except Exception as e:
            logger.error(f"删除模板失败 {key}: {e}")
            return False
    
    @staticmethod
    async def template_exists(key: str) -> bool:
        """
        检查模板是否存在
        
        Args:
            key: 模板键值
            
        Returns:
            模板是否存在
        """
        try:
            query = "SELECT 1 FROM templates WHERE key = ? LIMIT 1"
            result = await db_manager.fetch_one(query, (key,))
            return result is not None
            
        except Exception as e:
            logger.error(f"检查模板存在失败 {key}: {e}")
            return False
    
    @staticmethod
    async def get_templates_by_prefix(prefix: str) -> List[Dict[str, Any]]:
        """
        根据键前缀获取模板列表（用于分类管理）
        
        Args:
            prefix: 键前缀
            
        Returns:
            匹配的模板列表
        """
        try:
            query = """
                SELECT key, content, updated_at 
                FROM templates 
                WHERE key LIKE ? 
                ORDER BY key
            """
            results = await db_manager.fetch_all(query, (f"{prefix}%",))
            
            templates = []
            if results:
                for row in results:
                    templates.append(dict(row))
            
            logger.debug(f"找到 {len(templates)} 个前缀为 '{prefix}' 的模板")
            return templates
            
        except Exception as e:
            logger.error(f"按前缀获取模板失败 {prefix}: {e}")
            return []
    
    @staticmethod
    async def bulk_create_templates(templates: Dict[str, str]) -> int:
        """
        批量创建模板（用于初始化和迁移）
        
        Args:
            templates: 模板键值对字典
            
        Returns:
            成功创建的模板数量
        """
        try:
            created_count = 0
            
            for key, content in templates.items():
                # 检查是否已存在
                if not await TemplateManager.template_exists(key):
                    if await TemplateManager.add_template(key, content):
                        created_count += 1
                else:
                    logger.debug(f"模板 '{key}' 已存在，跳过创建")
            
            logger.info(f"批量创建了 {created_count} 个模板")
            return created_count
            
        except Exception as e:
            logger.error(f"批量创建模板失败: {e}")
            return 0
    
    @staticmethod
    async def get_template_statistics() -> Dict[str, int]:
        """
        获取模板统计信息（管理后台用）
        
        Returns:
            统计信息字典
        """
        try:
            stats = {}
            
            # 总模板数
            result = await db_manager.fetch_one("SELECT COUNT(*) as count FROM templates")
            stats['total_templates'] = result['count'] if result else 0
            
            # 按前缀分组统计（常见的分类）
            common_prefixes = ['welcome_', 'error_', 'success_', 'help_', 'admin_', 'user_']
            
            for prefix in common_prefixes:
                query = "SELECT COUNT(*) as count FROM templates WHERE key LIKE ?"
                result = await db_manager.fetch_one(query, (f"{prefix}%",))
                stats[f'{prefix}templates'] = result['count'] if result else 0
            
            # 最近更新的模板数（近7天）
            recent_query = """
                SELECT COUNT(*) as count FROM templates 
                WHERE updated_at >= datetime('now', '-7 days')
            """
            result = await db_manager.fetch_one(recent_query)
            stats['recent_updates'] = result['count'] if result else 0
            
            logger.debug(f"模板统计信息获取成功")
            return stats
            
        except Exception as e:
            logger.error(f"获取模板统计失败: {e}")
            return {}
    
    @staticmethod
    async def initialize_default_templates():
        """
        初始化默认模板（系统启动时调用）
        """
        try:
            # 定义系统必需的默认模板
            default_templates = {
                # 基础交互模板
                'welcome_message': '🎉 欢迎使用本系统！',
                'help_message': 'ℹ️ 这里是帮助信息。',
                'unknown_command': '❓ 抱歉，我不理解这个指令。',
                
                # 错误处理模板
                'error_system': '❌ 系统发生错误，请稍后重试。',
                'error_permission': '🚫 您没有权限执行此操作。',
                'error_invalid_input': '⚠️ 输入格式不正确，请检查后重试。',
                
                # 绑定相关模板
                'error_invalid_bind_code': '❌ 绑定码无效或已被使用。',
                'bind_success': '✅ 绑定成功！您的永久商户ID是 **{merchant_id}**。',
                
                # 操作成功模板
                'success_operation': '✅ 操作成功！',
                'success_save': '✅ 保存成功！',
                'success_delete': '✅ 删除成功！',
                
                # 管理员模板
                'admin_welcome': '🔧 管理员面板已启用。',
                'admin_unauthorized': '🚫 仅管理员可使用此功能。'
            }
            
            # 批量创建默认模板
            created_count = await TemplateManager.bulk_create_templates(default_templates)
            logger.info(f"默认模板初始化完成，创建了 {created_count} 个新模板")
            
            return created_count
            
        except Exception as e:
            logger.error(f"初始化默认模板失败: {e}")
            return 0


# 创建全局实例
template_manager = TemplateManager()

# V1兼容性便捷函数
async def get_template(key: str, default: str = None) -> str:
    """获取模板的便捷函数"""
    return await template_manager.get_template(key, default)

async def save_template(key: str, content: str) -> bool:
    """保存模板的便捷函数（V1兼容）"""
    # 如果已存在则更新，否则创建
    if await template_manager.template_exists(key):
        return await template_manager.update_template(key, content)
    else:
        return await template_manager.add_template(key, content)

async def get_all_templates() -> List[Dict[str, Any]]:
    """获取所有模板的便捷函数"""
    return await template_manager.get_all_templates()