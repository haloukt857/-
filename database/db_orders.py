# -*- coding: utf-8 -*-
"""
订单数据库管理器
完全替代V1版本，提供所有订单相关功能
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from decimal import Decimal
import json

from database.db_connection import db_manager

logger = logging.getLogger(__name__)

class OrderManager:
    """
    订单数据库管理器 V2.0
    外科手术式迁移V1全部功能，适配新架构，增加Web界面支持
    """
    
    @staticmethod
    async def create_order(order_data: Dict[str, Any]) -> Optional[int]:
        """
        创建新订单
        
        Args:
            order_data: 订单数据字典，包含以下字段：
                - customer_user_id: 用户Telegram ID
                - customer_username: 用户名（可选）
                - merchant_id: 商户ID
                - price: 价格
                - appointment_time: 预约时间（可选）
                - status: 订单状态（五阶段：尝试预约, 已完成, 已评价, 双方评价, 单方评价）
                
        Returns:
            新创建订单的ID或None（失败时）
            
        Raises:
            ValueError: 当必需字段缺失或数据无效时
            Exception: 数据库操作失败时
        """
        try:
            # 验证必需字段
            required_fields = ['customer_user_id', 'merchant_id', 'price']
            for field in required_fields:
                if field not in order_data or order_data[field] is None:
                    raise ValueError(f"缺少必需字段: {field}")
            
            # 验证订单状态
            valid_statuses = ['尝试预约', '已完成', '已评价', '双方评价', '单方评价']
            status = order_data.get('status', '尝试预约')
            if status not in valid_statuses:
                logger.warning(f"无效状态 {status}，使用默认状态 '尝试预约'")
                status = '尝试预约'
            
            # 确保用户存在于users表中（可选，如果users表存在）
            try:
                from .db_users import user_manager
                # 提供默认username（如果没有提供）
                username = order_data.get('customer_username', f"user_{order_data['customer_user_id']}")
                await user_manager.create_or_update_user(order_data['customer_user_id'], username)
            except ImportError:
                # 如果users模块不存在，跳过用户创建
                pass
            
            # 适配表结构的插入查询
            insert_query = """
                INSERT INTO orders (
                    merchant_id, customer_user_id, customer_username,
                    course_type, price, appointment_time, completion_time, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """
            
            params = (
                order_data['merchant_id'],
                order_data['customer_user_id'], 
                order_data.get('customer_username'),
                order_data.get('course_type'),
                order_data['price'],
                order_data.get('appointment_time'),
                order_data.get('completion_time'),
                status
            )
            
            order_id = await db_manager.get_last_insert_id(insert_query, params)
            
            logger.info(f"成功创建订单，ID: {order_id}, 用户: {order_data['customer_user_id']}, 商户: {order_data['merchant_id']}, 状态: {status}")
            return order_id
            
        except ValueError as e:
            logger.error(f"订单数据验证失败: {e}")
            raise
        except Exception as e:
            logger.error(f"创建订单失败: {e}")
            raise

    @staticmethod
    async def get_order(order_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取订单详情（核心方法）
        
        Args:
            order_id: 订单ID
            
        Returns:
            订单信息字典或None（如果订单不存在）
        """
        try:
            query = """
                SELECT o.*, m.name as merchant_name, m.telegram_chat_id as merchant_chat_id
                FROM orders o
                LEFT JOIN merchants m ON o.merchant_id = m.id
                WHERE o.id = ?
            """
            
            result = await db_manager.fetch_one(query, (order_id,))
            
            if result:
                order_dict = dict(result)
                logger.debug(f"获取订单成功，ID: {order_id}")
                return order_dict
            else:
                logger.warning(f"订单不存在，ID: {order_id}")
                return None
                
        except Exception as e:
            logger.error(f"获取订单失败，ID: {order_id}, 错误: {e}")
            raise

    @staticmethod
    async def get_orders_by_merchant(
        merchant_id: int, 
        status: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        按商户获取订单列表（核心方法）
        
        Args:
            merchant_id: 商户ID
            status: 订单状态过滤（可选）
            limit: 返回数量限制（可选）
            offset: 偏移量，用于分页
            
        Returns:
            订单列表
        """
        try:
            query = """
                SELECT o.*, m.name as merchant_name
                FROM orders o
                LEFT JOIN merchants m ON o.merchant_id = m.id
                WHERE o.merchant_id = ?
            """
            params = [merchant_id]
            
            # 添加状态过滤
            if status:
                valid_statuses = ['尝试预约', '已完成', '已评价', '双方评价', '单方评价']
                if status in valid_statuses:
                    query += " AND o.status = ?"
                    params.append(status)
                else:
                    logger.warning(f"无效的状态过滤: {status}")
            
            query += " ORDER BY o.created_at DESC"
            
            # 添加分页
            if limit:
                query += " LIMIT ?"
                params.append(limit)
                if offset > 0:
                    query += " OFFSET ?"
                    params.append(offset)
            
            results = await db_manager.fetch_all(query, tuple(params))
            
            orders = [dict(row) for row in results]
            logger.debug(f"获取商户订单成功，商户ID: {merchant_id}, 数量: {len(orders)}")
            return orders
            
        except Exception as e:
            logger.error(f"获取商户订单失败，商户ID: {merchant_id}, 错误: {e}")
            raise

    @staticmethod
    async def get_orders_by_user(
        customer_user_id: int,
        status: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        按用户获取订单列表（核心方法）
        
        Args:
            customer_user_id: 用户ID
            status: 订单状态过滤（可选）
            limit: 返回数量限制（可选）
            
        Returns:
            订单列表
        """
        try:
            query = """
                SELECT o.*, m.name as merchant_name, m.telegram_chat_id as merchant_chat_id
                FROM orders o
                LEFT JOIN merchants m ON o.merchant_id = m.id
                WHERE o.customer_user_id = ?
            """
            params = [customer_user_id]
            
            if status:
                valid_statuses = ['尝试预约', '已完成', '已评价', '双方评价', '单方评价']
                if status in valid_statuses:
                    query += " AND o.status = ?"
                    params.append(status)
            
            query += " ORDER BY o.created_at DESC"
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            results = await db_manager.fetch_all(query, tuple(params))
            
            orders = [dict(row) for row in results]
            logger.debug(f"获取用户订单成功，用户ID: {customer_user_id}, 数量: {len(orders)}")
            return orders
            
        except Exception as e:
            logger.error(f"获取用户订单失败，用户ID: {customer_user_id}, 错误: {e}")
            raise

    @staticmethod
    async def get_orders_by_timeframe(
        start_date: datetime,
        end_date: datetime,
        merchant_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        按时间范围获取订单（核心方法）
        
        Args:
            start_date: 开始时间
            end_date: 结束时间
            merchant_id: 商户ID过滤（可选）
            status: 订单状态过滤（可选）
            
        Returns:
            订单列表
        """
        try:
            query = """
                SELECT o.*, m.name as merchant_name, m.telegram_chat_id as merchant_chat_id
                FROM orders o
                LEFT JOIN merchants m ON o.merchant_id = m.id
                WHERE o.created_at BETWEEN ? AND ?
            """
            params = [start_date, end_date]
            
            # 添加可选过滤条件
            if merchant_id:
                query += " AND o.merchant_id = ?"
                params.append(merchant_id)
            
            if status:
                valid_statuses = ['尝试预约', '已完成', '已评价', '双方评价', '单方评价']
                if status in valid_statuses:
                    query += " AND o.status = ?"
                    params.append(status)
            
            query += " ORDER BY o.created_at DESC"
            
            results = await db_manager.fetch_all(query, tuple(params))
            
            orders = [dict(row) for row in results]
            logger.debug(f"按时间范围获取订单成功，数量: {len(orders)}")
            return orders
            
        except Exception as e:
            logger.error(f"按时间范围获取订单失败: {e}")
            raise

    @staticmethod
    async def update_order_status(order_id: int, status: str, completion_time: Optional[datetime] = None) -> bool:
        """
        更新订单状态（核心方法）
        
        Args:
            order_id: 订单ID
            status: 新状态（五阶段状态）
            completion_time: 完成时间（可选，状态为已完成时自动设置）
            
        Returns:
            更新是否成功
        """
        try:
            # 验证状态值
            valid_statuses = ['尝试预约', '已完成', '已评价', '双方评价', '单方评价']
            if status not in valid_statuses:
                raise ValueError(f"无效的订单状态: {status}")
            
            # 如果状态是已完成且没有提供完成时间，则使用当前时间
            if status in ['已完成', '已评价', '双方评价', '单方评价'] and completion_time is None:
                completion_time = datetime.now()
            
            query = """
                UPDATE orders 
                SET status = ?, completion_time = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """
            params = (status, completion_time, order_id)
            
            result = await db_manager.execute_query(query, params)
            
            if result > 0:
                logger.info(f"订单状态更新成功，ID: {order_id}, 新状态: {status}")
                # 新版：不在此处自动触发旧评价流程，避免重复流程
                
                return True
            else:
                logger.warning(f"订单不存在或状态未改变，ID: {order_id}")
                return False
                
        except ValueError as e:
            logger.error(f"订单状态验证失败: {e}")
            raise
        except Exception as e:
            logger.error(f"更新订单状态失败，ID: {order_id}, 错误: {e}")
            raise

    @staticmethod
    async def update_order(order_id: int, update_data: Dict[str, Any]) -> bool:
        """
        通用订单信息更新（核心方法）
        
        Args:
            order_id: 订单ID
            update_data: 要更新的字段字典
            
        Returns:
            更新是否成功
        """
        try:
            if not update_data:
                raise ValueError("更新数据不能为空")
            
            # 允许更新的字段
            allowed_fields = [
                'customer_username', 'course_type', 'price', 'appointment_time',
                'completion_time', 'status'
            ]
            
            update_fields = []
            params = []
            
            for field, value in update_data.items():
                if field in allowed_fields:
                    # 特殊处理状态字段验证
                    if field == 'status':
                        valid_statuses = ['尝试预约', '已完成', '已评价', '双方评价', '单方评价']
                        if value not in valid_statuses:
                            logger.warning(f"无效的状态值: {value}，跳过更新")
                            continue
                    
                    update_fields.append(f"{field} = ?")
                    params.append(value)
            
            if not update_fields:
                raise ValueError("没有有效的更新字段")
            
            # 添加updated_at字段
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            
            query = f"UPDATE orders SET {', '.join(update_fields)} WHERE id = ?"
            params.append(order_id)
            
            result = await db_manager.execute_query(query, tuple(params))
            
            if result > 0:
                logger.info(f"订单更新成功，ID: {order_id}")
                return True
            else:
                logger.warning(f"订单不存在或数据未改变，ID: {order_id}")
                return False
                
        except Exception as e:
            logger.error(f"更新订单失败，ID: {order_id}, 错误: {e}")
            raise

    @staticmethod
    async def delete_order(order_id: int) -> bool:
        """
        删除订单（核心方法）
        
        Args:
            order_id: 订单ID
            
        Returns:
            删除是否成功
        """
        try:
            query = "DELETE FROM orders WHERE id = ?"
            result = await db_manager.execute_query(query, (order_id,))
            
            if result > 0:
                logger.info(f"订单删除成功，ID: {order_id}")
                return True
            else:
                logger.warning(f"订单不存在，ID: {order_id}")
                return False
                
        except Exception as e:
            logger.error(f"删除订单失败，ID: {order_id}, 错误: {e}")
            raise

    @staticmethod
    async def get_order_statistics(
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        merchant_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        获取详细的订单统计报告（核心方法）
        
        Args:
            start_date: 开始时间（可选，默认为30天前）
            end_date: 结束时间（可选，默认为当前时间）
            merchant_id: 商户ID过滤（可选）
            
        Returns:
            统计信息字典，包含：
            - total_orders: 总订单数
            - orders_by_status: 按状态分组的订单数
            - total_revenue: 总收入
            - average_order_value: 平均订单价值
            - orders_by_day: 按日期分组的订单数
        """
        try:
            # 设置默认时间范围
            if not end_date:
                end_date = datetime.now()
            if not start_date:
                start_date = end_date - timedelta(days=30)
            
            # 基础查询条件
            base_where = "WHERE created_at BETWEEN ? AND ?"
            base_params = [start_date, end_date]
            
            if merchant_id:
                base_where += " AND merchant_id = ?"
                base_params.append(merchant_id)
            
            # 获取总订单数
            total_query = f"SELECT COUNT(*) as total FROM orders {base_where}"
            total_result = await db_manager.fetch_one(total_query, tuple(base_params))
            total_orders = total_result['total'] if total_result else 0
            
            # 按状态分组统计
            status_query = f"""
                SELECT status, COUNT(*) as count 
                FROM orders {base_where}
                GROUP BY status
            """
            status_results = await db_manager.fetch_all(status_query, tuple(base_params))
            orders_by_status = {row['status']: row['count'] for row in status_results}
            
            # 收入统计
            revenue_query = f"""
                SELECT 
                    SUM(CASE WHEN price IS NOT NULL THEN price ELSE 0 END) as total_revenue,
                    AVG(CASE WHEN price IS NOT NULL THEN price ELSE NULL END) as avg_order_value,
                    COUNT(CASE WHEN price IS NOT NULL THEN 1 END) as paid_orders
                FROM orders {base_where}
            """
            revenue_result = await db_manager.fetch_one(revenue_query, tuple(base_params))
            
            total_revenue = float(revenue_result['total_revenue']) if revenue_result['total_revenue'] else 0.0
            avg_order_value = float(revenue_result['avg_order_value']) if revenue_result['avg_order_value'] else 0.0
            paid_orders = revenue_result['paid_orders'] if revenue_result else 0
            
            # 按日期分组统计
            daily_query = f"""
                SELECT 
                    DATE(created_at) as order_date,
                    COUNT(*) as count
                FROM orders {base_where}
                GROUP BY DATE(created_at)
                ORDER BY order_date DESC
            """
            daily_results = await db_manager.fetch_all(daily_query, tuple(base_params))
            orders_by_day = {row['order_date']: row['count'] for row in daily_results}
            
            statistics = {
                'total_orders': total_orders,
                'orders_by_status': orders_by_status,
                'total_revenue': total_revenue,
                'average_order_value': avg_order_value,
                'paid_orders': paid_orders,
                'orders_by_day': orders_by_day,
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'status_summary': {
                    '尝试预约': orders_by_status.get('尝试预约', 0),
                    '已完成': orders_by_status.get('已完成', 0),
                    '已评价': orders_by_status.get('已评价', 0),
                    '双方评价': orders_by_status.get('双方评价', 0),
                    '单方评价': orders_by_status.get('单方评价', 0)
                }
            }
            
            logger.info(f"订单统计生成成功，总订单数: {total_orders}")
            return statistics
            
        except Exception as e:
            logger.error(f"获取订单统计失败: {e}")
            raise

    @staticmethod
    async def get_merchant_order_summary(merchant_id: int) -> Dict[str, Any]:
        """
        获取单个商户的订单摘要（核心方法）
        
        Args:
            merchant_id: 商户ID
            
        Returns:
            商户订单摘要字典
        """
        try:
            # 获取商户基本信息
            merchant_query = "SELECT name, status FROM merchants WHERE id = ?"
            merchant_result = await db_manager.fetch_one(merchant_query, (merchant_id,))
            
            if not merchant_result:
                raise ValueError(f"商户不存在，ID: {merchant_id}")
            
            # 获取订单统计
            stats_query = """
                SELECT 
                    COUNT(*) as total_orders,
                    COUNT(CASE WHEN status = '尝试预约' THEN 1 END) as pending_orders,
                    COUNT(CASE WHEN status = '已完成' THEN 1 END) as completed_orders,
                    COUNT(CASE WHEN status = '已评价' THEN 1 END) as reviewed_orders,
                    COUNT(CASE WHEN status = '双方评价' THEN 1 END) as mutual_review_orders,
                    COUNT(CASE WHEN status = '单方评价' THEN 1 END) as single_review_orders,
                    SUM(CASE WHEN price IS NOT NULL THEN price ELSE 0 END) as total_revenue,
                    MAX(created_at) as last_order_date
                FROM orders 
                WHERE merchant_id = ?
            """
            
            stats_result = await db_manager.fetch_one(stats_query, (merchant_id,))
            
            summary = {
                'merchant_id': merchant_id,
                'merchant_name': merchant_result['name'],
                'merchant_status': merchant_result['status'],
                'total_orders': stats_result['total_orders'] or 0,
                'pending_orders': stats_result['pending_orders'] or 0,
                'completed_orders': stats_result['completed_orders'] or 0,
                'reviewed_orders': stats_result['reviewed_orders'] or 0,
                'mutual_review_orders': stats_result['mutual_review_orders'] or 0,
                'single_review_orders': stats_result['single_review_orders'] or 0,
                'total_revenue': float(stats_result['total_revenue']) if stats_result['total_revenue'] else 0.0,
                'last_order_date': stats_result['last_order_date'],
                'metrics': {
                    '预约订单': stats_result['pending_orders'] or 0,
                    '完成订单': stats_result['completed_orders'] or 0,
                    '评价订单': (stats_result['reviewed_orders'] or 0) + (stats_result['mutual_review_orders'] or 0) + (stats_result['single_review_orders'] or 0)
                }
            }
            
            logger.debug(f"商户订单摘要生成成功，商户ID: {merchant_id}")
            return summary
            
        except Exception as e:
            logger.error(f"获取商户订单摘要失败，商户ID: {merchant_id}, 错误: {e}")
            raise

    @staticmethod
    async def get_orders_with_review_status() -> List[Dict[str, Any]]:
        """
        获取订单列表，包含评价状态（专用于Web后台）
        
        Returns:
            订单列表，每个订单包含review_status字段映射
        """
        try:
            query = """
                SELECT o.id as order_id, o.merchant_id, o.customer_user_id,
                       o.customer_username as user_username, o.price, o.status as order_status,
                       o.created_at, m.name as merchant_name,
                       CASE 
                           WHEN o.status = '尝试预约' THEN 'pending_user_review'
                           WHEN o.status IN ('已评价', '双方评价', '单方评价') THEN 'completed'
                           ELSE 'pending_merchant_review'
                       END as review_status
                FROM orders o
                LEFT JOIN merchants m ON o.merchant_id = m.id
                ORDER BY o.created_at DESC
            """
            results = await db_manager.fetch_all(query, ())
            
            orders = [dict(row) for row in results]
            logger.debug(f"获取带评价状态的订单成功，数量: {len(orders)}")
            return orders
            
        except Exception as e:
            logger.error(f"获取带评价状态的订单失败: {e}")
            raise

    # V1兼容性方法（向后兼容）
    @staticmethod 
    async def create_order_v1_compat(user_id: int, merchant_id: int, price: int, **kwargs) -> Optional[int]:
        """V1兼容性方法：使用V1参数格式创建订单"""
        order_data = {
            'customer_user_id': user_id,  # V1 -> V2字段映射
            'merchant_id': merchant_id,
            'price': price,
            'customer_username': kwargs.get('username'),
            'appointment_time': kwargs.get('appointment_time'),
            'status': kwargs.get('status', '尝试预约')
        }
        return await OrderManager.create_order(order_data)

    # ==========  V2.0 Web界面支持方法 ==========
    
    @staticmethod
    async def get_orders(
        status: Optional[str] = None,
        merchant_id: Optional[int] = None, 
        user_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取订单列表（Web界面专用）
        支持高级筛选和分页
        """
        try:
            conditions = []
            params = []
            
            base_query = """
                SELECT o.id, o.merchant_id, o.customer_user_id, o.customer_username,
                       o.price, o.status, o.appointment_time, o.completion_time, o.created_at,
                       m.name as merchant_name
                FROM orders o
                LEFT JOIN merchants m ON o.merchant_id = m.id
            """
            
            if status:
                conditions.append("o.status = ?")
                params.append(status)
            
            if merchant_id:
                conditions.append("o.merchant_id = ?")
                params.append(merchant_id)
            
            if user_id:
                conditions.append("o.customer_user_id = ?")
                params.append(user_id)
            
            if date_from:
                conditions.append("o.created_at >= ?")
                params.append(date_from)
            
            if date_to:
                conditions.append("o.created_at < ?")
                params.append(date_to)
            
            if search:
                conditions.append("(o.customer_username LIKE ? OR m.name LIKE ? OR o.id LIKE ?)")
                search_param = f"%{search}%"
                params.extend([search_param, search_param, search_param])
            
            # 构建完整查询
            if conditions:
                base_query += " WHERE " + " AND ".join(conditions)
            
            base_query += " ORDER BY o.created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            results = await db_manager.fetch_all(base_query, tuple(params))
            orders = [dict(row) for row in results]
            
            logger.debug(f"获取订单列表成功，数量: {len(orders)}")
            return orders
            
        except Exception as e:
            logger.error(f"获取订单列表失败: {e}")
            return []
    
    @staticmethod
    async def count_orders(
        status: Optional[str] = None,
        merchant_id: Optional[int] = None,
        user_id: Optional[int] = None, 
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> int:
        """统计符合条件的订单数量"""
        try:
            conditions = []
            params = []
            
            query = "SELECT COUNT(*) as count FROM orders o"
            
            if status:
                conditions.append("o.status = ?")
                params.append(status)
            
            if merchant_id:
                conditions.append("o.merchant_id = ?")
                params.append(merchant_id)
                
            if user_id:
                conditions.append("o.customer_user_id = ?")
                params.append(user_id)
            
            if date_from:
                conditions.append("o.created_at >= ?")
                params.append(date_from)
            
            if date_to:
                conditions.append("o.created_at < ?")
                params.append(date_to)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            result = await db_manager.fetch_one(query, tuple(params))
            return result['count'] if result else 0
            
        except Exception as e:
            logger.error(f"统计订单数量失败: {e}")
            return 0
    
    @staticmethod
    async def get_revenue_stats(
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> float:
        """获取收入统计"""
        try:
            conditions = ["o.status IN (?, ?, ?, ?)"]
            params = ['已完成', '已评价', '双方评价', '单方评价']
            
            query = "SELECT SUM(o.price) as total_revenue FROM orders o"
            
            if date_from:
                conditions.append("o.created_at >= ?")
                params.append(date_from)
            
            if date_to:
                conditions.append("o.created_at < ?")
                params.append(date_to)
            
            query += " WHERE " + " AND ".join(conditions)
            
            result = await db_manager.fetch_one(query, tuple(params))
            return float(result['total_revenue'] or 0)
            
        except Exception as e:
            logger.error(f"获取收入统计失败: {e}")
            return 0.0
    
    @staticmethod
    async def count_active_users(date_from: Optional[str] = None) -> int:
        """统计活跃用户数"""
        try:
            conditions = []
            params = []
            
            query = "SELECT COUNT(DISTINCT o.customer_user_id) as count FROM orders o"
            
            if date_from:
                conditions.append("o.created_at >= ?")
                params.append(date_from)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
                
            result = await db_manager.fetch_one(query, tuple(params))
            return result['count'] if result else 0
            
        except Exception as e:
            logger.error(f"统计活跃用户数失败: {e}")
            return 0
    
    @staticmethod
    async def get_order_by_id(order_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取订单详情（别名方法）"""
        return await OrderManager.get_order(order_id)

    # ==========  统计/分析便捷方法（供Web服务调用） ==========

    @staticmethod
    async def count_orders_by_status(status: str) -> int:
        """按状态统计订单数量"""
        try:
            result = await db_manager.fetch_one(
                "SELECT COUNT(*) as count FROM orders WHERE status = ?",
                (status,)
            )
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"按状态统计订单失败: {e}")
            return 0

    @staticmethod
    async def count_orders_since(start_time: datetime) -> int:
        """统计自指定时间起的订单数量"""
        try:
            result = await db_manager.fetch_one(
                "SELECT COUNT(*) as count FROM orders WHERE created_at >= ?",
                (start_time,)
            )
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"统计自时间起订单失败: {e}")
            return 0

    @staticmethod
    async def count_orders_in_range(start_time: datetime, end_time: datetime) -> int:
        """统计时间区间内的订单数量"""
        try:
            result = await db_manager.fetch_one(
                "SELECT COUNT(*) as count FROM orders WHERE created_at >= ? AND created_at < ?",
                (start_time, end_time)
            )
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"统计时间区间订单失败: {e}")
            return 0

    @staticmethod
    async def get_top_merchants_by_order_count(limit: int = 10) -> List[Dict[str, Any]]:
        """按订单数排行的商户列表"""
        try:
            query = """
                SELECT o.merchant_id, m.name as merchant_name, COUNT(*) as order_count
                FROM orders o
                LEFT JOIN merchants m ON o.merchant_id = m.id
                GROUP BY o.merchant_id
                ORDER BY order_count DESC
                LIMIT ?
            """
            results = await db_manager.fetch_all(query, (int(limit),))
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取按订单数排行商户失败: {e}")
            return []

    @staticmethod
    async def get_top_users_by_order_count(limit: int = 10) -> List[Dict[str, Any]]:
        """按下单数排行的用户列表"""
        try:
            query = """
                SELECT o.customer_user_id as user_id, u.username, COUNT(*) as order_count
                FROM orders o
                LEFT JOIN users u ON o.customer_user_id = u.user_id
                GROUP BY o.customer_user_id
                ORDER BY order_count DESC
                LIMIT ?
            """
            results = await db_manager.fetch_all(query, (int(limit),))
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取按下单数排行用户失败: {e}")
            return []

    @staticmethod
    async def get_daily_order_counts(days: int = 30) -> List[Dict[str, Any]]:
        """最近N天每日订单数量"""
        try:
            from datetime import datetime, timedelta
            start_date = (datetime.now() - timedelta(days=max(0, int(days) - 1)))
            query = """
                SELECT DATE(created_at) as day, COUNT(*) as count
                FROM orders
                WHERE created_at >= ?
                GROUP BY DATE(created_at)
                ORDER BY day ASC
            """
            results = await db_manager.fetch_all(query, (start_date,))
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取每日订单数失败: {e}")
            return []


# 创建全局实例
order_manager = OrderManager()
