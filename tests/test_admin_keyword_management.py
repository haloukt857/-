# -*- coding: utf-8 -*-
"""
管理员关键词管理功能测试 (V2.0)
验证admin_keyword_management.py与V2数据库管理器的完整集成

OPERATION ADMIN REFACTOR - KEYWORDS: 功能验证测试
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

# 测试框架导入
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dialogs.admin_keyword_management import AdminKeywordManagement
from database.db_keywords import KeywordManagerExtended

logger = logging.getLogger(__name__)

class TestAdminKeywordManagementV2:
    """管理员关键词管理V2集成测试"""
    
    async def test_initialization(self):
        """测试初始化"""
        admin_keyword_mgr = AdminKeywordManagement()
        await admin_keyword_mgr.initialize()
        
        # 验证使用的是V2管理器
        assert isinstance(admin_keyword_mgr.keyword_manager, KeywordManagerExtended)
        assert admin_keyword_mgr.user_states == {}
        
        print("✅ 初始化测试通过")
    
    async def test_main_menu_display(self):
        """测试主菜单显示"""
        admin_keyword_mgr = AdminKeywordManagement()
        
        # Mock update对象
        mock_update = MagicMock()
        mock_callback_query = MagicMock()
        mock_update.callback_query = mock_callback_query
        
        with patch.object(admin_keyword_mgr.keyword_manager, 'count_keywords') as mock_count:
            mock_count.side_effect = [10, 8]  # total_keywords, active_keywords
            
            result = await admin_keyword_mgr.show_main_menu(mock_update, None)
            
            assert result is True
            mock_count.assert_any_call()
            mock_count.assert_any_call(only_active=True)
            mock_callback_query.edit_message_text.assert_called_once()
            
            # 验证消息内容包含统计信息
            call_args = mock_callback_query.edit_message_text.call_args[1]
            assert "总关键词数: 10" in call_args['text']
            assert "激活关键词: 8" in call_args['text']
            assert "禁用关键词: 2" in call_args['text']
        
        print("✅ 主菜单显示测试通过")
    
    async def test_keyword_list_display(self):
        """测试关键词列表显示"""
        admin_keyword_mgr = AdminKeywordManagement()
        
        # Mock数据
        mock_keywords = [
            {'id': 1, 'name': '美食', 'is_active': True, 'usage_count': 5},
            {'id': 2, 'name': '购物', 'is_active': False, 'usage_count': 2},
            {'id': 3, 'name': '娱乐', 'is_active': True, 'usage_count': 0}
        ]
        
        mock_update = MagicMock()
        mock_callback_query = MagicMock()
        mock_update.callback_query = mock_callback_query
        
        with patch.object(admin_keyword_mgr.keyword_manager, 'get_all_keywords') as mock_get_all, \
             patch.object(admin_keyword_mgr.keyword_manager, 'count_keywords') as mock_count:
            
            mock_get_all.return_value = mock_keywords
            mock_count.return_value = 3
            
            result = await admin_keyword_mgr.handle_keyword_list(mock_update, None, page=1)
            
            assert result is True
            mock_get_all.assert_called_with(limit=8, offset=0)
            mock_count.assert_called_once()
            mock_callback_query.edit_message_text.assert_called_once()
            
            # 验证消息内容
            call_args = mock_callback_query.edit_message_text.call_args[1]
            assert "第 1/1 页" in call_args['text']
            assert "共 3 个关键词" in call_args['text']
        
        print("✅ 关键词列表显示测试通过")
    
    async def test_add_keyword_flow(self):
        """测试添加关键词流程"""
        admin_keyword_mgr = AdminKeywordManagement()
        
        # 测试开始添加流程
        mock_update = MagicMock()
        mock_callback_query = MagicMock()
        mock_update.callback_query = mock_callback_query
        mock_update.effective_user.id = 123
        
        result = await admin_keyword_mgr.handle_add_keyword(mock_update, None)
        
        assert result is True
        mock_callback_query.edit_message_text.assert_called_once()
        
        # 验证用户状态设置
        user_state = admin_keyword_mgr._get_user_state(123)
        assert user_state['action'] == 'adding_keyword'
        
        # 测试处理添加关键词
        mock_message = MagicMock()
        mock_message.from_user.id = 123
        mock_message.text = "新关键词"
        mock_message.reply_text = AsyncMock()
        
        with patch.object(admin_keyword_mgr.keyword_manager, 'get_keyword_by_name') as mock_get_by_name, \
             patch.object(admin_keyword_mgr.keyword_manager, 'create_keyword') as mock_create:
            
            mock_get_by_name.return_value = None  # 关键词不存在
            mock_create.return_value = 100  # 新创建的关键词ID
            
            result = await admin_keyword_mgr._process_add_keyword(mock_update, None, "新关键词")
            
            assert result is True
            mock_get_by_name.assert_called_with("新关键词")
            mock_create.assert_called_with(name="新关键词", description="", category="未分类")
        
        print("✅ 添加关键词流程测试通过")
    
    async def test_edit_keyword_flow(self):
        """测试编辑关键词流程"""
        admin_keyword_mgr = AdminKeywordManagement()
        
        mock_keyword = {
            'id': 1,
            'name': '美食',
            'description': '美食相关服务',
            'category': '生活服务',
            'is_active': True,
            'display_order': 1,
            'usage_count': 5,
            'created_at': '2023-01-01 10:00:00',
            'updated_at': '2023-01-01 10:00:00'
        }
        
        mock_update = MagicMock()
        mock_callback_query = MagicMock()
        mock_update.callback_query = mock_callback_query
        
        with patch.object(admin_keyword_mgr.keyword_manager, 'get_keyword_by_id') as mock_get_by_id:
            mock_get_by_id.return_value = mock_keyword
            
            result = await admin_keyword_mgr.handle_edit_keyword(mock_update, None, keyword_id=1)
            
            assert result is True
            mock_get_by_id.assert_called_with(1)
            mock_callback_query.edit_message_text.assert_called_once()
            
            # 验证消息内容包含关键词信息
            call_args = mock_callback_query.edit_message_text.call_args[1]
            assert "美食" in call_args['text']
            assert "✅ 激活" in call_args['text']
            assert "使用次数: 5" in call_args['text']
        
        print("✅ 编辑关键词流程测试通过")
    
    async def test_toggle_keyword_status(self):
        """测试切换关键词状态"""
        admin_keyword_mgr = AdminKeywordManagement()
        
        mock_keyword = {'id': 1, 'name': '美食', 'is_active': True}
        
        mock_update = MagicMock()
        mock_callback_query = MagicMock()
        mock_update.callback_query = mock_callback_query
        
        with patch.object(admin_keyword_mgr.keyword_manager, 'get_keyword_by_id') as mock_get_by_id, \
             patch.object(admin_keyword_mgr.keyword_manager, 'update_keyword_status') as mock_update_status, \
             patch.object(admin_keyword_mgr, 'handle_edit_keyword') as mock_handle_edit:
            
            mock_get_by_id.return_value = mock_keyword
            mock_update_status.return_value = True
            mock_handle_edit.return_value = True
            
            result = await admin_keyword_mgr.handle_toggle_keyword(mock_update, None, keyword_id=1)
            
            assert result is True
            mock_get_by_id.assert_called_with(1)
            mock_update_status.assert_called_with(1, False)  # 切换为False
            mock_callback_query.answer.assert_called_with("✅ 关键词已禁用")
            mock_handle_edit.assert_called_with(mock_update, None, 1)
        
        print("✅ 切换关键词状态测试通过")
    
    async def test_delete_keyword_flow(self):
        """测试删除关键词流程"""
        admin_keyword_mgr = AdminKeywordManagement()
        
        mock_keyword = {'id': 1, 'name': '测试关键词', 'usage_count': 0}
        
        mock_update = MagicMock()
        mock_callback_query = MagicMock()
        mock_update.callback_query = mock_callback_query
        
        # 测试删除确认
        with patch.object(admin_keyword_mgr.keyword_manager, 'get_keyword_by_id') as mock_get_by_id:
            mock_get_by_id.return_value = mock_keyword
            
            result = await admin_keyword_mgr.handle_delete_keyword_confirm(mock_update, None, keyword_id=1)
            
            assert result is True
            mock_get_by_id.assert_called_with(1)
            mock_callback_query.edit_message_text.assert_called_once()
            
            # 验证确认消息
            call_args = mock_callback_query.edit_message_text.call_args[1]
            assert "确认删除关键词" in call_args['text']
            assert "测试关键词" in call_args['text']
        
        # 测试执行删除
        with patch.object(admin_keyword_mgr.keyword_manager, 'get_keyword_by_id') as mock_get_by_id, \
             patch.object(admin_keyword_mgr.keyword_manager, 'delete_keyword') as mock_delete:
            
            mock_get_by_id.return_value = mock_keyword
            mock_delete.return_value = True
            
            result = await admin_keyword_mgr.handle_delete_keyword_confirmed(mock_update, None, keyword_id=1)
            
            assert result is True
            mock_delete.assert_called_with(1)
            mock_callback_query.answer.assert_called_with("✅ 关键词已删除")
        
        print("✅ 删除关键词流程测试通过")
    
    async def test_keyword_statistics_display(self):
        """测试关键词统计显示"""
        admin_keyword_mgr = AdminKeywordManagement()
        
        mock_popular_keywords = [
            {'name': '美食', 'usage_count': 10},
            {'name': '购物', 'usage_count': 8},
            {'name': '娱乐', 'usage_count': 5}
        ]
        
        mock_categories = {"生活服务": 5, "娱乐休闲": 3, "未分类": 2}
        
        mock_update = MagicMock()
        mock_callback_query = MagicMock()
        mock_update.callback_query = mock_callback_query
        
        with patch.object(admin_keyword_mgr.keyword_manager, 'count_keywords') as mock_count, \
             patch.object(admin_keyword_mgr.keyword_manager, 'get_popular_keywords') as mock_popular, \
             patch.object(admin_keyword_mgr.keyword_manager, 'get_keyword_categories') as mock_categories_call:
            
            mock_count.side_effect = [10, 8]  # total, active
            mock_popular.return_value = mock_popular_keywords
            mock_categories_call.return_value = mock_categories
            
            result = await admin_keyword_mgr.show_keyword_statistics(mock_update, None)
            
            assert result is True
            mock_count.assert_any_call()
            mock_count.assert_any_call(only_active=True)
            mock_popular.assert_called_with(limit=5)
            mock_categories_call.assert_called_once()
            
            # 验证统计信息显示
            call_args = mock_callback_query.edit_message_text.call_args[1]
            assert "总关键词数: 10" in call_args['text']
            assert "激活关键词: 8" in call_args['text']
            assert "最受欢迎关键词" in call_args['text']
            assert "美食 (10次)" in call_args['text']
        
        print("✅ 关键词统计显示测试通过")
    
    async def test_v2_manager_methods(self):
        """测试V2管理器扩展方法"""
        
        # 测试count_keywords方法
        with patch('database.db_keywords.db_manager') as mock_db:
            mock_db.fetch_one.return_value = {'total': 15}
            
            total_count = await KeywordManagerExtended.count_keywords()
            active_count = await KeywordManagerExtended.count_keywords(only_active=True)
            
            assert total_count == 15
            assert active_count == 15
            
            # 验证SQL查询
            calls = mock_db.fetch_one.call_args_list
            assert "SELECT COUNT(*) as total FROM keywords" in calls[0][0][0]
            assert "WHERE is_active = 1" in calls[1][0][0]
        
        # 测试update_keyword_status方法
        with patch('database.db_keywords.db_manager') as mock_db:
            mock_db.execute_query.return_value = 1
            
            result = await KeywordManagerExtended.update_keyword_status(1, True)
            
            assert result is True
            mock_db.execute_query.assert_called_once()
            
            # 验证SQL查询
            call_args = mock_db.execute_query.call_args[0]
            assert "UPDATE keywords SET is_active = ?" in call_args[0]
            assert call_args[1] == (True, 1)
        
        # 测试get_popular_keywords方法
        with patch('database.db_keywords.db_manager') as mock_db:
            mock_result = [
                {'id': 1, 'name': '美食', 'usage_count': 10},
                {'id': 2, 'name': '购物', 'usage_count': 5}
            ]
            mock_db.fetch_all.return_value = mock_result
            
            popular = await KeywordManagerExtended.get_popular_keywords(limit=2)
            
            assert len(popular) == 2
            assert popular[0]['name'] == '美食'
            assert popular[0]['usage_count'] == 10
            
            # 验证SQL查询
            call_args = mock_db.fetch_all.call_args[0]
            assert "ORDER BY mk_count.usage_count DESC" in call_args[0]
            assert call_args[1] == (2,)
        
        print("✅ V2管理器扩展方法测试通过")

def run_admin_keyword_management_tests():
    """运行管理员关键词管理测试"""
    print("\n🚀 开始管理员关键词管理V2集成测试...")
    
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    # 创建测试实例
    test_instance = TestAdminKeywordManagementV2()
    
    # 运行测试
    async def run_tests():
        try:
            await test_instance.test_initialization()
            await test_instance.test_main_menu_display()
            await test_instance.test_keyword_list_display()
            await test_instance.test_add_keyword_flow()
            await test_instance.test_edit_keyword_flow()
            await test_instance.test_toggle_keyword_status()
            await test_instance.test_delete_keyword_flow()
            await test_instance.test_keyword_statistics_display()
            await test_instance.test_v2_manager_methods()
            
            print("\n✅ 管理员关键词管理V2集成测试完成")
            print("📋 测试摘要：")
            print("   - 初始化: ✅")
            print("   - 主菜单显示: ✅") 
            print("   - 关键词列表: ✅")
            print("   - 添加关键词: ✅")
            print("   - 编辑关键词: ✅")
            print("   - 状态切换: ✅")
            print("   - 删除关键词: ✅")
            print("   - 统计显示: ✅")
            print("   - V2管理器扩展: ✅")
            print("\n🎯 结论: admin_keyword_management.py已100%适配V2架构")
            
        except Exception as e:
            print(f"❌ 测试执行失败: {e}")
            raise
    
    # 执行测试
    asyncio.run(run_tests())

if __name__ == "__main__":
    run_admin_keyword_management_tests()