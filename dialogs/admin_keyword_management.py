"""
管理员关键词管理对话流程
提供关键词的完整CRUD管理功能
"""

import logging
from typing import Dict, List, Optional, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.db_keywords import KeywordManagerExtended
from config import MESSAGE_TEMPLATES

logger = logging.getLogger(__name__)


class AdminKeywordManagement:
    """管理员关键词管理对话流程"""
    
    def __init__(self):
        self.keyword_manager = KeywordManagerExtended()
        # 临时状态存储
        self.user_states: Dict[int, Dict] = {}
    
    async def initialize(self):
        """初始化管理器"""
        # V2管理器无需初始化，直接可用
        logger.info("管理员关键词管理系统初始化完成")
    
    def _get_user_state(self, user_id: int) -> Dict:
        """获取用户状态"""
        if user_id not in self.user_states:
            self.user_states[user_id] = {
                'action': None,
                'selected_keyword_id': None,
                'editing_data': {}
            }
        return self.user_states[user_id]
    
    def _clear_user_state(self, user_id: int):
        """清除用户状态"""
        if user_id in self.user_states:
            del self.user_states[user_id]
    
    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """显示关键词管理主菜单"""
        try:
            # 获取关键词统计
            total_keywords = await self.keyword_manager.count_keywords()
            active_keywords = await self.keyword_manager.count_keywords(only_active=True)
            
            keyboard = [
                [
                    InlineKeyboardButton("📝 查看关键词", callback_data="admin_keyword_list"),
                    InlineKeyboardButton("➕ 添加关键词", callback_data="admin_keyword_add")
                ],
                [
                    InlineKeyboardButton("🏷️ 分类管理", callback_data="admin_keyword_categories"),
                    InlineKeyboardButton("📊 使用统计", callback_data="admin_keyword_stats")
                ],
                [
                    InlineKeyboardButton("🔄 批量操作", callback_data="admin_keyword_batch"),
                    InlineKeyboardButton("📤 导入导出", callback_data="admin_keyword_import_export")
                ],
                [InlineKeyboardButton("↩️ 返回管理菜单", callback_data="admin_main")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = (
                "🏷️ 关键词管理系统\n\n"
                f"📊 统计概览:\n"
                f"• 总关键词数: {total_keywords}\n"
                f"• 激活关键词: {active_keywords}\n"
                f"• 禁用关键词: {total_keywords - active_keywords}\n\n"
                "选择管理操作：\n"
                "• 查看关键词 - 浏览和编辑现有关键词\n"
                "• 添加关键词 - 创建新的关键词\n"
                "• 分类管理 - 管理关键词分类\n"
                "• 使用统计 - 查看关键词选择统计\n"
                "• 批量操作 - 批量启用/禁用/删除\n"
                "• 导入导出 - 批量导入或导出关键词"
            )
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    text=message,
                    reply_markup=reply_markup,
                    parse_mode=None
                )
            else:
                await update.message.reply_text(
                    text=message,
                    reply_markup=reply_markup,
                    parse_mode=None
                )
            
            return True
            
        except Exception as e:
            logger.error(f"显示关键词管理主菜单失败: {e}")
            return False
    
    async def handle_keyword_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1) -> bool:
        """处理关键词列表显示"""
        try:
            per_page = 8
            offset = (page - 1) * per_page
            
            keywords = await self.keyword_manager.get_all_keywords(limit=per_page, offset=offset)
            total_count = await self.keyword_manager.count_keywords()
            total_pages = (total_count + per_page - 1) // per_page
            
            keyboard = []
            
            # 添加关键词按钮
            for keyword in keywords:
                status_icon = "✅" if keyword['is_active'] else "❌"
                usage_info = f"({keyword['usage_count']}次)" if keyword['usage_count'] > 0 else ""
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"{status_icon} {keyword['name']} {usage_info}",
                        callback_data=f"admin_keyword_edit_{keyword['id']}"
                    )
                ])
            
            # 分页按钮
            if total_pages > 1:
                nav_buttons = []
                if page > 1:
                    nav_buttons.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f"admin_keyword_list_{page-1}"))
                if page < total_pages:
                    nav_buttons.append(InlineKeyboardButton("➡️ 下一页", callback_data=f"admin_keyword_list_{page+1}"))
                if nav_buttons:
                    keyboard.append(nav_buttons)
            
            # 操作按钮
            keyboard.extend([
                [
                    InlineKeyboardButton("➕ 添加关键词", callback_data="admin_keyword_add"),
                    InlineKeyboardButton("📊 分类统计", callback_data="admin_keyword_category_stats")
                ],
                [
                    InlineKeyboardButton("🔄 刷新列表", callback_data="admin_keyword_list"),
                    InlineKeyboardButton("↩️ 返回主菜单", callback_data="admin_keyword_main")
                ]
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = (
                f"📝 关键词列表 (第 {page}/{total_pages} 页)\n\n"
                f"共 {total_count} 个关键词\n\n"
                "点击关键词进行编辑：\n"
                "✅ = 激活  ❌ = 禁用\n"
                "数字表示被选择次数"
            )
            
            await update.callback_query.edit_message_text(
                text=message,
                reply_markup=reply_markup,
                parse_mode=None
            )
            
            return True
            
        except Exception as e:
            logger.error(f"显示关键词列表失败: {e}")
            await update.callback_query.answer("❌ 加载关键词列表失败", show_alert=True)
            return False
    
    async def handle_add_keyword(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """开始添加关键词流程"""
        try:
            user_id = update.effective_user.id
            state = self._get_user_state(user_id)
            state['action'] = 'adding_keyword'
            
            keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="admin_keyword_list")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = (
                "➕ 添加新关键词\n\n"
                "请输入关键词名称：\n\n"
                "💡 输入要求:\n"
                "• 1-20个字符\n"
                "• 建议使用描述性词汇\n"
                "• 避免重复现有关键词\n\n"
                "示例:\n"
                "• 美食推荐\n"
                "• 生活服务\n"
                "• 娱乐休闲\n"
                "• 购物优惠"
            )
            
            await update.callback_query.edit_message_text(
                text=message,
                reply_markup=reply_markup,
                parse_mode=None
            )
            
            return True
            
        except Exception as e:
            logger.error(f"开始添加关键词流程失败: {e}")
            return False
    
    async def handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """处理文本输入"""
        try:
            user_id = update.effective_user.id
            state = self._get_user_state(user_id)
            text = update.message.text.strip()
            
            if state['action'] == 'adding_keyword':
                return await self._process_add_keyword(update, context, text)
            elif state['action'] == 'editing_keyword_name':
                return await self._process_edit_keyword_name(update, context, text)
            elif state['action'] == 'editing_keyword_description':
                return await self._process_edit_keyword_description(update, context, text)
            elif state['action'] == 'setting_keyword_category':
                return await self._process_set_keyword_category(update, context, text)
            
            return False
            
        except Exception as e:
            logger.error(f"处理文本输入失败: {e}")
            return False
    
    async def _process_add_keyword(self, update: Update, context: ContextTypes.DEFAULT_TYPE, name: str) -> bool:
        """处理添加关键词"""
        try:
            user_id = update.effective_user.id
            
            # 验证输入
            if len(name) < 1 or len(name) > 20:
                await update.message.reply_text(
                    "❌ 关键词长度必须在1-20个字符之间！\n请重新输入：",
                    parse_mode=None
                )
                return True
            
            # 检查是否已存在
            existing = await self.keyword_manager.get_keyword_by_name(name)
            if existing:
                await update.message.reply_text(
                    f"❌ 关键词 '{name}' 已经存在！\n请输入不同的名称：",
                    parse_mode=None
                )
                return True
            
            # 添加关键词
            keyword_id = await self.keyword_manager.create_keyword(
                name=name,
                description="",
                category="未分类"
            )
            
            if keyword_id:
                self._clear_user_state(user_id)
                
                keyboard = [
                    [InlineKeyboardButton("✏️ 编辑详情", callback_data=f"admin_keyword_edit_{keyword_id}")],
                    [InlineKeyboardButton("➕ 继续添加", callback_data="admin_keyword_add")],
                    [InlineKeyboardButton("📝 查看列表", callback_data="admin_keyword_list")],
                    [InlineKeyboardButton("↩️ 返回主菜单", callback_data="admin_keyword_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"✅ 添加成功！\n\n"
                    f"关键词: {name}\n"
                    f"ID: {keyword_id}\n"
                    f"状态: 已激活\n\n"
                    "你可以继续编辑详情或添加更多关键词。",
                    reply_markup=reply_markup,
                    parse_mode=None
                )
                return True
            else:
                await update.message.reply_text("❌ 添加关键词失败，请重试")
                return False
                
        except Exception as e:
            logger.error(f"添加关键词失败: {e}")
            await update.message.reply_text("❌ 添加关键词时发生错误")
            return False
    
    async def handle_edit_keyword(self, update: Update, context: ContextTypes.DEFAULT_TYPE, keyword_id: int) -> bool:
        """处理编辑关键词"""
        try:
            keyword = await self.keyword_manager.get_keyword_by_id(keyword_id)
            if not keyword:
                await update.callback_query.answer("❌ 关键词不存在", show_alert=True)
                return False
            
            keyboard = [
                [
                    InlineKeyboardButton("✏️ 编辑名称", callback_data=f"admin_keyword_edit_name_{keyword_id}"),
                    InlineKeyboardButton("📝 编辑描述", callback_data=f"admin_keyword_edit_desc_{keyword_id}")
                ],
                [
                    InlineKeyboardButton("🏷️ 设置分类", callback_data=f"admin_keyword_set_category_{keyword_id}"),
                    InlineKeyboardButton("📊 设置排序", callback_data=f"admin_keyword_set_order_{keyword_id}")
                ],
                [
                    InlineKeyboardButton(
                        "🔄 切换状态" if keyword['is_active'] else "✅ 启用关键词",
                        callback_data=f"admin_keyword_toggle_{keyword_id}"
                    )
                ],
                [
                    InlineKeyboardButton("📊 使用统计", callback_data=f"admin_keyword_usage_stats_{keyword_id}"),
                    InlineKeyboardButton("🔍 查看引用", callback_data=f"admin_keyword_references_{keyword_id}")
                ],
                [InlineKeyboardButton("🗑️ 删除关键词", callback_data=f"admin_keyword_delete_confirm_{keyword_id}")],
                [InlineKeyboardButton("↩️ 返回列表", callback_data="admin_keyword_list")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            status = "✅ 激活" if keyword['is_active'] else "❌ 禁用"
            message = (
                f"✏️ 编辑关键词\n\n"
                f"名称: {keyword['name']}\n"
                f"描述: {keyword['description'] or '无'}\n"
                f"分类: {keyword['category']}\n"
                f"状态: {status}\n"
                f"排序: {keyword['display_order']}\n"
                f"使用次数: {keyword['usage_count']}\n"
                f"创建时间: {keyword['created_at'][:19]}\n"
                f"更新时间: {keyword['updated_at'][:19]}\n\n"
                "选择要编辑的内容："
            )
            
            await update.callback_query.edit_message_text(
                text=message,
                reply_markup=reply_markup,
                parse_mode=None
            )
            
            return True
            
        except Exception as e:
            logger.error(f"编辑关键词失败: {e}")
            await update.callback_query.answer("❌ 加载关键词信息失败", show_alert=True)
            return False
    
    async def handle_toggle_keyword(self, update: Update, context: ContextTypes.DEFAULT_TYPE, keyword_id: int) -> bool:
        """切换关键词状态"""
        try:
            keyword = await self.keyword_manager.get_keyword_by_id(keyword_id)
            if not keyword:
                await update.callback_query.answer("❌ 关键词不存在", show_alert=True)
                return False
            
            new_status = not keyword['is_active']
            success = await self.keyword_manager.update_keyword_status(keyword_id, new_status)
            
            if success:
                status_text = "激活" if new_status else "禁用"
                await update.callback_query.answer(f"✅ 关键词已{status_text}")
                # 刷新编辑界面
                return await self.handle_edit_keyword(update, context, keyword_id)
            else:
                await update.callback_query.answer("❌ 更新失败", show_alert=True)
                return False
                
        except Exception as e:
            logger.error(f"切换关键词状态失败: {e}")
            await update.callback_query.answer("❌ 操作失败", show_alert=True)
            return False
    
    async def handle_delete_keyword_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE, keyword_id: int) -> bool:
        """确认删除关键词"""
        try:
            keyword = await self.keyword_manager.get_keyword_by_id(keyword_id)
            if not keyword:
                await update.callback_query.answer("❌ 关键词不存在", show_alert=True)
                return False
            
            # 检查是否有商家使用
            usage_count = keyword['usage_count']
            
            keyboard = [
                [InlineKeyboardButton("⚠️ 确认删除", callback_data=f"admin_keyword_delete_confirmed_{keyword_id}")],
                [InlineKeyboardButton("❌ 取消", callback_data=f"admin_keyword_edit_{keyword_id}")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            warning_message = (
                f"⚠️ 确认删除关键词？\n\n"
                f"名称: {keyword['name']}\n"
                f"使用次数: {usage_count}\n\n"
            )
            
            if usage_count > 0:
                warning_message += (
                    f"❗ 警告:\n"
                    f"该关键词已被使用 {usage_count} 次！\n"
                    f"删除后相关的商家关键词关联将被移除。\n\n"
                )
            
            warning_message += "删除操作不可恢复，请谨慎操作！"
            
            await update.callback_query.edit_message_text(
                text=warning_message,
                reply_markup=reply_markup,
                parse_mode=None
            )
            
            return True
            
        except Exception as e:
            logger.error(f"显示删除确认失败: {e}")
            await update.callback_query.answer("❌ 操作失败", show_alert=True)
            return False
    
    async def handle_delete_keyword_confirmed(self, update: Update, context: ContextTypes.DEFAULT_TYPE, keyword_id: int) -> bool:
        """执行删除关键词"""
        try:
            keyword = await self.keyword_manager.get_keyword_by_id(keyword_id)
            if not keyword:
                await update.callback_query.answer("❌ 关键词不存在", show_alert=True)
                return False
            
            success = await self.keyword_manager.delete_keyword(keyword_id)
            
            if success:
                await update.callback_query.answer("✅ 关键词已删除")
                
                keyboard = [[InlineKeyboardButton("📝 返回列表", callback_data="admin_keyword_list")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.callback_query.edit_message_text(
                    text=f"✅ 删除成功\n\n关键词 '{keyword['name']}' 已被删除",
                    reply_markup=reply_markup,
                    parse_mode=None
                )
                return True
            else:
                await update.callback_query.answer("❌ 删除失败", show_alert=True)
                return False
                
        except Exception as e:
            logger.error(f"删除关键词失败: {e}")
            await update.callback_query.answer("❌ 删除时发生错误", show_alert=True)
            return False
    
    async def show_keyword_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """显示关键词分类管理"""
        try:
            categories = await self.keyword_manager.get_keyword_categories()
            
            keyboard = []
            for category, count in categories.items():
                keyboard.append([
                    InlineKeyboardButton(
                        f"🏷️ {category} ({count}个)",
                        callback_data=f"admin_keyword_view_category_{category}"
                    )
                ])
            
            keyboard.extend([
                [
                    InlineKeyboardButton("➕ 新建分类", callback_data="admin_keyword_add_category"),
                    InlineKeyboardButton("🔄 重命名分类", callback_data="admin_keyword_rename_category")
                ],
                [
                    InlineKeyboardButton("🗂️ 分类统计", callback_data="admin_keyword_category_stats"),
                    InlineKeyboardButton("↩️ 返回主菜单", callback_data="admin_keyword_main")
                ]
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = (
                "🏷️ 关键词分类管理\n\n"
                f"当前共有 {len(categories)} 个分类\n\n"
                "点击分类查看关键词，或进行分类管理："
            )
            
            await update.callback_query.edit_message_text(
                text=message,
                reply_markup=reply_markup,
                parse_mode=None
            )
            
            return True
            
        except Exception as e:
            logger.error(f"显示关键词分类失败: {e}")
            await update.callback_query.answer("❌ 加载分类失败", show_alert=True)
            return False
    
    async def show_keyword_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """显示关键词使用统计"""
        try:
            # 获取统计数据
            total_keywords = await self.keyword_manager.count_keywords()
            active_keywords = await self.keyword_manager.count_keywords(only_active=True)
            
            # 获取最受欢迎的关键词
            popular_keywords = await self.keyword_manager.get_popular_keywords(limit=5)
            
            # 获取分类统计
            categories = await self.keyword_manager.get_keyword_categories()
            
            keyboard = [
                [
                    InlineKeyboardButton("📊 详细统计", callback_data="admin_keyword_detailed_stats"),
                    InlineKeyboardButton("📈 使用趋势", callback_data="admin_keyword_usage_trends")
                ],
                [
                    InlineKeyboardButton("🔄 刷新数据", callback_data="admin_keyword_stats"),
                    InlineKeyboardButton("↩️ 返回主菜单", callback_data="admin_keyword_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = (
                f"📊 关键词使用统计\n\n"
                f"📈 总体概况:\n"
                f"• 总关键词数: {total_keywords}\n"
                f"• 激活关键词: {active_keywords}\n"
                f"• 禁用关键词: {total_keywords - active_keywords}\n"
                f"• 分类数量: {len(categories)}\n\n"
            )
            
            if popular_keywords:
                message += "🏆 最受欢迎关键词:\n"
                for i, keyword in enumerate(popular_keywords, 1):
                    message += f"{i}. {keyword['name']} ({keyword['usage_count']}次)\n"
            
            if categories:
                message += "\n🏷️ 分类统计:\n"
                for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]:
                    message += f"• {category}: {count}个\n"
            
            await update.callback_query.edit_message_text(
                text=message,
                reply_markup=reply_markup,
                parse_mode=None
            )
            
            return True
            
        except Exception as e:
            logger.error(f"显示关键词统计失败: {e}")
            await update.callback_query.answer("❌ 获取统计数据失败", show_alert=True)
            return False
    
    async def handle_batch_operations(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """处理批量操作"""
        try:
            keyboard = [
                [
                    InlineKeyboardButton("✅ 批量启用", callback_data="admin_keyword_batch_enable"),
                    InlineKeyboardButton("❌ 批量禁用", callback_data="admin_keyword_batch_disable")
                ],
                [
                    InlineKeyboardButton("🏷️ 批量分类", callback_data="admin_keyword_batch_categorize"),
                    InlineKeyboardButton("📊 批量排序", callback_data="admin_keyword_batch_reorder")
                ],
                [
                    InlineKeyboardButton("🗑️ 批量删除", callback_data="admin_keyword_batch_delete"),
                    InlineKeyboardButton("🔄 批量重置", callback_data="admin_keyword_batch_reset")
                ],
                [InlineKeyboardButton("↩️ 返回主菜单", callback_data="admin_keyword_main")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = (
                "🔄 批量操作管理\n\n"
                "选择要执行的批量操作：\n\n"
                "• 批量启用 - 启用所有禁用的关键词\n"
                "• 批量禁用 - 禁用所有激活的关键词\n"
                "• 批量分类 - 为关键词批量设置分类\n"
                "• 批量排序 - 重新排列关键词显示顺序\n"
                "• 批量删除 - 删除未使用的关键词\n"
                "• 批量重置 - 重置关键词使用计数\n\n"
                "⚠️ 批量操作会影响多个关键词，请谨慎使用！"
            )
            
            await update.callback_query.edit_message_text(
                text=message,
                reply_markup=reply_markup,
                parse_mode=None
            )
            
            return True
            
        except Exception as e:
            logger.error(f"显示批量操作菜单失败: {e}")
            await update.callback_query.answer("❌ 加载批量操作失败", show_alert=True)
            return False
    
    async def cleanup(self):
        """清理资源"""
        # V2管理器无需清理，只清理用户状态
        self.user_states.clear()
        logger.info("关键词管理系统已清理")