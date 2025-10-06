# -*- coding: utf-8 -*-
"""
自动回复服务层
封装 AutoReplyManager 的调用与最小校验，供 Web 路由使用。

遵循三层结构：Route 仅做参数解析/CSRF；Service 调用 DB 并返回结构；UI 只渲染。
"""

from typing import Any, Dict, List, Optional
import logging

from database.db_auto_reply import auto_reply_manager

logger = logging.getLogger(__name__)


class AutoReplyService:
    @staticmethod
    async def list_triggers(include_messages: bool = True) -> List[Dict[str, Any]]:
        try:
            if include_messages:
                return await auto_reply_manager.get_all_triggers()
            return await auto_reply_manager.get_all_active_triggers()
        except Exception as e:
            logger.error(f"获取触发词列表失败: {e}")
            return []

    @staticmethod
    async def create_trigger(trigger_text: str, match_type: str, priority_order: int, is_active: bool, admin_id: int) -> Dict[str, Any]:
        try:
            trigger_id = await auto_reply_manager.create_trigger(
                trigger_text=trigger_text,
                match_type=match_type,
                created_by=admin_id,
                priority_order=priority_order,
                is_active=is_active,
            )
            if trigger_id:
                return {"success": True, "id": trigger_id}
            return {"success": False, "error": "创建触发词失败"}
        except Exception as e:
            logger.error(f"创建触发词异常: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def update_trigger(trigger_id: int, trigger_text: Optional[str] = None, match_type: Optional[str] = None,
                             priority_order: Optional[int] = None, is_active: Optional[bool] = None) -> Dict[str, Any]:
        try:
            ok = await auto_reply_manager.update_trigger(
                trigger_id=trigger_id,
                trigger_text=trigger_text,
                match_type=match_type,
                is_active=is_active,
                priority_order=priority_order,
            )
            return {"success": bool(ok)} if ok else {"success": False, "error": "更新失败"}
        except Exception as e:
            logger.error(f"更新触发词异常: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def delete_trigger(trigger_id: int) -> Dict[str, Any]:
        try:
            ok = await auto_reply_manager.delete_trigger(trigger_id)
            return {"success": bool(ok)} if ok else {"success": False, "error": "删除失败"}
        except Exception as e:
            logger.error(f"删除触发词异常: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def create_message(trigger_id: int, message_content: str, display_order: int, is_active: bool) -> Dict[str, Any]:
        try:
            msg_id = await auto_reply_manager.create_message(trigger_id, message_content, display_order, is_active)
            if msg_id:
                return {"success": True, "id": msg_id}
            return {"success": False, "error": "创建消息失败"}
        except Exception as e:
            logger.error(f"创建消息异常: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def update_message(message_id: int, message_content: Optional[str] = None, display_order: Optional[int] = None,
                             is_active: Optional[bool] = None) -> Dict[str, Any]:
        try:
            ok = await auto_reply_manager.update_message(message_id, message_content, is_active, display_order)
            return {"success": bool(ok)} if ok else {"success": False, "error": "更新失败"}
        except Exception as e:
            logger.error(f"更新消息异常: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def delete_message(message_id: int) -> Dict[str, Any]:
        try:
            ok = await auto_reply_manager.delete_message(message_id)
            return {"success": bool(ok)} if ok else {"success": False, "error": "删除失败"}
        except Exception as e:
            logger.error(f"删除消息异常: {e}")
            return {"success": False, "error": str(e)}

