# -*- coding: utf-8 -*-
"""
绑定码数据库管理器
完全替代V1版本，提供所有绑定码相关功能
"""

import logging
import secrets
import string
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from database.db_connection import db_manager

logger = logging.getLogger(__name__)

class BindingCodesManager:
    """
    绑定码数据库管理器
    提供绑定码生成、验证、使用、查询、统计等全套功能
    """
    
    # 绑定码配置常量
    CODE_LENGTH = 8  # 绑定码长度
    CODE_CHARSET = string.ascii_uppercase + string.digits  # 使用大写字母和数字
    DEFAULT_EXPIRY_HOURS = 24  # 默认过期时间（小时）

    @staticmethod
    async def generate_binding_code(expiry_hours: Optional[int] = None) -> Dict[str, Any]:
        """
        生成新的绑定码
        
        Args:
            expiry_hours: 过期时间（小时），默认为24小时
            
        Returns:
            包含绑定码信息的字典
            
        Raises:
            Exception: 生成绑定码失败时
        """
        try:
            if expiry_hours is None:
                expiry_hours = BindingCodesManager.DEFAULT_EXPIRY_HOURS
            
            # 计算过期时间
            expires_at = datetime.now() + timedelta(hours=expiry_hours) if expiry_hours > 0 else None
            
            # 生成唯一绑定码
            max_attempts = 10
            for attempt in range(max_attempts):
                # 生成随机码
                code = ''.join(
                    secrets.choice(BindingCodesManager.CODE_CHARSET) 
                    for _ in range(BindingCodesManager.CODE_LENGTH)
                )
                
                # 检查是否已存在
                existing = await BindingCodesManager._check_code_exists(code)
                if not existing:
                    # 插入新绑定码，包含过期时间
                    insert_query = """
                        INSERT INTO binding_codes (code, is_used, created_at, expires_at)
                        VALUES (?, FALSE, CURRENT_TIMESTAMP, ?)
                    """
                    
                    await db_manager.execute_query(insert_query, (code, expires_at))
                    
                    # 获取插入的记录ID
                    get_id_query = "SELECT id, created_at FROM binding_codes WHERE code = ?"
                    result = await db_manager.fetch_one(get_id_query, (code,))
                    
                    code_info = {
                        'id': result['id'] if result else None,
                        'code': code,
                        'is_used': False,
                        'created_at': result['created_at'] if result else datetime.now().isoformat(),
                        'expires_at': expires_at.isoformat() if expires_at else None,
                        'used_at': None,
                        'merchant_id': None
                    }
                    
                    logger.info(f"成功生成绑定码: {code}")
                    return code_info
            
            # 如果多次尝试都失败，抛出异常
            raise Exception(f"生成唯一绑定码失败，已尝试 {max_attempts} 次")
            
        except Exception as e:
            logger.error(f"生成绑定码失败: {e}")
            raise

    @staticmethod
    async def _check_code_exists(code: str) -> bool:
        """
        检查绑定码是否已存在
        
        Args:
            code: 绑定码
            
        Returns:
            绑定码是否存在
        """
        try:
            query = "SELECT 1 FROM binding_codes WHERE code = ? LIMIT 1"
            result = await db_manager.fetch_one(query, (code,))
            return result is not None
            
        except Exception as e:
            logger.error(f"检查绑定码存在性失败: {e}")
            raise

    @staticmethod
    async def get_binding_code_info(code: str) -> Optional[Dict[str, Any]]:
        """
        获取绑定码详细信息
        
        Args:
            code: 绑定码
            
        Returns:
            绑定码信息字典或None
        """
        try:
            code = code.strip().upper()
            
            query = """
                SELECT bc.*, 
                       m.name as merchant_name, 
                       m.telegram_chat_id as merchant_chat_id,
                       bc.merchant_id as merchant_id
                FROM binding_codes bc
                LEFT JOIN merchants m ON bc.merchant_id = m.id
                WHERE bc.code = ?
            """
            
            result = await db_manager.fetch_one(query, (code,))
            
            if result:
                code_info = dict(result)
                logger.debug(f"获取绑定码信息成功: {code}")
                return code_info
            else:
                logger.warning(f"绑定码不存在: {code}")
                return None
                
        except Exception as e:
            logger.error(f"获取绑定码信息失败: {e}")
            raise

    @staticmethod
    async def get_all_binding_codes(
        include_used: bool = True,
        include_expired: bool = False,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        获取所有绑定码列表
        
        Args:
            include_used: 是否包含已使用的绑定码
            include_expired: 是否包含已过期的绑定码
            limit: 返回数量限制
            
        Returns:
            绑定码列表和统计信息
        """
        try:
            query = """
                SELECT bc.*, 
                       m.name as merchant_name, 
                       m.telegram_chat_id as merchant_chat_id,
                       bc.merchant_id as merchant_id
                FROM binding_codes bc
                LEFT JOIN merchants m ON bc.merchant_id = m.id
                WHERE 1=1
            """
            params = []
            
            # 添加过滤条件
            if not include_used:
                query += " AND bc.is_used = FALSE"
            
            # 添加过期筛选
            if not include_expired:
                query += " AND (bc.expires_at IS NULL OR bc.expires_at > CURRENT_TIMESTAMP)"
            
            query += " ORDER BY bc.created_at DESC"
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            results = await db_manager.fetch_all(query, tuple(params))
            
            codes = [dict(row) for row in results]
            logger.debug(f"获取绑定码列表成功，数量: {len(codes)}")
            
            # 获取总数统计
            count_query = """
                SELECT COUNT(*) as total
                FROM binding_codes bc
                WHERE 1=1
            """
            count_params = []
            
            if not include_used:
                count_query += " AND bc.is_used = FALSE"
            
            if not include_expired:
                count_query += " AND (bc.expires_at IS NULL OR bc.expires_at > CURRENT_TIMESTAMP)"
                
            count_result = await db_manager.fetch_one(count_query, tuple(count_params))
            total_count = count_result['total'] if count_result else 0
            
            return {
                "codes": codes,
                "total": total_count,
                "has_more": limit is not None and len(codes) == limit
            }
            
        except Exception as e:
            logger.error(f"获取绑定码列表失败: {e}")
            raise

    @staticmethod
    async def get_binding_code_statistics() -> Dict[str, Any]:
        """
        获取绑定码统计信息
        
        Returns:
            统计信息字典
        """
        try:
            current_time = datetime.now()
            
            # 总体统计
            total_query = "SELECT COUNT(*) as total FROM binding_codes"
            total_result = await db_manager.fetch_one(total_query)
            total_codes = total_result['total'] if total_result else 0
            
            # 已使用统计
            used_query = "SELECT COUNT(*) as used FROM binding_codes WHERE is_used = TRUE"
            used_result = await db_manager.fetch_one(used_query)
            used_codes = used_result['used'] if used_result else 0
            
            # 有效统计（未使用）
            valid_query = "SELECT COUNT(*) as valid FROM binding_codes WHERE is_used = FALSE"
            valid_result = await db_manager.fetch_one(valid_query)
            valid_codes = valid_result['valid'] if valid_result else 0
            
            # 最近创建统计（24小时内）
            recent_time = current_time - timedelta(hours=24)
            recent_query = """
                SELECT COUNT(*) as recent 
                FROM binding_codes 
                WHERE created_at > ?
            """
            recent_result = await db_manager.fetch_one(recent_query, (recent_time,))
            recent_codes = recent_result['recent'] if recent_result else 0
            
            statistics = {
                'total_codes': total_codes,
                'used_codes': used_codes,
                'valid_codes': valid_codes,
                'recent_codes': recent_codes,
                'usage_rate': (used_codes / total_codes * 100) if total_codes > 0 else 0,
                'generated_at': current_time.isoformat()
            }
            
            logger.debug("绑定码统计生成成功")
            return statistics
            
        except Exception as e:
            logger.error(f"获取绑定码统计失败: {e}")
            raise

    @staticmethod
    async def delete_binding_code(code: str) -> bool:
        """
        删除绑定码
        
        Args:
            code: 要删除的绑定码
            
        Returns:
            删除是否成功
        """
        try:
            code = code.strip().upper()
            logger.info(f"准备删除绑定码: {code}")
            
            # 直接删除绑定码，不检查是否已使用
            delete_query = "DELETE FROM binding_codes WHERE code = ?"
            result = await db_manager.execute_query(delete_query, (code,))
            
            if result > 0:
                logger.info(f"绑定码删除成功: {code}")
                return True
            else:
                logger.warning(f"绑定码不存在: {code}")
                return False
                
        except Exception as e:
            logger.error(f"删除绑定码失败: {e}")
            raise

    @staticmethod
    async def get_code_data(code: str) -> Optional[Dict[str, Any]]:
        """
        获取绑定码基础数据（保持兼容性）
        """
        try:
            query = "SELECT * FROM binding_codes WHERE code = ?"
            result = await db_manager.fetch_one(query, (code,))
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"获取绑定码数据失败: {e}")
            return None

    @staticmethod
    async def validate_and_use_binding_code(code: str, user_id: int) -> Dict[str, Any]:
        """
        一次性验证并使用绑定码（核心绑定流程）
        
        Args:
            code: 绑定码
            user_id: 用户ID
            
        Returns:
            处理结果字典：
            - success: 是否成功
            - merchant_id: 创建的商户ID（如果成功）
            - message: 结果消息
        """
        try:
            # 输入验证
            if not code or len(code.strip()) == 0:
                return {
                    'success': False,
                    'merchant_id': None,
                    'message': '绑定码不能为空'
                }
            
            # 标准化绑定码
            code = code.strip().upper()
            
            # 一次性查询并验证（存在性+使用状态+过期状态）
            query = """
                SELECT id, code, is_used, merchant_id, expires_at
                FROM binding_codes 
                WHERE code = ? AND is_used = FALSE
                AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """
            
            result = await db_manager.fetch_one(query, (code,))
            
            if not result:
                logger.warning(f"绑定码无效、已使用或已过期: {code}")
                return {
                    'success': False,
                    'merchant_id': None,
                    'message': '绑定码无效、已被使用或已过期'
                }
            
            # 检查该TG用户是否已绑定过
            from .db_merchants import MerchantManager
            existing_merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
            if existing_merchant:
                logger.warning(f"用户已绑定商户: user_id={user_id}, merchant_id={existing_merchant['id']}")
                return {
                    'success': False,
                    'merchant_id': None,
                    'message': f'您的账号已绑定到商户ID: {existing_merchant["id"]}'
                }
            
            # 创建空白商户档案
            merchant_data = {
                'telegram_chat_id': user_id,
                'status': 'pending_submission'
            }
            merchant_id = await MerchantManager.create_merchant(merchant_data)
            
            if not merchant_id:
                logger.error(f"创建商户失败: user_id={user_id}, code={code}")
                return {
                    'success': False,
                    'merchant_id': None,
                    'message': '创建商户档案失败，请联系管理员'
                }
            
            # 原子性操作：标记绑定码为已使用
            update_query = """
                UPDATE binding_codes 
                SET is_used = TRUE, merchant_id = ?, used_at = ?
                WHERE code = ? AND is_used = FALSE
            """
            
            update_result = await db_manager.execute_query(update_query, (merchant_id, datetime.now(), code))
            
            if update_result > 0:
                logger.info(f"绑定码使用成功: {code}, 用户ID: {user_id}, 商户ID: {merchant_id}")
                return {
                    'success': True,
                    'merchant_id': merchant_id,
                    'message': f'绑定成功！您的永久商户ID是 {merchant_id}。现在开始填写资料...'
                }
            else:
                # 回滚：删除已创建的商户
                await MerchantManager.delete_merchant(merchant_id)
                logger.error(f"标记绑定码失败，已回滚商户创建: {code}")
                return {
                    'success': False,
                    'merchant_id': None,
                    'message': '绑定码已被其他用户使用，请重试'
                }
                
        except Exception as e:
            logger.error(f"处理绑定码失败: {e}")
            return {
                'success': False,
                'merchant_id': None,
                'message': '系统错误，请稍后重试'
            }

    @staticmethod
    async def use_binding_code(code: str, merchant_id: int) -> bool:
        """
        使用绑定码（标记为已使用并关联商户）
        
        Args:
            code: 绑定码
            merchant_id: 商户ID
            
        Returns:
            使用是否成功
        """
        try:
            # 标准化绑定码
            code = code.strip().upper()
            
            # 更新绑定码状态
            update_query = """
                UPDATE binding_codes 
                SET is_used = TRUE, merchant_id = ?, used_at = ?
                WHERE code = ? AND is_used = FALSE
            """
            
            result = await db_manager.execute_query(update_query, (merchant_id, datetime.now(), code))
            
            if result > 0:
                logger.info(f"绑定码使用成功: {code}, 商户ID: {merchant_id}")
                return True
            else:
                logger.error(f"绑定码使用失败，可能已被其他商户使用: {code}")
                return False
                
        except Exception as e:
            logger.error(f"使用绑定码失败: {e}")
            raise

    @staticmethod
    async def get_merchant_binding_codes(merchant_id: int) -> List[Dict[str, Any]]:
        """
        获取商户使用的所有绑定码
        
        Args:
            merchant_id: 商户ID
            
        Returns:
            绑定码列表
        """
        try:
            query = """
                SELECT * FROM binding_codes 
                WHERE merchant_id = ?
                ORDER BY created_at DESC
            """
            
            results = await db_manager.fetch_all(query, (merchant_id,))
            
            codes = [dict(row) for row in results]
            logger.debug(f"获取商户绑定码成功，商户ID: {merchant_id}, 数量: {len(codes)}")
            return codes
            
        except Exception as e:
            logger.error(f"获取商户绑定码失败，商户ID: {merchant_id}, 错误: {e}")
            raise

    @staticmethod
    async def cleanup_expired_codes() -> int:
        """
        清理过期的绑定码
        
        Returns:
            清理的绑定码数量
        """
        try:
            # 删除已过期且未使用的绑定码
            delete_query = """
                DELETE FROM binding_codes 
                WHERE expires_at < CURRENT_TIMESTAMP AND is_used = FALSE
            """
            
            result = await db_manager.execute_query(delete_query)
            logger.info(f"清理过期绑定码成功，删除数量: {result}")
            return result
            
        except Exception as e:
            logger.error(f"清理过期绑定码失败: {e}")
            raise

    @staticmethod
    async def update_binding_code_merchant(code: str, merchant_id: int) -> bool:
        """
        更新已使用绑定码的商户ID
        
        Args:
            code: 绑定码
            merchant_id: 新的商户ID
            
        Returns:
            更新是否成功
        """
        try:
            code = code.strip().upper()
            
            # 检查绑定码是否存在且已使用
            code_info = await BindingCodesManager.get_binding_code_info(code)
            if not code_info:
                raise ValueError("绑定码不存在")
            
            if not code_info['is_used']:
                raise ValueError("绑定码尚未使用")
            
            # 更新商户ID
            update_query = "UPDATE binding_codes SET merchant_id = ? WHERE code = ?"
            result = await db_manager.execute_query(update_query, (merchant_id, code))
            
            if result > 0:
                logger.info(f"绑定码商户ID更新成功: {code}, 商户ID: {merchant_id}")
                return True
            else:
                logger.error(f"更新绑定码商户ID失败: {code}")
                return False
                
        except ValueError as e:
            logger.error(f"更新绑定码商户ID失败，验证错误: {e}")
            raise
        except Exception as e:
            logger.error(f"更新绑定码商户ID失败: {e}")
            raise

    @staticmethod
    async def extend_binding_code_expiry(code: str, additional_hours: int) -> bool:
        """
        延长绑定码有效期
        
        Args:
            code: 绑定码
            additional_hours: 延长的小时数
            
        Returns:
            延长是否成功
        """
        try:
            code = code.strip().upper()
            
            # 检查绑定码是否存在
            code_info = await BindingCodesManager.get_binding_code_info(code)
            if not code_info:
                logger.error(f"绑定码不存在: {code}")
                return False
            
            # 计算新的过期时间
            current_expiry = code_info.get('expires_at')
            if current_expiry:
                if isinstance(current_expiry, str):
                    current_expiry = datetime.fromisoformat(current_expiry)
                new_expiry = current_expiry + timedelta(hours=additional_hours)
            else:
                # 如果没有过期时间，从当前时间开始计算
                new_expiry = datetime.now() + timedelta(hours=additional_hours)
            
            # 更新过期时间
            update_query = "UPDATE binding_codes SET expires_at = ? WHERE code = ?"
            result = await db_manager.execute_query(update_query, (new_expiry, code))
            
            if result > 0:
                logger.info(f"延长绑定码有效期成功: {code}, 新过期时间: {new_expiry}")
                return True
            else:
                logger.error(f"更新绑定码有效期失败: {code}")
                return False
                
        except Exception as e:
            logger.error(f"延长绑定码有效期失败: {e}")
            raise

    @staticmethod
    async def mark_code_as_used(code: str, merchant_id: int, username: str, full_name: str):
        """
        标记绑定码为已使用（增强版本）
        """
        try:
            query = """
                UPDATE binding_codes 
                SET is_used = TRUE, merchant_id = ?, used_at = ?, 
                    bound_telegram_username = ?, bound_telegram_name = ?
                WHERE code = ?
            """
            params = (merchant_id, datetime.now(), username, full_name, code)
            await db_manager.execute_query(query, params)
            logger.info(f"绑定码标记使用成功: {code}, 商户ID: {merchant_id}")
        except Exception as e:
            logger.error(f"标记绑定码使用失败: {e}")
            raise

# 创建别名以支持V1兼容性
class BindingCodesDatabase(BindingCodesManager):
    """V1兼容性别名"""
    pass

# 实例
binding_codes_manager = BindingCodesManager()
binding_codes_db = binding_codes_manager  # V1兼容性实例
