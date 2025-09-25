"""
管理员地区管理对话流程
提供城市和地区的完整CRUD管理功能
完全基于当前数据模型: cities + districts
"""

import logging
from typing import Dict, List, Optional, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.db_regions import region_manager
from config import MESSAGE_TEMPLATES

logger = logging.getLogger(__name__)


class AdminRegionManagement:
    """管理员地区管理对话流程"""
    
    def __init__(self):
        # 临时状态存储
        self.user_states: Dict[int, Dict] = {}
    
    async def initialize(self):
        """初始化管理器"""
        logger.info("管理员地区管理系统初始化完成")
    
    def _get_user_state(self, user_id: int) -> Dict:
        """获取用户状态"""
        if user_id not in self.user_states:
            self.user_states[user_id] = {
                'action': None,
                'selected_city_id': None,
                'selected_district_id': None,
                'editing_data': {}
            }
        return self.user_states[user_id]
    
    def _clear_user_state(self, user_id: int):
        """清除用户状态"""
        if user_id in self.user_states:
            del self.user_states[user_id]
    
    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """显示地区管理主菜单"""
        try:
            keyboard = [
                [
                    InlineKeyboardButton("🏙️ 城市管理", callback_data="admin_region_cities"),
                    InlineKeyboardButton("🏛️ 地区管理", callback_data="admin_region_districts")
                ],
                [
                    InlineKeyboardButton("📊 统计信息", callback_data="admin_region_stats"),
                    InlineKeyboardButton("🔄 同步数据", callback_data="admin_region_sync")
                ],
                [InlineKeyboardButton("↩️ 返回管理菜单", callback_data="admin_main")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = (
                "🌍 地区管理系统\n\n"
                "选择要管理的内容：\n"
                "• 城市管理 - 添加、编辑、删除城市\n"
                "• 地区管理 - 管理地区信息\n"
                "• 统计信息 - 查看地区数据统计\n"
                "• 同步数据 - 手动同步地区数据"
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
            logger.error(f"显示地区管理主菜单失败: {e}")
            return False
    
    async def handle_city_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """处理城市管理"""
        try:
            cities_with_districts = await region_manager.get_all_cities_with_districts()
            
            keyboard = []
            # 添加现有城市的管理按钮
            for city in cities_with_districts:
                status_icon = "✅" if city['is_active'] else "❌"
                district_count = len(city.get('districts', []))
                keyboard.append([
                    InlineKeyboardButton(
                        f"{status_icon} {city['name']} ({district_count}个地区)",
                        callback_data=f"admin_city_edit_{city['id']}"
                    )
                ])
            
            # 操作按钮
            keyboard.extend([
                [InlineKeyboardButton("➕ 添加新城市", callback_data="admin_city_add")],
                [
                    InlineKeyboardButton("📊 城市统计", callback_data="admin_city_stats"),
                    InlineKeyboardButton("🔄 刷新列表", callback_data="admin_region_cities")
                ],
                [InlineKeyboardButton("↩️ 返回地区管理", callback_data="admin_region_main")]
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = (
                f"🏙️ 城市管理\n\n"
                f"当前共有 {len(cities_with_districts)} 个城市\n\n"
                "点击城市名称进行编辑，或选择其他操作：\n"
                "✅ = 激活状态  ❌ = 禁用状态\n"
                "数字表示该城市下的地区数量"
            )
            
            await update.callback_query.edit_message_text(
                text=message,
                reply_markup=reply_markup,
                parse_mode=None
            )
            
            return True
            
        except Exception as e:
            logger.error(f"处理城市管理失败: {e}")
            await update.callback_query.answer("❌ 加载城市列表失败", show_alert=True)
            return False
    
    async def handle_district_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """处理地区管理"""
        try:
            cities_with_districts = await region_manager.get_all_cities_with_districts()
            
            keyboard = []
            # 按城市显示地区管理入口
            for city in cities_with_districts:
                district_count = len(city.get('districts', []))
                keyboard.append([
                    InlineKeyboardButton(
                        f"🏛️ {city['name']} ({district_count}个地区)",
                        callback_data=f"admin_districts_by_city_{city['id']}"
                    )
                ])
            
            # 操作按钮
            keyboard.extend([
                [
                    InlineKeyboardButton("➕ 快速添加地区", callback_data="admin_district_quick_add"),
                    InlineKeyboardButton("📊 地区统计", callback_data="admin_district_stats")
                ],
                [InlineKeyboardButton("↩️ 返回地区管理", callback_data="admin_region_main")]
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = (
                "🏛️ 地区管理\n\n"
                "选择城市来管理其下属地区：\n"
                "数字表示该城市下的地区数量"
            )
            
            await update.callback_query.edit_message_text(
                text=message,
                reply_markup=reply_markup,
                parse_mode=None
            )
            
            return True
            
        except Exception as e:
            logger.error(f"处理地区管理失败: {e}")
            await update.callback_query.answer("❌ 加载地区管理失败", show_alert=True)
            return False
    
    async def handle_add_city(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """开始添加新城市流程"""
        try:
            user_id = update.effective_user.id
            state = self._get_user_state(user_id)
            state['action'] = 'adding_city'
            
            keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="admin_region_cities")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = (
                "➕ 添加新城市\n\n"
                "请输入城市名称：\n"
                "• 名称应该清晰明确\n"
                "• 不能与现有城市重复\n"
                "• 建议使用标准城市名称"
            )
            
            await update.callback_query.edit_message_text(
                text=message,
                reply_markup=reply_markup,
                parse_mode=None
            )
            
            return True
            
        except Exception as e:
            logger.error(f"开始添加城市流程失败: {e}")
            return False
    
    async def handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """处理文本输入"""
        try:
            user_id = update.effective_user.id
            state = self._get_user_state(user_id)
            text = update.message.text.strip()
            
            if state['action'] == 'adding_city':
                return await self._process_add_city(update, context, text)
            elif state['action'] == 'editing_city_name':
                return await self._process_edit_city_name(update, context, text)
            elif state['action'] == 'adding_district':
                return await self._process_add_district(update, context, text)
            elif state['action'] == 'editing_district_name':
                return await self._process_edit_district_name(update, context, text)
            
            return False
            
        except Exception as e:
            logger.error(f"处理文本输入失败: {e}")
            return False
    
    async def _process_add_city(self, update: Update, context: ContextTypes.DEFAULT_TYPE, name: str) -> bool:
        """处理添加城市"""
        try:
            user_id = update.effective_user.id
            
            # 检查名称是否已存在 - 通过获取所有城市来检查重名
            all_cities = await region_manager.get_all_cities_with_districts()
            for city in all_cities:
                if city['name'].lower() == name.lower():
                    await update.message.reply_text(
                        f"❌ 城市 '{name}' 已经存在！\n请输入不同的名称：",
                        parse_mode=None
                    )
                    return True
            
            # 添加城市
            city_id = await region_manager.add_city(name)
            if city_id:
                self._clear_user_state(user_id)
                
                keyboard = [
                    [InlineKeyboardButton("➕ 继续添加", callback_data="admin_city_add")],
                    [InlineKeyboardButton("🏛️ 添加地区", callback_data=f"admin_districts_by_city_{city_id}")],
                    [InlineKeyboardButton("↩️ 返回城市管理", callback_data="admin_region_cities")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"✅ 添加成功！\n\n"
                    f"城市 '{name}' 已成功添加\n"
                    f"ID: {city_id}",
                    reply_markup=reply_markup,
                    parse_mode=None
                )
                return True
            else:
                await update.message.reply_text("❌ 添加城市失败，请重试")
                return False
                
        except Exception as e:
            logger.error(f"添加城市失败: {e}")
            await update.message.reply_text("❌ 添加城市时发生错误")
            return False
    
    async def handle_edit_city(self, update: Update, context: ContextTypes.DEFAULT_TYPE, city_id: int) -> bool:
        """处理编辑城市"""
        try:
            city = await region_manager.get_city_by_id(city_id)
            if not city:
                await update.callback_query.answer("❌ 城市不存在", show_alert=True)
                return False
            
            districts = await region_manager.get_districts_by_city(city_id)
            
            keyboard = [
                [InlineKeyboardButton("✏️ 编辑名称", callback_data=f"admin_city_edit_name_{city_id}")],
                [
                    InlineKeyboardButton(
                        "🔄 切换状态" if city['is_active'] else "✅ 启用城市",
                        callback_data=f"admin_city_toggle_{city_id}"
                    ),
                    InlineKeyboardButton("📊 调整排序", callback_data=f"admin_city_order_{city_id}")
                ],
                [InlineKeyboardButton("🏛️ 管理地区", callback_data=f"admin_districts_by_city_{city_id}")],
            ]
            
            # 只有在没有地区时才允许删除
            if len(districts) == 0:
                keyboard.append([InlineKeyboardButton("🗑️ 删除城市", callback_data=f"admin_city_delete_{city_id}")])
            
            keyboard.append([InlineKeyboardButton("↩️ 返回城市管理", callback_data="admin_region_cities")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            status = "✅ 激活" if city['is_active'] else "❌ 禁用"
            message = (
                f"✏️ 编辑城市: {city['name']}\n\n"
                f"ID: {city['id']}\n"
                f"状态: {status}\n"
                f"排序: {city['display_order']}\n"
                f"地区数量: {len(districts)}\n"
                f"创建时间: {city['created_at'][:19]}"
            )
            
            if len(districts) > 0:
                message += f"\n\n⚠️ 该城市下有 {len(districts)} 个地区，无法删除"
            
            await update.callback_query.edit_message_text(
                text=message,
                reply_markup=reply_markup,
                parse_mode=None
            )
            
            return True
            
        except Exception as e:
            logger.error(f"编辑城市失败: {e}")
            await update.callback_query.answer("❌ 加载城市信息失败", show_alert=True)
            return False
    
    async def handle_toggle_city(self, update: Update, context: ContextTypes.DEFAULT_TYPE, city_id: int) -> bool:
        """切换城市状态"""
        try:
            city = await region_manager.get_city_by_id(city_id)
            if not city:
                await update.callback_query.answer("❌ 城市不存在", show_alert=True)
                return False
            
            # 使用toggle方法切换状态
            success = await region_manager.toggle_city_status(city_id)
            
            if success:
                status_text = "激活" if not city['is_active'] else "禁用"
                await update.callback_query.answer(f"✅ 城市已{status_text}")
                # 刷新编辑界面
                return await self.handle_edit_city(update, context, city_id)
            else:
                await update.callback_query.answer("❌ 更新失败", show_alert=True)
                return False
                
        except Exception as e:
            logger.error(f"切换城市状态失败: {e}")
            await update.callback_query.answer("❌ 操作失败", show_alert=True)
            return False
    
    async def handle_districts_by_city(self, update: Update, context: ContextTypes.DEFAULT_TYPE, city_id: int) -> bool:
        """显示指定城市下的地区管理"""
        try:
            city = await region_manager.get_city_by_id(city_id)
            if not city:
                await update.callback_query.answer("❌ 城市不存在", show_alert=True)
                return False
            
            districts = await region_manager.get_districts_by_city(city_id)
            
            keyboard = []
            # 添加现有地区的管理按钮
            for district in districts:
                status_icon = "✅" if district['is_active'] else "❌"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{status_icon} {district['name']}",
                        callback_data=f"admin_district_edit_{district['id']}"
                    )
                ])
            
            # 操作按钮
            keyboard.extend([
                [InlineKeyboardButton("➕ 添加地区", callback_data=f"admin_district_add_{city_id}")],
                [
                    InlineKeyboardButton("🔄 刷新列表", callback_data=f"admin_districts_by_city_{city_id}"),
                    InlineKeyboardButton("📊 统计信息", callback_data=f"admin_district_stats_{city_id}")
                ],
                [InlineKeyboardButton("↩️ 返回地区管理", callback_data="admin_region_districts")]
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = (
                f"🏛️ {city['name']} - 地区管理\n\n"
                f"当前共有 {len(districts)} 个地区\n\n"
                "点击地区名称进行编辑：\n"
                "✅ = 激活状态  ❌ = 禁用状态"
            )
            
            await update.callback_query.edit_message_text(
                text=message,
                reply_markup=reply_markup,
                parse_mode=None
            )
            
            return True
            
        except Exception as e:
            logger.error(f"显示城市地区失败: {e}")
            await update.callback_query.answer("❌ 加载地区列表失败", show_alert=True)
            return False
    
    async def handle_add_district(self, update: Update, context: ContextTypes.DEFAULT_TYPE, city_id: int) -> bool:
        """开始添加地区流程"""
        try:
            user_id = update.effective_user.id
            state = self._get_user_state(user_id)
            state['action'] = 'adding_district'
            state['selected_city_id'] = city_id
            
            city = await region_manager.get_city_by_id(city_id)
            
            keyboard = [[InlineKeyboardButton("❌ 取消", callback_data=f"admin_districts_by_city_{city_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = (
                f"➕ 添加地区到 {city['name']}\n\n"
                "请输入地区名称：\n"
                "• 名称应该清晰明确\n"
                "• 不能与该城市现有地区重复\n"
                "• 建议使用标准地区名称"
            )
            
            await update.callback_query.edit_message_text(
                text=message,
                reply_markup=reply_markup,
                parse_mode=None
            )
            
            return True
            
        except Exception as e:
            logger.error(f"开始添加地区流程失败: {e}")
            return False
    
    async def _process_add_district(self, update: Update, context: ContextTypes.DEFAULT_TYPE, name: str) -> bool:
        """处理添加地区"""
        try:
            user_id = update.effective_user.id
            state = self._get_user_state(user_id)
            city_id = state['selected_city_id']
            
            # 检查名称在该城市内是否已存在 - 通过获取该城市的地区列表检查重名
            existing_districts = await region_manager.get_districts_by_city(city_id)
            for district in existing_districts:
                if district['name'].lower() == name.lower():
                    await update.message.reply_text(
                        f"❌ 该城市内已存在地区 '{name}'！\n请输入不同的名称：",
                        parse_mode=None
                    )
                    return True
            
            # 添加地区
            district_id = await region_manager.add_district(city_id, name)
            if district_id:
                self._clear_user_state(user_id)
                
                keyboard = [
                    [InlineKeyboardButton("➕ 继续添加", callback_data=f"admin_district_add_{city_id}")],
                    [InlineKeyboardButton("✏️ 编辑地区", callback_data=f"admin_district_edit_{district_id}")],
                    [InlineKeyboardButton("↩️ 返回地区列表", callback_data=f"admin_districts_by_city_{city_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"✅ 添加成功！\n\n"
                    f"地区 '{name}' 已成功添加\n"
                    f"ID: {district_id}",
                    reply_markup=reply_markup,
                    parse_mode=None
                )
                return True
            else:
                await update.message.reply_text("❌ 添加地区失败，请重试")
                return False
                
        except Exception as e:
            logger.error(f"添加地区失败: {e}")
            await update.message.reply_text("❌ 添加地区时发生错误")
            return False
    
    async def handle_delete_city(self, update: Update, context: ContextTypes.DEFAULT_TYPE, city_id: int) -> bool:
        """处理删除城市"""
        try:
            city = await region_manager.get_city_by_id(city_id)
            if not city:
                await update.callback_query.answer("❌ 城市不存在", show_alert=True)
                return False
            
            # 检查是否有地区
            districts = await region_manager.get_districts_by_city(city_id)
            if len(districts) > 0:
                await update.callback_query.answer(f"❌ 城市下还有 {len(districts)} 个地区，无法删除", show_alert=True)
                return False
            
            # 删除城市
            success = await region_manager.delete_city(city_id)
            if success:
                await update.callback_query.answer(f"✅ 城市 '{city['name']}' 已删除")
                # 返回城市列表
                return await self.handle_city_management(update, context)
            else:
                await update.callback_query.answer("❌ 删除失败", show_alert=True)
                return False
                
        except Exception as e:
            logger.error(f"删除城市失败: {e}")
            await update.callback_query.answer("❌ 操作失败", show_alert=True)
            return False
    
    async def handle_delete_district(self, update: Update, context: ContextTypes.DEFAULT_TYPE, district_id: int) -> bool:
        """处理删除地区"""
        try:
            district = await region_manager.get_district_by_id(district_id)
            if not district:
                await update.callback_query.answer("❌ 地区不存在", show_alert=True)
                return False
            
            city_id = district['city_id']
            
            # 删除地区
            success = await region_manager.delete_district(district_id)
            if success:
                await update.callback_query.answer(f"✅ 地区 '{district['name']}' 已删除")
                # 返回地区列表
                return await self.handle_districts_by_city(update, context, city_id)
            else:
                await update.callback_query.answer("❌ 删除失败", show_alert=True)
                return False
                
        except Exception as e:
            logger.error(f"删除地区失败: {e}")
            await update.callback_query.answer("❌ 操作失败", show_alert=True)
            return False
    
    async def show_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """显示地区统计信息"""
        try:
            # 获取统计数据
            cities_with_districts = await region_manager.get_all_cities_with_districts()
            active_cities = [c for c in cities_with_districts if c['is_active']]
            
            total_districts = 0
            active_districts = 0
            
            for city in cities_with_districts:
                districts = city.get('districts', [])
                total_districts += len(districts)
                active_districts += len([d for d in districts if d['is_active']])
            
            keyboard = [
                [InlineKeyboardButton("🏙️ 城市详情", callback_data="admin_city_stats")],
                [InlineKeyboardButton("🏛️ 地区详情", callback_data="admin_district_stats")],
                [InlineKeyboardButton("↩️ 返回地区管理", callback_data="admin_region_main")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = (
                f"📊 地区统计信息\n\n"
                f"🏙️ 城市统计\n"
                f"• 总计: {len(cities_with_districts)} 个\n"
                f"• 激活: {len(active_cities)} 个\n"
                f"• 禁用: {len(cities_with_districts) - len(active_cities)} 个\n\n"
                f"🏛️ 地区统计\n"
                f"• 总计: {total_districts} 个\n"
                f"• 激活: {active_districts} 个\n"
                f"• 禁用: {total_districts - active_districts} 个\n\n"
                f"📈 平均数据\n"
                f"• 平均每城市地区数: {total_districts / len(cities_with_districts) if cities_with_districts else 0:.1f}"
            )
            
            await update.callback_query.edit_message_text(
                text=message,
                reply_markup=reply_markup,
                parse_mode=None
            )
            
            return True
            
        except Exception as e:
            logger.error(f"显示统计信息失败: {e}")
            await update.callback_query.answer("❌ 获取统计信息失败", show_alert=True)
            return False
    
    async def cleanup(self):
        """清理资源"""
        self.user_states.clear()
        logger.info("地区管理系统已清理")