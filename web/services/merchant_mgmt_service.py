# -*- coding: utf-8 -*-
"""
商户管理服务
从app.py.old中提取的商户管理业务逻辑
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

# 导入数据库管理器
from database.db_merchants import merchant_manager
from database.db_connection import db_manager
from database.db_fsm import create_fsm_db_manager
from utils.enums import MERCHANT_STATUS
from utils.user_detector import TelegramUserDetector
from config import BOT_TOKEN
import json

# 导入缓存服务
from .cache_service import CacheService

logger = logging.getLogger(__name__)


class MerchantMgmtService:
    """商户管理服务类"""
    
    CACHE_NAMESPACE = "merchant_mgmt"
    
    @staticmethod
    async def get_merchants_list(
        status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        获取商户列表
        
        Args:
            status: 商户状态筛选
            search: 搜索关键词
            page: 页码
            per_page: 每页数量
            
        Returns:
            dict: 商户列表数据
        """
        try:
            # 使用MerchantManager.get_merchants_list方法，它返回完整数据结构
            merchants_data = await merchant_manager.get_merchants_list(
                page=page,
                per_page=per_page,
                status=status,
                search=search
            )
            
            merchants = merchants_data.get('posts', [])  # get_merchants_list返回的是posts字段

            # 严格遵循“唯一真源”：不从FSM或其他缓存补齐任何字段，完全以数据库为准。
            total_count = merchants_data.get('total', 0)
            
            # 获取状态统计
            status_stats = await MerchantMgmtService._get_status_statistics()
            
            return {
                'merchants': merchants,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total_count,
                    'pages': (total_count + per_page - 1) // per_page
                },
                'filters': {
                    'status': status,
                    'search': search
                },
                'status_stats': status_stats,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"获取商户列表失败: {e}")
            return {
                'merchants': [],
                'pagination': {'page': page, 'per_page': per_page, 'total': 0, 'pages': 0},
                'filters': {'status': status, 'search': search},
                'status_stats': {
                    'total': 0,
                    'pending_approval': 0,
                    'approved': 0,
                    'published': 0,
                    'expired': 0
                },
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    async def get_merchant_detail(merchant_id: int) -> Dict[str, Any]:
        """
        获取商户详情
        
        Args:
            merchant_id: 商户ID
            
        Returns:
            dict: 商户详情数据
        """
        try:
            merchant = await merchant_manager.get_merchant_by_id(merchant_id)
            if not merchant:
                return {'success': False, 'error': '商户不存在'}
            
            # 获取商户的订单统计
            order_stats = await MerchantMgmtService._get_merchant_order_stats(merchant_id)
            
            # 获取商户的评价统计
            review_stats = await MerchantMgmtService._get_merchant_review_stats(merchant_id)
            
            return {
                'merchant': merchant,
                'order_stats': order_stats,
                'review_stats': review_stats,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"获取商户详情失败: merchant_id={merchant_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def update_merchant_status(merchant_id: int, status: str, publish_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        更新商户状态
        
        Args:
            merchant_id: 商户ID
            status: 新状态
            publish_time: 发布时间（可选）
            
        Returns:
            dict: 更新结果
        """
        try:
            # 验证状态有效性
            if status not in [s.value for s in MERCHANT_STATUS]:
                return {'success': False, 'error': '无效的状态值'}
            
            result = await merchant_manager.update_merchant_status(
                merchant_id=merchant_id,
                status=status,
                publish_time=publish_time
            )
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(MerchantMgmtService.CACHE_NAMESPACE)
                CacheService.clear_namespace("dashboard")
                
                logger.info(f"商户状态更新成功: merchant_id={merchant_id}, status={status}")
                return {'success': True, 'message': '状态更新成功'}
            else:
                return {'success': False, 'error': '状态更新失败'}
                
        except Exception as e:
            logger.error(f"更新商户状态失败: merchant_id={merchant_id}, status={status}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def update_merchant_info(merchant_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新商户信息
        
        Args:
            merchant_id: 商户ID
            data: 更新数据
            
        Returns:
            dict: 更新结果
        """
        try:
            result = await merchant_manager.update_merchant(merchant_id, data)
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(MerchantMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"商户信息更新成功: merchant_id={merchant_id}")
                return {'success': True, 'message': '信息更新成功'}
            else:
                return {'success': False, 'error': '信息更新失败'}
                
        except Exception as e:
            logger.error(f"更新商户信息失败: merchant_id={merchant_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def delete_merchant(merchant_id: int) -> Dict[str, Any]:
        """
        删除商户
        
        Args:
            merchant_id: 商户ID
            
        Returns:
            dict: 删除结果
        """
        try:
            result = await merchant_manager.delete_merchant(merchant_id)
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(MerchantMgmtService.CACHE_NAMESPACE)
                CacheService.clear_namespace("dashboard")
                
                logger.info(f"商户删除成功: merchant_id={merchant_id}")
                return {'success': True, 'message': '商户删除成功'}
            else:
                return {'success': False, 'error': '商户删除失败'}
                
        except Exception as e:
            logger.error(f"删除商户失败: merchant_id={merchant_id}, error={e}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def refresh_telegram_user_info(merchant_id: int) -> Dict[str, Any]:
        """以数据库为唯一真源，主动刷新并写入 Telegram 用户信息。

        - 读取商户 telegram_chat_id
        - 通过 Telegram API 获取用户资料
        - 持久化到 merchants.user_info（JSON）
        - 若 DB 中 contact_info 为空且检测到 username，则写入 '@username'
        """
        try:
            merchant = await merchant_manager.get_merchant_by_id(merchant_id)
            if not merchant:
                return {'success': False, 'error': '商户不存在'}

            chat_id = merchant.get('telegram_chat_id')
            if not chat_id:
                return {'success': False, 'error': '缺少telegram_chat_id'}

            detector = TelegramUserDetector(BOT_TOKEN)
            await detector.initialize()
            info = await detector.get_user_info(int(chat_id))
            await detector.cleanup()

            # 组织最小一致结构
            payload = {
                'user_id': info.get('user_id'),
                'username': info.get('username'),
                'full_name': info.get('full_name'),
                'bio': info.get('bio'),
                'language_code': info.get('language_code'),
                'detected_info': info.get('detected_info', {})
            }

            update_data = {
                'user_info': json.dumps(payload, ensure_ascii=False)
            }

            # 仅当DB中 contact_info 为空时才写入 '@username'
            username = info.get('username')
            if (not merchant.get('contact_info')) and username:
                update_data['contact_info'] = f"@{username}"

            # 名称统一：若商户名称为空/待完善，则用Telegram显示名回填
            full_name = info.get('full_name')
            # 始终以 Telegram 网名作为“名称”的权威来源（覆盖旧值）
            if full_name:
                update_data['name'] = full_name

            ok = await merchant_manager.update_merchant(merchant_id, update_data)
            if ok:
                # 清除相关缓存
                CacheService.clear_namespace(MerchantMgmtService.CACHE_NAMESPACE)
                return {'success': True, 'updated': list(update_data.keys()), 'username': username}
            return {'success': False, 'error': '数据库更新失败'}

        except Exception as e:
            logger.error(f"刷新用户信息失败: merchant_id={merchant_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def batch_update_status(merchant_ids: List[int], status: str) -> Dict[str, Any]:
        """
        批量更新商户状态
        
        Args:
            merchant_ids: 商户ID列表
            status: 新状态
            
        Returns:
            dict: 批量更新结果
        """
        try:
            if not merchant_ids:
                return {'success': False, 'error': '未选择商户'}
            
            if status not in [s.value for s in MERCHANT_STATUS]:
                return {'success': False, 'error': '无效的状态值'}
            
            success_count = 0
            failed_count = 0
            errors = []
            
            for merchant_id in merchant_ids:
                try:
                    result = await merchant_manager.update_merchant_status(merchant_id, status)
                    if result:
                        success_count += 1
                    else:
                        failed_count += 1
                        errors.append(f"商户 {merchant_id} 更新失败")
                except Exception as e:
                    failed_count += 1
                    errors.append(f"商户 {merchant_id} 更新异常: {str(e)}")
            
            # 清除相关缓存
            if success_count > 0:
                CacheService.clear_namespace(MerchantMgmtService.CACHE_NAMESPACE)
                CacheService.clear_namespace("dashboard")
            
            return {
                'success': success_count > 0,
                'success_count': success_count,
                'failed_count': failed_count,
                'errors': errors,
                'message': f'成功更新 {success_count} 个商户，失败 {failed_count} 个'
            }
            
        except Exception as e:
            logger.error(f"批量更新商户状态失败: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def _get_status_statistics() -> Dict[str, int]:
        """获取状态统计"""
        try:
            cache_key = "status_stats"
            cached_stats = CacheService.get(MerchantMgmtService.CACHE_NAMESPACE, cache_key)
            if cached_stats is not None:
                return cached_stats
            
            stats = await merchant_manager.get_merchant_statistics()
            by_status = stats.get('by_status', {}) if isinstance(stats, dict) else {}
            status_stats = {
                'total': stats.get('total_merchants', 0) if isinstance(stats, dict) else 0,
                'pending_submission': by_status.get('pending_submission', 0),
                'pending_approval': by_status.get('pending_approval', 0),
                'approved': by_status.get('approved', 0),
                'published': by_status.get('published', 0),
                'expired': by_status.get('expired', 0)
            }
            
            # 为保证与绑定流程的实时联动，将TTL缩短为5秒
            CacheService.set(MerchantMgmtService.CACHE_NAMESPACE, cache_key, status_stats, 5)
            return status_stats
            
        except Exception as e:
            logger.error(f"获取状态统计失败: {e}")
            return {}
    
    @staticmethod
    async def _get_merchant_order_stats(merchant_id: int) -> Dict[str, Any]:
        """获取商户订单统计"""
        try:
            # TODO: 实现商户订单统计逻辑
            return {
                'total_orders': 0,
                'completed_orders': 0,
                'pending_orders': 0,
                'completion_rate': 0.0
            }
        except Exception as e:
            logger.error(f"获取商户订单统计失败: merchant_id={merchant_id}, error={e}")
            return {}
    
    @staticmethod
    async def _get_merchant_review_stats(merchant_id: int) -> Dict[str, Any]:
        """获取商户评价统计"""
        try:
            # TODO: 实现商户评价统计逻辑
            return {
                'total_reviews': 0,
                'average_rating': 0.0,
                'rating_distribution': {}
            }
        except Exception as e:
            logger.error(f"获取商户评价统计失败: merchant_id={merchant_id}, error={e}")
            return {}
