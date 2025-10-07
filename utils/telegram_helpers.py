"""
Telegram消息处理辅助函数
提供安全的消息更新方法，处理常见的Telegram API错误
"""

import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


async def safe_edit_message(message, new_content: str, reply_markup=None, parse_mode=None) -> bool:
    """
    安全更新消息，处理"message is not modified"错误
    
    Args:
        message: 要更新的消息对象
        new_content: 新的消息内容
        reply_markup: 可选的回复键盘
        parse_mode: 可选的解析模式
        
    Returns:
        bool: 是否成功更新消息
    """
    try:
        # 检查内容是否真的改变了
        current_text = getattr(message, 'text', '') or getattr(message, 'caption', '') or ''
        current_markup = getattr(message, 'reply_markup', None)
        
        # 比较文本内容和键盘是否相同
        text_changed = current_text.strip() != new_content.strip()
        markup_changed = (current_markup != reply_markup)
        
        if not text_changed and not markup_changed:
            logger.debug("消息内容未改变，跳过更新")
            return True
            
        # 统一禁用链接预览，避免触发官方预览卡片
        try:
            await message.edit_text(
                new_content,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=True,
            )
        except TypeError:
            # 兼容旧版/新参数名（aiogram>=3 使用 link_preview_options）
            try:
                from aiogram.types import LinkPreviewOptions  # type: ignore
                await message.edit_text(
                    new_content,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
            except Exception as e2:
                logger.error(f"更新消息时设置禁用预览失败: {e2}")
                raise
        return True
        
    except Exception as e:
        # 专门处理"message is not modified"错误
        error_msg = str(e).lower()
        if "message is not modified" in error_msg or "bad request: message is not modified" in error_msg:
            logger.debug(f"消息内容相同，跳过更新: {e}")
            return True
        else:
            logger.error(f"更新消息失败: {e}")
            raise e


async def safe_answer_callback(callback, text: str, show_alert: bool = False) -> bool:
    """
    安全回复回调查询，处理可能的错误
    
    Args:
        callback: 回调查询对象
        text: 回复文本
        show_alert: 是否显示弹窗
        
    Returns:
        bool: 是否成功回复
    """
    try:
        await callback.answer(text, show_alert=show_alert)
        return True
    except Exception as e:
        logger.warning(f"回复回调查询失败: {e}")
        return False
