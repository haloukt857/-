# -*- coding: utf-8 -*-
"""
商家/帖子数据库管理器 - 修正版
与实际数据库结构保持一致，支持现有的字段名和结构。
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Union

# 导入项目模块

from database.db_connection import db_manager

logger = logging.getLogger(__name__)


class MerchantManager:
    """
    商户管理器类，与实际数据库结构保持一致。
    支持现有的telegram_chat_id字段和V1扩展字段。
    """

    @staticmethod
    async def create_merchant(merchant_data: Dict[str, Any]) -> Optional[int]:
        """
        创建新商户（使用实际数据库字段）
        
        Args:
            merchant_data: 商户信息字典，支持实际数据库字段：
                - telegram_chat_id: TG聊天ID (必需)
                - name: 商户名称 (可选，默认为"待完善")
                - merchant_type: 商户类型 (teacher/business，默认teacher)
                - city_id: 城市ID (可选)
                - district_id: 区县ID (可选)
                - p_price: 价格1 (可选)
                - pp_price: 价格2 (可选)
                - custom_description: 自定义描述 (可选)
                - contact_info: 联系信息 (可选)
                - profile_data: JSON格式详细资料 (可选)
                - status: 状态 (默认为'pending_submission')
        
        Returns:
            新创建商户的永久ID，失败时返回None
        """
        try:
            # 验证必需字段
            if not merchant_data.get('telegram_chat_id'):
                logger.error("创建商户失败：缺少必需字段 telegram_chat_id")
                return None
            
            # 检查商户是否已存在（根据telegram_chat_id）
            existing = await MerchantManager.get_merchant_by_chat_id(merchant_data['telegram_chat_id'])
            if existing:
                logger.warning(f"商户已存在，telegram_chat_id: {merchant_data['telegram_chat_id']}")
                return existing['id']
            
            # 准备插入数据（使用实际数据库字段）
            query = """
                INSERT INTO merchants (
                    telegram_chat_id, name, merchant_type, city_id, district_id,
                    p_price, pp_price, custom_description, adv_sentence, contact_info,
                    profile_data, status, user_info, channel_link
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            # 处理profile_data
            profile_data = merchant_data.get('profile_data', {})
            if isinstance(profile_data, dict):
                profile_json = json.dumps(profile_data, ensure_ascii=False)
            else:
                profile_json = profile_data
            
            params = (
                merchant_data['telegram_chat_id'],
                merchant_data.get('name', '待完善'),
                merchant_data.get('merchant_type', 'teacher'),
                merchant_data.get('city_id'),
                merchant_data.get('district_id'),
                merchant_data.get('p_price'),
                merchant_data.get('pp_price'),
                merchant_data.get('custom_description'),
                merchant_data.get('adv_sentence'),
                merchant_data.get('contact_info'),
                profile_json,
                merchant_data.get('status', 'pending_submission'),
                merchant_data.get('user_info'),
                merchant_data.get('channel_link')
            )
            
            merchant_id = await db_manager.get_last_insert_id(query, params)
            
            logger.info(f"商户创建成功，永久ID: {merchant_id}, telegram_chat_id: {merchant_data['telegram_chat_id']}")
            
            # 记录活动日志
            await MerchantManager._log_merchant_activity(
                merchant_id, 'merchant_created', 
                {
                    'telegram_chat_id': merchant_data['telegram_chat_id'],
                    'name': merchant_data.get('name', '待完善')
                }
            )
            
            return merchant_id
            
        except Exception as e:
            logger.error(f"创建商户失败: {e}")
            return None

    @staticmethod
    async def create_blank_merchant(telegram_chat_id: int, binding_code: str = None) -> Optional[int]:
        """
        创建空白商户档案（用于绑定码系统快速注册）
        
        Args:
            telegram_chat_id: Telegram用户ID
            binding_code: 绑定码（记录在活动日志中）
            
        Returns:
            int: 新创建的商户永久ID，失败时返回None
        """
        try:
            merchant_data = {
                'telegram_chat_id': telegram_chat_id,
                'name': '待完善',
                'status': 'pending_submission',
                'custom_description': '待完善',
                'contact_info': '待完善',
                'profile_data': {
                    'binding_code': binding_code,
                    'registration_mode': 'binding_code'
                }
            }
            
            merchant_id = await MerchantManager.create_merchant(merchant_data)
            
            if merchant_id:
                logger.info(f"空白商户档案创建成功，telegram_chat_id: {telegram_chat_id}, 永久ID: {merchant_id}")
                
                # 记录绑定码关联日志
                await MerchantManager._log_merchant_activity(
                    merchant_id, 'blank_merchant_created', 
                    {
                        'telegram_chat_id': telegram_chat_id,
                        'binding_code': binding_code,
                        'registration_mode': 'binding_code'
                    }
                )
            
            return merchant_id
            
        except Exception as e:
            logger.error(f"创建空白商户失败: {e}")
            return None

    @staticmethod
    async def get_merchant(merchant_id: int) -> Optional[Dict[str, Any]]:
        """
        根据永久ID获取商户信息
        
        Args:
            merchant_id: 商户永久ID
            
        Returns:
            商户信息字典（包含地区信息），不存在时返回None
        """
        try:
            query = """
                SELECT m.id, m.telegram_chat_id, m.name, m.contact_info,
                       m.profile_data, m.status, m.created_at, m.updated_at,
                       m.merchant_type, m.city_id, m.district_id, m.p_price, m.pp_price,
                       m.custom_description, m.adv_sentence, m.user_info, m.channel_link, m.channel_chat_id, m.show_in_region_search,
                       m.publish_time, m.expiration_time, m.post_url,
                       c.name as city_name, d.name as district_name
                FROM merchants m
                LEFT JOIN cities c ON m.city_id = c.id
                LEFT JOIN districts d ON m.district_id = d.id
                WHERE m.id = ?
            """
            
            result = await db_manager.fetch_one(query, (merchant_id,))
            
            if result:
                merchant = dict(result)
                
                # 解析JSON字段
                if merchant['profile_data']:
                    try:
                        merchant['profile_data'] = json.loads(merchant['profile_data'])
                    except json.JSONDecodeError:
                        merchant['profile_data'] = {}
                
                # 生成完整地区信息
                if merchant.get('city_name') and merchant.get('district_name'):
                    merchant['region_display'] = f"{merchant['city_name']} - {merchant['district_name']}"
                elif merchant.get('city_name'):
                    merchant['region_display'] = merchant['city_name']
                else:
                    merchant['region_display'] = '未设置'
                
                logger.debug(f"获取商户成功，永久ID: {merchant_id}")
                return merchant
            else:
                logger.debug(f"商户不存在，永久ID: {merchant_id}")
                return None
                
        except Exception as e:
            logger.error(f"获取商户失败: {e}")
            return None

    @staticmethod
    async def get_merchant_by_id(merchant_id: int) -> Optional[Dict[str, Any]]:
        """兼容方法：根据永久ID获取商户信息（等价于 get_merchant）"""
        return await MerchantManager.get_merchant(merchant_id)

    @staticmethod
    async def set_post_url(merchant_id: int, url: str) -> bool:
        """保存最近一次发布的频道贴文链接。

        Args:
            merchant_id: 商户ID
            url: 帖子完整URL（https://t.me/.../<message_id>）

        Returns:
            bool: 是否更新成功
        """
        try:
            sql = "UPDATE merchants SET post_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            rc = await db_manager.execute_query(sql, (url, merchant_id))
            return bool(rc and rc >= 0)
        except Exception as e:
            logger.error(f"更新商户帖子链接失败: merchant_id={merchant_id}, error={e}")
            return False

    @staticmethod
    async def get_merchant_by_chat_id(telegram_chat_id: int) -> Optional[Dict[str, Any]]:
        """
        根据Telegram聊天ID获取商户信息
        
        Args:
            telegram_chat_id: Telegram聊天ID
            
        Returns:
            商户信息字典，不存在时返回None
        """
        try:
            query = """
                SELECT m.id, m.telegram_chat_id, m.name, m.contact_info,
                       m.profile_data, m.status, m.created_at, m.updated_at,
                       m.merchant_type, m.city_id, m.district_id, m.p_price, m.pp_price,
                       m.custom_description, m.adv_sentence, m.user_info, m.channel_link, m.channel_chat_id, m.show_in_region_search,
                       m.publish_time, m.expiration_time, m.post_url,
                       c.name as city_name, d.name as district_name
                FROM merchants m
                LEFT JOIN cities c ON m.city_id = c.id
                LEFT JOIN districts d ON m.district_id = d.id
                WHERE m.telegram_chat_id = ?
            """
            
            result = await db_manager.fetch_one(query, (telegram_chat_id,))
            
            if result:
                merchant = dict(result)
                
                # 解析JSON字段
                if merchant['profile_data']:
                    try:
                        merchant['profile_data'] = json.loads(merchant['profile_data'])
                    except json.JSONDecodeError:
                        merchant['profile_data'] = {}
                
                # 生成完整地区信息
                if merchant.get('city_name') and merchant.get('district_name'):
                    merchant['region_display'] = f"{merchant['city_name']} - {merchant['district_name']}"
                elif merchant.get('city_name'):
                    merchant['region_display'] = merchant['city_name']
                else:
                    merchant['region_display'] = '未设置'
                
                logger.debug(f"根据telegram_chat_id获取商户成功: {telegram_chat_id}")
                return merchant
            else:
                logger.debug(f"商户不存在，telegram_chat_id: {telegram_chat_id}")
                return None
                
        except Exception as e:
            logger.error(f"根据telegram_chat_id获取商户失败: {e}")
            return None

    @staticmethod
    async def get_merchants(status: Optional[str] = None, search: Optional[str] = None, region_id: Optional[int] = None, limit: int = 30, offset: int = 0) -> List[Dict[str, Any]]:
        """
        获取商户列表（使用实际数据库字段）
        
        Args:
            status: 状态过滤
            search: 搜索关键词 (名称或ID)
            region_id: 地区ID过滤（使用实际字段名）
            limit: 限制返回数量
            offset: 偏移量
            
        Returns:
            商户信息列表（包含地区信息）
        """
        try:
            base_query = """
                SELECT m.id, m.telegram_chat_id, m.name, m.contact_info,
                       m.profile_data, m.status, m.created_at, m.updated_at,
                       m.merchant_type, m.city_id, m.district_id, m.p_price, m.pp_price,
                       m.custom_description, m.user_info, m.channel_link, m.channel_chat_id, m.show_in_region_search,
                       c.name as city_name, d.name as district_name
                FROM merchants m
                LEFT JOIN cities c ON m.city_id = c.id
                LEFT JOIN districts d ON m.district_id = d.id
            """
            conditions = []
            params = []

            if status:
                conditions.append("m.status = ?")
                params.append(status)
            
            if search:
                # 支持名称模糊搜索和ID精确搜索
                conditions.append("(m.name LIKE ? OR CAST(m.id AS TEXT) = ?)")
                params.extend([f"%{search}%", search])

            if region_id:
                conditions.append("m.district_id = ?")
                params.append(region_id)

            if conditions:
                base_query += " WHERE " + " AND ".join(conditions)
            
            # 分页：仅当提供有效的limit时才追加LIMIT/OFFSET，防止SQLite类型不匹配
            if isinstance(limit, int):
                base_query += " ORDER BY m.created_at DESC LIMIT ? OFFSET ?"
                params.extend([int(limit), int(offset or 0)])
            else:
                base_query += " ORDER BY m.created_at DESC"

            results = await db_manager.fetch_all(base_query, tuple(params))
            
            merchants = []
            for row in results:
                merchant = dict(row)
                # 解析JSON字段
                if merchant['profile_data']:
                    try:
                        merchant['profile_data'] = json.loads(merchant['profile_data'])
                    except json.JSONDecodeError:
                        merchant['profile_data'] = {}
                        
                # 生成完整地区信息
                if merchant.get('city_name') and merchant.get('district_name'):
                    merchant['region_display'] = f"{merchant['city_name']} - {merchant['district_name']}"
                elif merchant.get('city_name'):
                    merchant['region_display'] = merchant['city_name']
                else:
                    merchant['region_display'] = '未设置'
                merchants.append(merchant)
            
            logger.debug(f"获取商户列表成功，数量: {len(merchants)}")
            return merchants
            
        except Exception as e:
            logger.error(f"获取商户列表失败: {e}")
            return []

    # ====== 唯一定义：深链查询接口 ======
    @staticmethod
    async def list_active_by_district(district_id: int, limit: int = 30, offset: int = 0) -> List[Dict[str, Any]]:
        try:
            query = """
                SELECT m.id, m.name, m.p_price, m.pp_price,
                       m.publish_time, m.expiration_time, m.created_at, m.updated_at,
                       d.name AS district_name, c.name AS city_name
                FROM merchants m
                LEFT JOIN districts d ON m.district_id = d.id
                LEFT JOIN cities c ON m.city_id = c.id
                WHERE m.district_id = ?
                  AND m.status IN ('approved','published')
                  AND (m.expiration_time IS NULL OR m.expiration_time > datetime('now'))
                ORDER BY COALESCE(m.publish_time, m.created_at) ASC
                LIMIT ? OFFSET ?
            """
            rows = await db_manager.fetch_all(query, (int(district_id), int(limit), int(offset)))
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"按区县获取活跃商户失败: {e}")
            return []

    @staticmethod
    async def list_active_by_price(price_field: str, price_value: int, limit: int = 30, offset: int = 0) -> List[Dict[str, Any]]:
        try:
            if price_field not in ('p_price','pp_price'):
                raise ValueError('invalid price_field')
            query = f"""
                SELECT m.id, m.name, m.p_price, m.pp_price,
                       m.publish_time, m.expiration_time, m.created_at, m.updated_at,
                       d.name AS district_name, c.name AS city_name
                FROM merchants m
                LEFT JOIN districts d ON m.district_id = d.id
                LEFT JOIN cities c ON m.city_id = c.id
                WHERE m.{price_field} = ?
                  AND m.status IN ('approved','published')
                  AND (m.expiration_time IS NULL OR m.expiration_time > datetime('now'))
                ORDER BY COALESCE(m.publish_time, m.created_at) ASC
                LIMIT ? OFFSET ?
            """
            rows = await db_manager.fetch_all(query, (int(price_value), int(limit), int(offset)))
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"按价格获取活跃商户失败: {e}")
            return []

    @staticmethod
    async def list_active_by_keyword(keyword_id: int, limit: int = 30, offset: int = 0) -> List[Dict[str, Any]]:
        try:
            query = """
                SELECT m.id, m.name, m.p_price, m.pp_price,
                       m.publish_time, m.expiration_time, m.created_at, m.updated_at,
                       d.name AS district_name, c.name AS city_name
                FROM merchants m
                JOIN merchant_keywords mk ON mk.merchant_id = m.id
                LEFT JOIN districts d ON m.district_id = d.id
                LEFT JOIN cities c ON m.city_id = c.id
                WHERE mk.keyword_id = ?
                  AND m.status IN ('approved','published')
                  AND (m.expiration_time IS NULL OR m.expiration_time > datetime('now'))
                ORDER BY COALESCE(m.publish_time, m.created_at) ASC
                LIMIT ? OFFSET ?
            """
            rows = await db_manager.fetch_all(query, (int(keyword_id), int(limit), int(offset)))
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"按关键词获取活跃商户失败: {e}")
            return []

    @staticmethod
    async def get_all_merchants(
        status_filter: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取所有商户列表（V1兼容方法）
        """
        return await MerchantManager.get_merchants(status=status_filter, limit=limit, offset=offset)

    @staticmethod
    async def get_merchant_details(merchant_id: int) -> Optional[Dict[str, Any]]:
        """
        获取单个商户的详细信息，用于Web后台编辑页面。
        """
        return await MerchantManager.get_merchant(merchant_id)

    @staticmethod
    async def update_merchant(merchant_id: int, update_data: Dict[str, Any]) -> bool:
        """
        更新商户信息（使用实际数据库字段）
        
        Args:
            merchant_id: 商户永久ID
            update_data: 要更新的字段字典
            
        Returns:
            更新是否成功
        """
        try:
            # 验证商户是否存在
            existing = await MerchantManager.get_merchant(merchant_id)
            if not existing:
                logger.error(f"商户不存在，无法更新，永久ID: {merchant_id}")
                return False
            
            # 构建更新查询
            update_fields = []
            params = []
            
            # 实际数据库允许的字段列表
            allowed_fields = [
                'telegram_chat_id', 'name', 'contact_info', 'profile_data', 'status',
                'merchant_type', 'city_id', 'district_id', 'p_price', 'pp_price',
                'custom_description', 'adv_sentence', 'user_info', 'channel_link', 'channel_chat_id', 'show_in_region_search',
                'publish_time', 'expiration_time'
            ]
            
            for field, value in update_data.items():
                if field in allowed_fields:
                    update_fields.append(f"{field} = ?")
                    if field == 'profile_data' and isinstance(value, dict):
                        params.append(json.dumps(value, ensure_ascii=False))
                    else:
                        params.append(value)
            
            if not update_fields:
                logger.warning("没有有效的更新字段")
                return False
            
            # 添加updated_at字段
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(merchant_id)
            
            query = f"UPDATE merchants SET {', '.join(update_fields)} WHERE id = ?"
            
            result = await db_manager.execute_query(query, tuple(params))
            
            if result > 0:
                logger.info(f"商户更新成功，永久ID: {merchant_id}")
                
                # 记录活动日志
                await MerchantManager._log_merchant_activity(
                    merchant_id, 'merchant_updated', update_data
                )
                
                return True
            else:
                logger.warning(f"商户更新失败，可能不存在，永久ID: {merchant_id}")
                return False
                
        except Exception as e:
            logger.error(f"更新商户失败: {e}")
            return False

    @staticmethod
    async def update_merchant_status(merchant_id: int, status: str, publish_time: Any = None, expiration_time: Any = None) -> bool:
        """
        更新商户状态
        
        Args:
            merchant_id: 商户永久ID
            status: 新状态 (pending_submission, pending_approval, approved, published, expired)
            
        Returns:
            更新是否成功
        """
        try:
            # 验证状态值（使用实际数据库的状态值）
            valid_statuses = ['pending_submission', 'pending_approval', 'approved', 'published', 'expired']
            if status not in valid_statuses:
                logger.error(f"无效的状态值: {status}")
                return False
            
            # 可选同步发布时间与到期时间
            fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
            params = [status]
            if publish_time is not None:
                fields.insert(1, "publish_time = ?")
                params.insert(1, publish_time)
            if expiration_time is not None:
                fields.insert(1, "expiration_time = ?")
                params.insert(1, expiration_time)
            params.append(merchant_id)
            query = f"UPDATE merchants SET {', '.join(fields)} WHERE id = ?"
            result = await db_manager.execute_query(query, tuple(params))
            
            if result > 0:
                logger.info(f"商户状态更新成功，永久ID: {merchant_id}, 新状态: {status}")
                
                # 记录活动日志
                await MerchantManager._log_merchant_activity(
                    merchant_id, 'status_changed', {'new_status': status}
                )
                
                return True
            else:
                logger.warning(f"商户状态更新失败，可能不存在，永久ID: {merchant_id}")
                return False
                
        except Exception as e:
            logger.error(f"更新商户状态失败: {e}")
            return False

    @staticmethod
    async def delete_merchant(merchant_id: int) -> bool:
        """
        删除商户（级联删除相关数据）
        
        Args:
            merchant_id: 商户永久ID
            
        Returns:
            删除是否成功
        """
        try:
            # 获取商户信息用于日志记录
            merchant = await MerchantManager.get_merchant(merchant_id)
            if not merchant:
                logger.warning(f"商户不存在，无法删除，永久ID: {merchant_id}")
                return False
            
            # 删除商户（级联删除相关数据）
            query = "DELETE FROM merchants WHERE id = ?"
            result = await db_manager.execute_query(query, (merchant_id,))
            
            if result > 0:
                logger.info(f"商户删除成功，永久ID: {merchant_id}, 名称: {merchant['name']}")
                
                # 记录活动日志
                await MerchantManager._log_merchant_activity(
                    merchant_id, 'merchant_deleted', 
                    {
                        'name': merchant['name'],
                        'telegram_chat_id': merchant['telegram_chat_id']
                    }
                )
                
                return True
            else:
                logger.warning(f"商户删除失败，永久ID: {merchant_id}")
                return False
                
        except Exception as e:
            logger.error(f"删除商户失败: {e}")
            return False

    # ===== 发布时间槽占用查询（供上榜流程使用） =====
    @staticmethod
    async def get_occupied_time_slots_for_date(
        date_str: str,
        statuses: Optional[List[str]] = None,
        exclude_merchant_id: Optional[int] = None,
    ) -> List[str]:
        """获取某天已被占用的时间槽（HH:MM）。

        Args:
            date_str: 日期字符串，格式 YYYY-MM-DD
            statuses: 计入占用的商户状态集合，默认 ['pending_approval','approved','published']
            exclude_merchant_id: 排除的商户ID（编辑本人资料时避免自占）

        Returns:
            已被占用的时间字符串列表（HH:MM）
        """
        try:
            if not statuses:
                statuses = ['pending_approval', 'approved', 'published']

            placeholders = ','.join(['?'] * len(statuses))
            params: List[Any] = [date_str]
            params.extend(statuses)

            where_exclude = ''
            if exclude_merchant_id is not None:
                where_exclude = ' AND id <> ?'
                params.append(exclude_merchant_id)

            query = f"""
                SELECT DISTINCT strftime('%H:%M', publish_time) as slot
                FROM merchants
                WHERE date(publish_time) = ?
                  AND publish_time IS NOT NULL
                  AND status IN ({placeholders})
                  {where_exclude}
            """
            rows = await db_manager.fetch_all(query, tuple(params))
            return [r['slot'] for r in rows if r['slot']]
        except Exception as e:
            logger.error(f"查询已占用时间槽失败: {e}")
            return []

    @staticmethod
    async def is_time_slot_available(
        date_str: str,
        time_str: str,
        exclude_merchant_id: Optional[int] = None,
    ) -> bool:
        """检查指定日期的某个时间槽是否可用。"""
        try:
            occupied = await MerchantManager.get_occupied_time_slots_for_date(
                date_str, exclude_merchant_id=exclude_merchant_id
            )
            return time_str not in set(occupied)
        except Exception as e:
            logger.error(f"检查时间槽可用性失败: {e}")
            return False

    @staticmethod
    async def count_merchants() -> int:
        """统计商户总数"""
        try:
            row = await db_manager.fetch_one("SELECT COUNT(*) as cnt FROM merchants")
            if isinstance(row, dict):
                return int(row.get('cnt', 0))
            return int(row[0] if row else 0)
        except Exception as e:
            logger.error(f"统计商户总数失败: {e}")
            return 0

    @staticmethod
    async def get_merchants_count_by_region() -> Dict[str, int]:
        """按“城市-区县”统计商户数量（仅使用 city_id/district_id）"""
        try:
            query = """
                SELECT COALESCE(c.name, '未设置') AS city_name,
                       COALESCE(d.name, '') AS district_name,
                       COUNT(*) as cnt
                FROM merchants m
                LEFT JOIN cities c ON m.city_id = c.id
                LEFT JOIN districts d ON m.district_id = d.id
                GROUP BY c.id, d.id
            """
            rows = await db_manager.fetch_all(query)
            result: Dict[str, int] = {}
            for r in rows:
                city = r['city_name'] if isinstance(r, dict) else r[0]
                district = r['district_name'] if isinstance(r, dict) else r[1]
                key = f"{city} - {district}" if district else city
                result[key] = r['cnt'] if isinstance(r, dict) else r[2]
            return result
        except Exception as e:
            logger.error(f"按地区统计商户数量失败: {e}")
            return {}

    @staticmethod
    async def search_merchants(
        search_term: str,
        search_fields: List[str] = None,
        status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索商户
        
        Args:
            search_term: 搜索关键词
            search_fields: 搜索字段列表，默认为['name', 'custom_description']
            status_filter: 状态过滤器
            
        Returns:
            匹配的商户列表
        """
        try:
            if not search_fields:
                search_fields = ['name', 'custom_description', 'contact_info']
            
            # 构建搜索条件
            search_conditions = []
            params = []
            
            for field in search_fields:
                if field in ['name', 'custom_description', 'contact_info']:
                    search_conditions.append(f"m.{field} LIKE ?")
                    params.append(f"%{search_term}%")
            
            query = f"""
                SELECT m.id, m.telegram_chat_id, m.name, m.contact_info,
                       m.profile_data, m.status, m.created_at, m.updated_at,
                       m.merchant_type, m.city_id, m.district_id, m.p_price, m.pp_price,
                       m.custom_description, m.user_info, m.channel_link, m.show_in_region_search,
                       c.name as city_name, d.name as district_name
                FROM merchants m
                LEFT JOIN cities c ON m.city_id = c.id
                LEFT JOIN districts d ON m.district_id = d.id
                WHERE ({' OR '.join(search_conditions)})
            """
            
            # 添加状态过滤
            if status_filter:
                query += " AND m.status = ?"
                params.append(status_filter)
            
            query += " ORDER BY m.name"
            
            results = await db_manager.fetch_all(query, tuple(params))
            
            merchants = []
            for row in results:
                merchant = dict(row)
                # 解析JSON字段
                if merchant['profile_data']:
                    try:
                        merchant['profile_data'] = json.loads(merchant['profile_data'])
                    except json.JSONDecodeError:
                        merchant['profile_data'] = {}
                        
                # 生成地区信息
                if merchant.get('city_name') and merchant.get('district_name'):
                    merchant['region_display'] = f"{merchant['city_name']} - {merchant['district_name']}"
                elif merchant.get('city_name'):
                    merchant['region_display'] = merchant['city_name']
                else:
                    merchant['region_display'] = '未设置'
                merchants.append(merchant)
            
            logger.debug(f"搜索商户成功，关键词: {search_term}, 结果数量: {len(merchants)}")
            return merchants
            
        except Exception as e:
            logger.error(f"搜索商户失败: {e}")
            return []

    @staticmethod
    async def get_merchants_list(
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None,
        district_id: Optional[int] = None,
        search: Optional[str] = None,
        sort_by: str = 'created_at'
    ) -> Dict[str, Any]:
        """
        获取帖子（商户）分页列表，用于 Web 后台“帖子管理”。

        返回结构:
            {
              'posts': [ {id, name, status, city_name, district_name, publish_time, expiration_time, created_at, updated_at}... ],
              'total': <int>, 'page': <int>, 'per_page': <int>
            }
        """
        try:
            # 校验与规范化分页参数
            page = max(1, int(page or 1))
            per_page = max(1, min(100, int(per_page or 20)))
            offset = (page - 1) * per_page

            # 允许的排序字段白名单
            allowed_sort = {
                'created_at': 'm.created_at',
                'updated_at': 'm.updated_at',
                'publish_time': 'm.publish_time',
                'expiration_time': 'm.expiration_time',
            }
            order_by = allowed_sort.get(sort_by, 'm.created_at')

            # 基础查询（连接省/区以提供 city_name/district_name 字段给前端）
            base_from = (
                " FROM merchants m "
                " LEFT JOIN cities c ON m.city_id = c.id "
                " LEFT JOIN districts d ON m.district_id = d.id "
            )

            # 组装过滤条件
            conditions = []
            params: list[Any] = []

            if status:
                conditions.append("m.status = ?")
                params.append(status)

            if district_id:
                conditions.append("m.district_id = ?")
                params.append(int(district_id))

            if search:
                # 扩展搜索范围：名称/ID/联系方式/城市/区县/频道链接/频道用户名
                # 说明：
                # - 城市/区县来自LEFT JOIN的别名 c/d
                # - channel_chat_id 可能为数字，统一转为文本比较
                # - 统一使用 LIKE 模糊匹配，ID 仍保留精确等值匹配
                conditions.append(
                    "( m.name LIKE ?"
                    "  OR CAST(m.id AS TEXT) = ?"
                    "  OR COALESCE(m.contact_info, '') LIKE ?"
                    "  OR COALESCE(c.name, '') LIKE ?"
                    "  OR COALESCE(d.name, '') LIKE ?"
                    "  OR COALESCE(m.channel_link, '') LIKE ?"
                    "  OR CAST(COALESCE(m.channel_chat_id, '') AS TEXT) LIKE ? )"
                )
                search_like = f"%{search}%"
                params.extend([search_like, search, search_like, search_like, search_like, search_like, search_like])

            where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

            # 统计总数
            count_sql = "SELECT COUNT(*) as cnt" + base_from + where_clause
            total_row = await db_manager.fetch_one(count_sql, tuple(params))
            total = int(total_row['cnt'] if total_row and 'cnt' in total_row.keys() else (total_row[0] if total_row else 0))

            # 分页查询
            # 列表页需要展示联系方式、频道用户名/链接等字段，这里一并返回
            select_sql = (
                "SELECT m.id, m.name, m.status, "
                " COALESCE(c.name, '') as city_name, COALESCE(d.name, '') as district_name, "
                " m.publish_time, m.expiration_time, m.created_at, m.updated_at, "
                " m.contact_info, m.channel_chat_id, m.channel_link, m.user_info "
                + base_from + where_clause + f" ORDER BY {order_by} DESC LIMIT ? OFFSET ?"
            )
            rows = await db_manager.fetch_all(select_sql, tuple(params + [per_page, offset]))

            posts = [dict(row) for row in rows]
            return {
                'posts': posts,
                'total': total,
                'page': page,
                'per_page': per_page,
            }
        except Exception as e:
            logger.error(f"获取帖子列表失败: {e}")
            return {'posts': [], 'total': 0, 'page': page, 'per_page': per_page}

    @staticmethod
    async def get_merchant_statistics() -> Dict[str, Any]:
        """
        获取商户统计信息
        
        Returns:
            统计信息字典
        """
        try:
            stats = {}
            
            # 总商户数
            result = await db_manager.fetch_one("SELECT COUNT(*) FROM merchants")
            stats['total_merchants'] = result[0] if result else 0
            
            # 按状态统计
            status_query = """
                SELECT status, COUNT(*) as count 
                FROM merchants 
                GROUP BY status
            """
            status_results = await db_manager.fetch_all(status_query)
            stats['by_status'] = {row['status']: row['count'] for row in status_results}
            
            # 按商户类型统计
            type_query = """
                SELECT merchant_type, COUNT(*) as count 
                FROM merchants 
                WHERE merchant_type IS NOT NULL
                GROUP BY merchant_type
            """
            type_results = await db_manager.fetch_all(type_query)
            stats['by_type'] = {row['merchant_type']: row['count'] for row in type_results}
            
            # 按区县统计
            district_query = """
                SELECT d.name as district_name, COUNT(*) as count 
                FROM merchants m
                INNER JOIN districts d ON m.district_id = d.id
                GROUP BY d.id, d.name 
                ORDER BY count DESC 
                LIMIT 10
            """
            district_results = await db_manager.fetch_all(district_query)
            stats['by_district'] = {row['district_name']: row['count'] for row in district_results}
            
            # 按城市统计
            city_query = """
                SELECT c.name as city_name, COUNT(*) as count 
                FROM merchants m
                INNER JOIN cities c ON m.city_id = c.id
                GROUP BY c.id, c.name 
                ORDER BY count DESC 
                LIMIT 10
            """
            city_results = await db_manager.fetch_all(city_query)
            stats['by_city'] = {row['city_name']: row['count'] for row in city_results}
            
            # 最近注册统计（近7天）
            recent_query = """
                SELECT COUNT(*) 
                FROM merchants 
                WHERE created_at >= datetime('now', '-7 days')
            """
            recent_result = await db_manager.fetch_one(recent_query)
            stats['recent_registrations'] = recent_result[0] if recent_result else 0
            
            logger.debug(f"商户统计信息获取成功")
            return stats
            
        except Exception as e:
            logger.error(f"获取商户统计信息失败: {e}")
            return {}

    @staticmethod
    async def get_dashboard_stats() -> Dict[str, int]:
        """
        获取Web后台仪表板所需的核心统计数据
        """
        try:
            queries = {
                "pending_submission": "SELECT COUNT(*) as count FROM merchants WHERE status = 'pending_submission'",
                "pending_approval": "SELECT COUNT(*) as count FROM merchants WHERE status = 'pending_approval'",
                "approved": "SELECT COUNT(*) as count FROM merchants WHERE status = 'approved'",
                "published": "SELECT COUNT(*) as count FROM merchants WHERE status = 'published'",
                "expired": "SELECT COUNT(*) as count FROM merchants WHERE status = 'expired'",
                "total_merchants": "SELECT COUNT(*) as count FROM merchants"
            }
            
            # 订单统计（如果orders表存在）
            orders_queries = {
                "total_orders": "SELECT COUNT(*) as count FROM orders",
                "today_orders": "SELECT COUNT(*) as count FROM orders WHERE date(created_at) = date('now')"
            }
            
            stats = {}
            
            # 商户状态统计
            for key, query in queries.items():
                try:
                    result = await db_manager.fetch_one(query)
                    stats[key] = result['count'] if result else 0
                except Exception as e:
                    logger.warning(f"查询{key}失败: {e}")
                    stats[key] = 0
            
            # 订单统计（安全处理）
            for key, query in orders_queries.items():
                try:
                    result = await db_manager.fetch_one(query)
                    stats[key] = result['count'] if result else 0
                except Exception:
                    # 如果orders表不存在或查询失败，则返回0
                    stats[key] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"获取仪表板统计失败: {e}")
            return {}

    @staticmethod
    async def get_merchant_performance_analytics(
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        merchant_filter: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        商户绩效分析 - 数据库层聚合计算
        
        Args:
            start_date: 开始时间
            end_date: 结束时间
            merchant_filter: 指定商户ID过滤
            
        Returns:
            商户绩效分析数据，包含排行榜、地区分析、类别分析等
        """
        try:
            # 构建时间过滤条件
            time_filter = ""
            params = []
            
            if start_date and end_date:
                time_filter = "AND m.created_at BETWEEN ? AND ?"
                params.extend([start_date.isoformat(), end_date.isoformat()])
            
            merchant_filter_sql = ""
            if merchant_filter:
                merchant_filter_sql = "AND m.id = ?"
                params.append(merchant_filter)
            
            # 商户基础绩效数据（使用SQL聚合）
            performance_query = f"""
                SELECT 
                    m.id,
                    m.name,
                    m.merchant_type,
                    m.status,
                    COALESCE(d.name, '未知') as district_name,
                    COALESCE(c.name, '未知') as city_name,
                    COALESCE(order_stats.total_orders, 0) as total_orders,
                    COALESCE(order_stats.completed_orders, 0) as completed_orders,
                    COALESCE(order_stats.total_revenue, 0) as total_revenue,
                    COALESCE(activity_stats.total_interactions, 0) as total_interactions,
                    CASE 
                        WHEN COALESCE(activity_stats.total_interactions, 0) > 0 
                        THEN (COALESCE(order_stats.total_orders, 0) * 100.0) / activity_stats.total_interactions
                        ELSE 0 
                    END as conversion_rate,
                    m.created_at
                FROM merchants m
                LEFT JOIN districts d ON m.district_id = d.id
                LEFT JOIN cities c ON m.city_id = c.id
                LEFT JOIN (
                    SELECT 
                        merchant_id,
                        COUNT(*) as total_orders,
                        SUM(CASE WHEN status = '已完成' THEN 1 ELSE 0 END) as completed_orders,
                        SUM(CASE WHEN status = '已完成' AND price IS NOT NULL THEN CAST(price as REAL) ELSE 0 END) as total_revenue
                    FROM orders o
                    WHERE 1=1 {time_filter.replace('m.created_at', 'o.created_at') if time_filter else ''}
                    GROUP BY merchant_id
                ) order_stats ON m.id = order_stats.merchant_id
                LEFT JOIN (
                    SELECT 
                        merchant_id,
                        COUNT(*) as total_interactions
                    FROM activity_logs al
                    WHERE merchant_id IS NOT NULL {time_filter.replace('m.created_at', 'al.timestamp') if time_filter else ''}
                    GROUP BY merchant_id
                ) activity_stats ON m.id = activity_stats.merchant_id
                WHERE 1=1 {merchant_filter_sql}
                ORDER BY total_orders DESC, total_interactions DESC
                LIMIT 100
            """
            
            merchants_data = await db_manager.fetch_all(performance_query, build_query_params())
            
            # 区县聚合分析（SQL层面聚合）
            district_analysis_query = f"""
                SELECT 
                    COALESCE(d.name, '未知') as district_name,
                    COUNT(DISTINCT m.id) as merchant_count,
                    SUM(COALESCE(order_stats.total_orders, 0)) as total_orders,
                    SUM(COALESCE(order_stats.total_revenue, 0)) as total_revenue,
                    AVG(COALESCE(activity_stats.total_interactions, 0)) as avg_interactions
                FROM merchants m
                LEFT JOIN districts d ON m.district_id = d.id
                LEFT JOIN (
                    SELECT merchant_id, COUNT(*) as total_orders, 
                           SUM(CASE WHEN status = '已完成' AND price IS NOT NULL THEN CAST(price as REAL) ELSE 0 END) as total_revenue
                    FROM orders o WHERE 1=1 {time_filter.replace('m.created_at', 'o.created_at') if time_filter else ''}
                    GROUP BY merchant_id
                ) order_stats ON m.id = order_stats.merchant_id
                LEFT JOIN (
                    SELECT merchant_id, COUNT(*) as total_interactions
                    FROM activity_logs al WHERE merchant_id IS NOT NULL {time_filter.replace('m.created_at', 'al.timestamp') if time_filter else ''}
                    GROUP BY merchant_id
                ) activity_stats ON m.id = activity_stats.merchant_id
                WHERE 1=1 {merchant_filter_sql}
                GROUP BY d.name
                HAVING merchant_count > 0
                ORDER BY total_orders DESC
                LIMIT 20
            """
            district_data = await db_manager.fetch_all(district_analysis_query, build_query_params())
            
            # 商户类型分析（SQL层面聚合）
            category_analysis_query = f"""
                SELECT 
                    m.merchant_type,
                    COUNT(DISTINCT m.id) as merchant_count,
                    SUM(COALESCE(order_stats.total_orders, 0)) as total_orders,
                    SUM(COALESCE(order_stats.total_revenue, 0)) as total_revenue,
                    AVG(COALESCE(activity_stats.total_interactions, 0)) as avg_interactions
                FROM merchants m
                LEFT JOIN (
                    SELECT merchant_id, COUNT(*) as total_orders,
                           SUM(CASE WHEN status = '已完成' AND price IS NOT NULL THEN CAST(price as REAL) ELSE 0 END) as total_revenue
                    FROM orders o WHERE 1=1 {time_filter.replace('m.created_at', 'o.created_at') if time_filter else ''}
                    GROUP BY merchant_id
                ) order_stats ON m.id = order_stats.merchant_id
                LEFT JOIN (
                    SELECT merchant_id, COUNT(*) as total_interactions
                    FROM activity_logs al WHERE merchant_id IS NOT NULL {time_filter.replace('m.created_at', 'al.timestamp') if time_filter else ''}
                    GROUP BY merchant_id
                ) activity_stats ON m.id = activity_stats.merchant_id
                WHERE m.merchant_type IS NOT NULL {merchant_filter_sql}
                GROUP BY m.merchant_type
                HAVING merchant_count > 0
                ORDER BY total_orders DESC
            """
            
            category_data = await db_manager.fetch_all(category_analysis_query, build_query_params())
            
            # 基础汇总指标（SQL层面聚合）
            summary_query = f"""
                SELECT 
                    COUNT(DISTINCT m.id) as total_merchants,
                    COUNT(DISTINCT CASE WHEN m.status IN ('approved', 'published') THEN m.id END) as active_merchants,
                    SUM(COALESCE(order_stats.total_orders, 0)) as total_orders,
                    SUM(COALESCE(order_stats.total_revenue, 0)) as total_revenue,
                    AVG(COALESCE(activity_stats.total_interactions, 0)) as avg_interactions_per_merchant
                FROM merchants m
                LEFT JOIN (
                    SELECT merchant_id, COUNT(*) as total_orders,
                           SUM(CASE WHEN status = '已完成' AND price IS NOT NULL THEN CAST(price as REAL) ELSE 0 END) as total_revenue
                    FROM orders o WHERE 1=1 {time_filter.replace('m.created_at', 'o.created_at') if time_filter else ''}
                    GROUP BY merchant_id
                ) order_stats ON m.id = order_stats.merchant_id
                LEFT JOIN (
                    SELECT merchant_id, COUNT(*) as total_interactions
                    FROM activity_logs al WHERE merchant_id IS NOT NULL {time_filter.replace('m.created_at', 'al.timestamp') if time_filter else ''}
                    GROUP BY merchant_id
                ) activity_stats ON m.id = activity_stats.merchant_id
                WHERE 1=1 {merchant_filter_sql}
            """
            
            summary_result = await db_manager.fetch_one(summary_query, build_query_params())
            
            # 构建返回数据
            analytics_data = {
                'basic_metrics': dict(summary_result) if summary_result else {},
                'merchant_rankings': [dict(row) for row in merchants_data],
                'district_analysis': {row['district_name']: dict(row) for row in district_data},
                'category_analysis': {row['merchant_type']: dict(row) for row in category_data},
                'performance_tiers': await MerchantManager._calculate_performance_tiers([dict(row) for row in merchants_data])
            }
            
            logger.info("商户绩效分析完成")
            return analytics_data
            
        except Exception as e:
            logger.error(f"商户绩效分析失败: {e}")
            return {}
    
    @staticmethod
    async def get_merchant_registration_trends(days: int = 30) -> Dict[str, Any]:
        """
        商户注册趋势分析 - 数据库层聚合计算
        
        Args:
            days: 分析天数
            
        Returns:
            注册趋势数据
        """
        try:
            # 每日注册趋势（SQL聚合）
            daily_trends_query = """
                SELECT 
                    DATE(created_at) as registration_date,
                    COUNT(*) as registrations,
                    COUNT(CASE WHEN status IN ('approved', 'published') THEN 1 END) as approved_count,
                    COUNT(CASE WHEN merchant_type = 'teacher' THEN 1 END) as teacher_count,
                    COUNT(CASE WHEN merchant_type = 'business' THEN 1 END) as business_count
                FROM merchants 
                WHERE created_at >= datetime('now', '-' || ? || ' days')
                GROUP BY DATE(created_at)
                ORDER BY registration_date DESC
            """
            
            daily_data = await db_manager.fetch_all(daily_trends_query, (days,))
            
            # 注册渠道分析（如果有来源数据）
            source_analysis_query = """
                SELECT 
                    COALESCE(JSON_EXTRACT(profile_data, '$.registration_source'), '直接注册') as source,
                    COUNT(*) as count
                FROM merchants
                WHERE created_at >= datetime('now', '-' || ? || ' days')
                GROUP BY source
                ORDER BY count DESC
            """
            
            source_data = await db_manager.fetch_all(source_analysis_query, (days,))
            
            # 计算趋势指标
            if len(daily_data) >= 2:
                recent_avg = sum(row['registrations'] for row in daily_data[:7]) / min(7, len(daily_data))
                earlier_avg = sum(row['registrations'] for row in daily_data[-7:]) / min(7, len(daily_data[-7:]))
                growth_rate = ((recent_avg - earlier_avg) / max(earlier_avg, 1)) * 100 if earlier_avg > 0 else 0
            else:
                growth_rate = 0
            
            return {
                'daily_trends': [dict(row) for row in daily_data],
                'registration_sources': {row['source']: row['count'] for row in source_data},
                'growth_rate': growth_rate,
                'total_registrations': sum(row['registrations'] for row in daily_data),
                'average_daily': sum(row['registrations'] for row in daily_data) / max(len(daily_data), 1)
            }
            
        except Exception as e:
            logger.error(f"商户注册趋势分析失败: {e}")
            return {}
    
    @staticmethod
    async def _calculate_performance_tiers(merchants_data: List[Dict]) -> Dict[str, Any]:
        """
        计算商户表现分层（数据已从数据库聚合获取）
        """
        try:
            if not merchants_data:
                return {}
            
            # 基于订单数分层
            sorted_merchants = sorted(merchants_data, key=lambda x: x.get('total_orders', 0), reverse=True)
            total_count = len(sorted_merchants)
            
            # 分层标准
            high_threshold = max(1, total_count // 5)  # 前20%
            medium_threshold = max(1, total_count // 2)  # 前50%
            
            high_performers = sorted_merchants[:high_threshold]
            medium_performers = sorted_merchants[high_threshold:medium_threshold]
            low_performers = sorted_merchants[medium_threshold:]
            
            return {
                'high_performers': {
                    'count': len(high_performers),
                    'percentage': (len(high_performers) / total_count) * 100,
                    'avg_orders': sum(m.get('total_orders', 0) for m in high_performers) / max(len(high_performers), 1),
                    'avg_revenue': sum(m.get('total_revenue', 0) for m in high_performers) / max(len(high_performers), 1)
                },
                'medium_performers': {
                    'count': len(medium_performers),
                    'percentage': (len(medium_performers) / total_count) * 100,
                    'avg_orders': sum(m.get('total_orders', 0) for m in medium_performers) / max(len(medium_performers), 1),
                    'avg_revenue': sum(m.get('total_revenue', 0) for m in medium_performers) / max(len(medium_performers), 1)
                },
                'low_performers': {
                    'count': len(low_performers),
                    'percentage': (len(low_performers) / total_count) * 100,
                    'avg_orders': sum(m.get('total_orders', 0) for m in low_performers) / max(len(low_performers), 1),
                    'avg_revenue': sum(m.get('total_revenue', 0) for m in low_performers) / max(len(low_performers), 1)
                }
            }
            
        except Exception as e:
            logger.error(f"计算商户表现分层失败: {e}")
            return {}

    @staticmethod
    async def approve_merchant_post(merchant_id: int) -> bool:
        """
        批准商户帖子发布（Web后台使用）
        
        Args:
            merchant_id: 商户永久ID
            
        Returns:
            批准是否成功
        """
        try:
            # 获取当前商户信息
            merchant = await MerchantManager.get_merchant(merchant_id)
            if not merchant:
                logger.error(f"商户不存在，无法批准，永久ID: {merchant_id}")
                return False
            
            # 检查当前状态是否允许批准
            if merchant['status'] != 'pending_approval':
                logger.warning(f"商户状态不是 pending_approval，无法批准，当前状态: {merchant['status']}")
                return False
            
            # 更新状态为 approved
            success = await MerchantManager.update_merchant_status(merchant_id, 'approved')
            
            if success:
                logger.info(f"商户帖子批准成功，永久ID: {merchant_id}")
                
                # 记录批准活动
                await MerchantManager._log_merchant_activity(
                    merchant_id, 'post_approved', 
                    {
                        'approved_by': 'web_admin',
                        'previous_status': 'pending_approval',
                        'new_status': 'approved'
                    }
                )
                
                return True
            else:
                logger.error(f"商户帖子批准失败，永久ID: {merchant_id}")
                return False
                
        except Exception as e:
            logger.error(f"批准商户帖子失败: {e}")
            return False

    @staticmethod
    async def toggle_merchant_region_search_status(merchant_id: int) -> bool:
        """
        切换商家地区搜索的显示状态 (0/1)
        """
        try:
            query = """
                UPDATE merchants
                SET
                    show_in_region_search = 1 - show_in_region_search,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """
            result = await db_manager.execute_query(query, (merchant_id,))

            if result > 0:
                logger.info(f"商家 {merchant_id} 的地区搜索显示状态切换成功。")
                return True
            else:
                logger.warning(f"尝试切换地区搜索状态失败，商家ID {merchant_id} 可能不存在。")
                return False
        except Exception as e:
            logger.error(f"切换商家 {merchant_id} 的地区搜索状态时发生异常: {e}")
            return False

    @staticmethod
    async def get_merchant_performance_analytics(
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        merchant_filter: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        商户绩效分析 - 数据库层聚合计算
        
        Args:
            start_date: 开始时间
            end_date: 结束时间  
            merchant_filter: 指定商户ID过滤
            
        Returns:
            商户绩效分析数据，包含排行榜、地区分析、类别分析等
        """
        try:
            # 构建时间过滤条件和参数（为多个查询准备足够的参数）
            time_filter = ""
            base_params = []
            
            if start_date and end_date:
                time_filter = "AND m.created_at BETWEEN ? AND ?"
                base_params.extend([start_date.isoformat(), end_date.isoformat()])
            
            merchant_filter_sql = ""
            merchant_param = []
            if merchant_filter:
                merchant_filter_sql = "AND m.id = ?"
                merchant_param = [merchant_filter]
            
            # 为每个查询构建完整的参数列表（time_filter在多个子查询中重复使用）
            def build_query_params():
                query_params = []
                # 主查询中的时间参数（3次使用：主查询 + orders子查询 + activity子查询）
                if base_params:
                    query_params.extend(base_params)  # orders子查询时间参数
                    query_params.extend(base_params)  # activity_logs子查询时间参数
                # 商户过滤参数
                if merchant_param:
                    query_params.extend(merchant_param)
                return query_params
            
            # 商户基础绩效数据（使用SQL聚合）
            performance_query = f"""
                SELECT 
                    m.id,
                    m.name,
                    m.merchant_type,
                    m.status,
                    COALESCE(d.name, '未知') as district_name,
                    COALESCE(c.name, '未知') as city_name,
                    COALESCE(order_stats.total_orders, 0) as total_orders,
                    COALESCE(order_stats.completed_orders, 0) as completed_orders,
                    COALESCE(order_stats.total_revenue, 0) as total_revenue,
                    COALESCE(activity_stats.total_interactions, 0) as total_interactions,
                    CASE 
                        WHEN COALESCE(activity_stats.total_interactions, 0) > 0 
                        THEN (COALESCE(order_stats.total_orders, 0) * 100.0) / activity_stats.total_interactions
                        ELSE 0 
                    END as conversion_rate,
                    m.created_at
                FROM merchants m
                LEFT JOIN districts d ON m.district_id = d.id
                LEFT JOIN cities c ON m.city_id = c.id
                LEFT JOIN (
                    SELECT 
                        merchant_id,
                        COUNT(*) as total_orders,
                        SUM(CASE WHEN status = '已完成' THEN 1 ELSE 0 END) as completed_orders,
                        SUM(CASE WHEN status = '已完成' AND price IS NOT NULL THEN CAST(price as REAL) ELSE 0 END) as total_revenue
                    FROM orders o
                    WHERE 1=1 {time_filter.replace('m.created_at', 'o.created_at') if time_filter else ''}
                    GROUP BY merchant_id
                ) order_stats ON m.id = order_stats.merchant_id
                LEFT JOIN (
                    SELECT 
                        merchant_id,
                        COUNT(*) as total_interactions
                    FROM activity_logs al
                    WHERE merchant_id IS NOT NULL {time_filter.replace('m.created_at', 'al.timestamp') if time_filter else ''}
                    GROUP BY merchant_id
                ) activity_stats ON m.id = activity_stats.merchant_id
                WHERE 1=1 {merchant_filter_sql}
                ORDER BY total_orders DESC, total_interactions DESC
                LIMIT 100
            """
            
            merchants_data = await db_manager.fetch_all(performance_query, build_query_params())
            
            # 区县聚合分析（SQL层面聚合）
            district_analysis_query = f"""
                SELECT 
                    COALESCE(d.name, '未知') as district_name,
                    COUNT(DISTINCT m.id) as merchant_count,
                    SUM(COALESCE(order_stats.total_orders, 0)) as total_orders,
                    SUM(COALESCE(order_stats.total_revenue, 0)) as total_revenue,
                    AVG(COALESCE(activity_stats.total_interactions, 0)) as avg_interactions
                FROM merchants m
                LEFT JOIN districts d ON m.district_id = d.id
                LEFT JOIN (
                    SELECT merchant_id, COUNT(*) as total_orders, 
                           SUM(CASE WHEN status = '已完成' AND price IS NOT NULL THEN CAST(price as REAL) ELSE 0 END) as total_revenue
                    FROM orders o WHERE 1=1 {time_filter.replace('m.created_at', 'o.created_at') if time_filter else ''}
                    GROUP BY merchant_id
                ) order_stats ON m.id = order_stats.merchant_id
                LEFT JOIN (
                    SELECT merchant_id, COUNT(*) as total_interactions
                    FROM activity_logs al WHERE merchant_id IS NOT NULL {time_filter.replace('m.created_at', 'al.timestamp') if time_filter else ''}
                    GROUP BY merchant_id
                ) activity_stats ON m.id = activity_stats.merchant_id
                WHERE 1=1 {merchant_filter_sql}
                GROUP BY d.name
                HAVING merchant_count > 0
                ORDER BY total_orders DESC
                LIMIT 20
            """
            district_data = await db_manager.fetch_all(district_analysis_query, build_query_params())
            
            # 商户类型分析（SQL层面聚合）
            category_analysis_query = f"""
                SELECT 
                    m.merchant_type,
                    COUNT(DISTINCT m.id) as merchant_count,
                    SUM(COALESCE(order_stats.total_orders, 0)) as total_orders,
                    SUM(COALESCE(order_stats.total_revenue, 0)) as total_revenue,
                    AVG(COALESCE(activity_stats.total_interactions, 0)) as avg_interactions
                FROM merchants m
                LEFT JOIN (
                    SELECT merchant_id, COUNT(*) as total_orders,
                           SUM(CASE WHEN status = '已完成' AND price IS NOT NULL THEN CAST(price as REAL) ELSE 0 END) as total_revenue
                    FROM orders o WHERE 1=1 {time_filter.replace('m.created_at', 'o.created_at') if time_filter else ''}
                    GROUP BY merchant_id
                ) order_stats ON m.id = order_stats.merchant_id
                LEFT JOIN (
                    SELECT merchant_id, COUNT(*) as total_interactions
                    FROM activity_logs al WHERE merchant_id IS NOT NULL {time_filter.replace('m.created_at', 'al.timestamp') if time_filter else ''}
                    GROUP BY merchant_id
                ) activity_stats ON m.id = activity_stats.merchant_id
                WHERE m.merchant_type IS NOT NULL {merchant_filter_sql}
                GROUP BY m.merchant_type
                HAVING merchant_count > 0
                ORDER BY total_orders DESC
            """
            
            category_data = await db_manager.fetch_all(category_analysis_query, build_query_params())
            
            # 基础汇总指标（SQL层面聚合）
            summary_query = f"""
                SELECT 
                    COUNT(DISTINCT m.id) as total_merchants,
                    COUNT(DISTINCT CASE WHEN m.status IN ('approved', 'published') THEN m.id END) as active_merchants,
                    SUM(COALESCE(order_stats.total_orders, 0)) as total_orders,
                    SUM(COALESCE(order_stats.total_revenue, 0)) as total_revenue,
                    AVG(COALESCE(activity_stats.total_interactions, 0)) as avg_interactions_per_merchant
                FROM merchants m
                LEFT JOIN (
                    SELECT merchant_id, COUNT(*) as total_orders,
                           SUM(CASE WHEN status = '已完成' AND price IS NOT NULL THEN CAST(price as REAL) ELSE 0 END) as total_revenue
                    FROM orders o WHERE 1=1 {time_filter.replace('m.created_at', 'o.created_at') if time_filter else ''}
                    GROUP BY merchant_id
                ) order_stats ON m.id = order_stats.merchant_id
                LEFT JOIN (
                    SELECT merchant_id, COUNT(*) as total_interactions
                    FROM activity_logs al WHERE merchant_id IS NOT NULL {time_filter.replace('m.created_at', 'al.timestamp') if time_filter else ''}
                    GROUP BY merchant_id
                ) activity_stats ON m.id = activity_stats.merchant_id
                WHERE 1=1 {merchant_filter_sql}
            """
            
            summary_result = await db_manager.fetch_one(summary_query, build_query_params())
            
            # 构建返回数据
            analytics_data = {
                'basic_metrics': dict(summary_result) if summary_result else {},
                'merchant_rankings': [dict(row) for row in merchants_data],
                'district_analysis': {row['district_name']: dict(row) for row in district_data},
                'category_analysis': {row['merchant_type']: dict(row) for row in category_data},
                'performance_tiers': await MerchantManager._calculate_performance_tiers([dict(row) for row in merchants_data])
            }
            
            logger.info("商户绩效分析完成")
            return analytics_data
            
        except Exception as e:
            logger.error(f"商户绩效分析失败: {e}")
            return {}
    
    @staticmethod
    async def get_merchant_registration_trends(days: int = 30) -> Dict[str, Any]:
        """
        商户注册趋势分析 - 数据库层聚合计算
        
        Args:
            days: 分析天数
            
        Returns:
            注册趋势数据
        """
        try:
            # 每日注册趋势（SQL聚合）
            daily_trends_query = """
                SELECT 
                    DATE(created_at) as registration_date,
                    COUNT(*) as registrations,
                    COUNT(CASE WHEN status IN ('approved', 'published') THEN 1 END) as approved_count,
                    COUNT(CASE WHEN merchant_type = 'teacher' THEN 1 END) as teacher_count,
                    COUNT(CASE WHEN merchant_type = 'business' THEN 1 END) as business_count
                FROM merchants 
                WHERE created_at >= datetime('now', '-' || ? || ' days')
                GROUP BY DATE(created_at)
                ORDER BY registration_date DESC
            """
            
            daily_data = await db_manager.fetch_all(daily_trends_query, (days,))
            
            # 注册渠道分析（如果有来源数据）
            source_analysis_query = """
                SELECT 
                    COALESCE(JSON_EXTRACT(profile_data, '$.registration_source'), '直接注册') as source,
                    COUNT(*) as count
                FROM merchants
                WHERE created_at >= datetime('now', '-' || ? || ' days')
                GROUP BY source
                ORDER BY count DESC
            """
            
            source_data = await db_manager.fetch_all(source_analysis_query, (days,))
            
            # 计算趋势指标
            if len(daily_data) >= 2:
                recent_avg = sum(row['registrations'] for row in daily_data[:7]) / min(7, len(daily_data))
                earlier_avg = sum(row['registrations'] for row in daily_data[-7:]) / min(7, len(daily_data[-7:]))
                growth_rate = ((recent_avg - earlier_avg) / max(earlier_avg, 1)) * 100 if earlier_avg > 0 else 0
            else:
                growth_rate = 0
            
            return {
                'daily_trends': [dict(row) for row in daily_data],
                'registration_sources': {row['source']: row['count'] for row in source_data},
                'growth_rate': growth_rate,
                'total_registrations': sum(row['registrations'] for row in daily_data),
                'average_daily': sum(row['registrations'] for row in daily_data) / max(len(daily_data), 1)
            }
            
        except Exception as e:
            logger.error(f"商户注册趋势分析失败: {e}")
            return {}
    
    @staticmethod
    async def _calculate_performance_tiers(merchants_data: List[Dict]) -> Dict[str, Any]:
        """
        计算商户表现分层（数据已从数据库聚合获取）
        """
        try:
            if not merchants_data:
                return {}
            
            # 基于订单数分层
            sorted_merchants = sorted(merchants_data, key=lambda x: x.get('total_orders', 0), reverse=True)
            total_count = len(sorted_merchants)
            
            # 分层标准
            high_threshold = max(1, total_count // 5)  # 前20%
            medium_threshold = max(1, total_count // 2)  # 前50%
            
            high_performers = sorted_merchants[:high_threshold]
            medium_performers = sorted_merchants[high_threshold:medium_threshold]
            low_performers = sorted_merchants[medium_threshold:]
            
            return {
                'high_performers': {
                    'count': len(high_performers),
                    'percentage': (len(high_performers) / total_count) * 100,
                    'avg_orders': sum(m.get('total_orders', 0) for m in high_performers) / max(len(high_performers), 1),
                    'avg_revenue': sum(m.get('total_revenue', 0) for m in high_performers) / max(len(high_performers), 1)
                },
                'medium_performers': {
                    'count': len(medium_performers),
                    'percentage': (len(medium_performers) / total_count) * 100,
                    'avg_orders': sum(m.get('total_orders', 0) for m in medium_performers) / max(len(medium_performers), 1),
                    'avg_revenue': sum(m.get('total_revenue', 0) for m in medium_performers) / max(len(medium_performers), 1)
                },
                'low_performers': {
                    'count': len(low_performers),
                    'percentage': (len(low_performers) / total_count) * 100,
                    'avg_orders': sum(m.get('total_orders', 0) for m in low_performers) / max(len(low_performers), 1),
                    'avg_revenue': sum(m.get('total_revenue', 0) for m in low_performers) / max(len(low_performers), 1)
                }
            }
            
        except Exception as e:
            logger.error(f"计算商户表现分层失败: {e}")
            return {}

    @staticmethod
    async def _log_merchant_activity(merchant_id: int, action_type: str, details: Dict[str, Any]):
        """
        记录商户活动日志
        
        Args:
            merchant_id: 商户永久ID
            action_type: 活动类型
            details: 活动详情
        """
        try:
            query = """
                INSERT INTO activity_logs (user_id, action_type, details, merchant_id, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """
            
            await db_manager.execute_query(
                query,
                (
                    0,  # 系统操作
                    action_type,
                    json.dumps(details, ensure_ascii=False),
                    merchant_id,
                    datetime.now()
                )
            )
            
        except Exception as e:
            logger.warning(f"记录商户活动日志失败: {e}")


# V1兼容性便捷函数（保持原有API不变）
async def create_merchant(merchant_data: Dict[str, Any]) -> Optional[int]:
    """创建商户的便捷函数。支持V1和V2数据格式自动转换。"""
    # V1到V2字段映射（向后兼容）
    if 'chat_id' in merchant_data and 'telegram_chat_id' not in merchant_data:
        merchant_data['telegram_chat_id'] = merchant_data['chat_id']
    
    return await MerchantManager.create_merchant(merchant_data)

async def create_blank_merchant(user_id: int, binding_code: str = None) -> Optional[int]:
    """创建空白商户的便捷函数"""
    return await MerchantManager.create_blank_merchant(user_id, binding_code)

async def get_merchant(merchant_id: int) -> Optional[Dict[str, Any]]:
    """获取商户的便捷函数"""
    return await MerchantManager.get_merchant(merchant_id)

async def get_merchant_by_id(merchant_id: int) -> Optional[Dict[str, Any]]:
    """根据永久ID获取商户的便捷函数（兼容API）"""
    return await MerchantManager.get_merchant_by_id(merchant_id)

async def get_merchant_by_chat_id(telegram_chat_id: int) -> Optional[Dict[str, Any]]:
    """根据telegram_chat_id获取商户的便捷函数"""
    return await MerchantManager.get_merchant_by_chat_id(telegram_chat_id)

async def get_all_merchants(status_filter: Optional[str] = None, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
    """获取所有商户的便捷函数"""
    return await MerchantManager.get_all_merchants(status_filter, limit, offset)

async def update_merchant(merchant_id: int, update_data: Dict[str, Any]) -> bool:
    """更新商户的便捷函数"""
    return await MerchantManager.update_merchant(merchant_id, update_data)

async def update_merchant_status(merchant_id: int, status: str, publish_time: Any = None, expiration_time: Any = None) -> bool:
    """更新商户状态的便捷函数（可选同步发布时间/到期时间）"""
    return await MerchantManager.update_merchant_status(merchant_id, status, publish_time, expiration_time)

async def delete_merchant(merchant_id: int) -> bool:
    """删除商户的便捷函数"""
    return await MerchantManager.delete_merchant(merchant_id)

async def search_merchants(
    search_term: str,
    search_fields: List[str] = None,
    status_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """搜索商户的便捷函数"""
    return await MerchantManager.search_merchants(search_term, search_fields, status_filter)

async def get_merchant_statistics() -> Dict[str, Any]:
    """获取商户统计的便捷函数"""
    return await MerchantManager.get_merchant_statistics()

async def count_merchants() -> int:
    """统计商户总数（便捷函数）"""
    return await MerchantManager.count_merchants()

async def get_merchants_count_by_region() -> Dict[str, int]:
    """按地区统计商户数量（便捷函数）"""
    return await MerchantManager.get_merchants_count_by_region()

async def get_merchant_type_statistics():
    """获取商家类型统计"""
    try:
        query = """
            SELECT merchant_type, COUNT(*) as count
            FROM merchants 
            WHERE merchant_type IS NOT NULL
            GROUP BY merchant_type
        """
        results = await db_manager.fetch_all(query)
        return {row['merchant_type']: row['count'] for row in results}
    except Exception as e:
        logger.error(f"获取商家类型统计失败: {e}")
        return {}

async def toggle_merchant_region_search_status(merchant_id: int) -> bool:
    """切换商家地区搜索状态的便捷函数"""
    return await MerchantManager.toggle_merchant_region_search_status(merchant_id)

# V1兼容别名
# 为了与现有代码完全兼容，保留这些别名
get_merchant_stats = get_merchant_statistics  # V1别名
merchants_db = MerchantManager  # V1实例名

# 创建实例
merchant_manager = MerchantManager()
