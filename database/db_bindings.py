"""
绑定码数据库操作模块
提供绑定码生成、验证、清理和商户关联功能
支持安全的随机码生成和过期处理
"""

import logging
import secrets
import string
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from .db_connection import db_manager

# 配置日志
logger = logging.getLogger(__name__)

class BindingCodesDatabase:
    """
    绑定码数据库操作类
    处理所有与绑定码相关的数据库操作
    """
    
    # 绑定码配置
    CODE_LENGTH = 8  # 绑定码长度
    CODE_CHARSET = string.ascii_uppercase + string.digits  # 使用大写字母和数字
    DEFAULT_EXPIRY_HOURS = 24  # 默认过期时间（小时）
    
    @staticmethod
    async def generate_binding_code(expiry_hours: Optional[int] = None) -> str:
        """
        生成新的绑定码
        
        Args:
            expiry_hours: 过期时间（小时），默认为24小时
            
        Returns:
            生成的绑定码字符串
            
        Raises:
            Exception: 生成绑定码失败时
        """
        try:
            if expiry_hours is None:
                expiry_hours = BindingCodesDatabase.DEFAULT_EXPIRY_HOURS
            
            # 计算过期时间
            expires_at = datetime.now() + timedelta(hours=expiry_hours)
            
            # 生成唯一绑定码
            max_attempts = 10
            for attempt in range(max_attempts):
                # 生成随机码
                code = ''.join(
                    secrets.choice(BindingCodesDatabase.CODE_CHARSET) 
                    for _ in range(BindingCodesDatabase.CODE_LENGTH)
                )
                
                # 检查是否已存在
                existing = await BindingCodesDatabase._check_code_exists(code)
                if not existing:
                    # 插入新绑定码，明确设置is_used=0
                    insert_query = """
                        INSERT INTO binding_codes (code, is_used, expires_at)
                        VALUES (?, 0, ?)
                    """
                    
                    await db_manager.execute_query(insert_query, (code, expires_at))
                    
                    logger.info(f"成功生成绑定码: {code}, 过期时间: {expires_at}")
                    return code
            
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
    async def validate_and_use_binding_code(code: str, user_id: int) -> Dict[str, Any]:
        """
        一次性验证并使用绑定码（简化流程）
        
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
                WHERE code = ? AND is_used = 0 AND (expires_at IS NULL OR expires_at > datetime('now'))
            """
            
            result = await db_manager.fetch_one(query, (code,))
            
            if not result:
                logger.warning(f"绑定码无效或已使用: {code}")
                return {
                    'success': False,
                    'merchant_id': None,
                    'message': '绑定码无效、已被使用或已过期'
                }
            
            # 创建空白商户档案
            from .db_merchants import MerchantManager
            merchant_id = await MerchantManager.create_blank_merchant(user_id, code)
            
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
                SET is_used = 1, merchant_id = ?
                WHERE code = ? AND is_used = 0
            """
            
            update_result = await db_manager.execute_query(update_query, (merchant_id, code))
            
            if update_result > 0:
                logger.info(f"绑定码使用成功: {code}, 用户ID: {user_id}, 商户ID: {merchant_id}")
                return {
                    'success': True,
                    'merchant_id': merchant_id,
                    'message': '✅ 注册成功！您的商户档案已创建，管理员将为您完善商户信息。'
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
            
        Raises:
            ValueError: 绑定码无效时
            Exception: 数据库操作失败时
        """
        try:
            # 首先验证绑定码
            validation_result = await BindingCodesDatabase.validate_binding_code(code)
            
            if not validation_result['is_valid']:
                raise ValueError(validation_result['error_message'])
            
            # 标准化绑定码
            code = code.strip().upper()
            
            # 更新绑定码状态
            update_query = """
                UPDATE binding_codes 
                SET is_used = 1, merchant_id = ?
                WHERE code = ? AND is_used = 0
            """
            
            result = await db_manager.execute_query(update_query, (merchant_id, code))
            
            if result > 0:
                logger.info(f"绑定码使用成功: {code}, 商户ID: {merchant_id}")
                return True
            else:
                logger.error(f"绑定码使用失败，可能已被其他商户使用: {code}")
                return False
                
        except ValueError as e:
            logger.error(f"绑定码使用失败，验证错误: {e}")
            raise
        except Exception as e:
            logger.error(f"使用绑定码失败: {e}")
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
                SELECT bc.*, m.name as merchant_name, m.chat_id as merchant_chat_id
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
            current_time = datetime.now()
            
            # 删除过期且未使用的绑定码
            delete_query = """
                DELETE FROM binding_codes 
                WHERE expires_at < ? AND is_used = 0
            """
            
            result = await db_manager.execute_query(delete_query, (current_time,))
            
            if result > 0:
                logger.info(f"清理过期绑定码成功，数量: {result}")
            else:
                logger.debug("没有过期的绑定码需要清理")
            
            return result
            
        except Exception as e:
            logger.error(f"清理过期绑定码失败: {e}")
            raise
    
    @staticmethod
    async def get_all_binding_codes(
        include_used: bool = True,
        include_expired: bool = False,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取所有绑定码列表
        
        Args:
            include_used: 是否包含已使用的绑定码
            include_expired: 是否包含已过期的绑定码
            limit: 返回数量限制
            
        Returns:
            绑定码列表
        """
        try:
            query = """
                SELECT bc.*, m.name as merchant_name, m.chat_id as merchant_chat_id
                FROM binding_codes bc
                LEFT JOIN merchants m ON bc.merchant_id = m.id
                WHERE 1=1
            """
            params = []
            
            # 添加过滤条件
            if not include_used:
                query += " AND bc.is_used = 0"
            
            if not include_expired:
                query += " AND (bc.expires_at IS NULL OR bc.expires_at > ?)"
                params.append(datetime.now())
            
            query += " ORDER BY bc.created_at DESC"
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            results = await db_manager.fetch_all(query, tuple(params))
            
            codes = [dict(row) for row in results]
            logger.debug(f"获取绑定码列表成功，数量: {len(codes)}")
            return codes
            
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
            used_query = "SELECT COUNT(*) as used FROM binding_codes WHERE is_used = 1"
            used_result = await db_manager.fetch_one(used_query)
            used_codes = used_result['used'] if used_result else 0
            
            # 过期统计
            expired_query = """
                SELECT COUNT(*) as expired 
                FROM binding_codes 
                WHERE expires_at < ? AND is_used = 0
            """
            expired_result = await db_manager.fetch_one(expired_query, (current_time,))
            expired_codes = expired_result['expired'] if expired_result else 0
            
            # 有效统计
            valid_query = """
                SELECT COUNT(*) as valid 
                FROM binding_codes 
                WHERE is_used = 0 AND (expires_at IS NULL OR expires_at > ?)
            """
            valid_result = await db_manager.fetch_one(valid_query, (current_time,))
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
                'expired_codes': expired_codes,
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
            code_info = await BindingCodesDatabase.get_binding_code_info(code)
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
            
            # 获取当前绑定码信息
            code_info = await BindingCodesDatabase.get_binding_code_info(code)
            if not code_info:
                raise ValueError("绑定码不存在")
            
            if code_info['is_used']:
                raise ValueError("已使用的绑定码不能延长有效期")
            
            # 计算新的过期时间
            current_expiry = datetime.fromisoformat(code_info['expires_at']) if code_info['expires_at'] else datetime.now()
            new_expiry = max(current_expiry, datetime.now()) + timedelta(hours=additional_hours)
            
            # 更新过期时间
            update_query = "UPDATE binding_codes SET expires_at = ? WHERE code = ?"
            result = await db_manager.execute_query(update_query, (new_expiry, code))
            
            if result > 0:
                logger.info(f"绑定码有效期延长成功: {code}, 新过期时间: {new_expiry}")
                return True
            else:
                logger.error(f"延长绑定码有效期失败: {code}")
                return False
                
        except ValueError as e:
            logger.error(f"延长绑定码有效期失败，验证错误: {e}")
            raise
        except Exception as e:
            logger.error(f"延长绑定码有效期失败: {e}")
            raise

# 创建全局实例
binding_codes_db = BindingCodesDatabase()