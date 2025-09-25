# -*- coding: utf-8 -*-
"""
缓存服务
提供应用层的缓存机制，优化性能和用户体验
"""

import time
import logging
from typing import Dict, Any, Optional, Callable
import os

logger = logging.getLogger(__name__)


class CacheService:
    """缓存服务类"""
    
    # 缓存存储 (内存缓存)
    _cache_store: Dict[str, Dict[str, Any]] = {}
    
    # 默认缓存配置
    DEFAULT_TTL = int(os.getenv("CACHE_TTL", "300"))  # 默认5分钟
    DASHBOARD_CACHE_TTL = int(os.getenv("DASHBOARD_CACHE_TTL", "5"))  # 仪表板缓存5秒
    
    @staticmethod
    def _get_cache_key(namespace: str, key: str) -> str:
        """生成缓存键"""
        return f"{namespace}:{key}"
    
    @staticmethod
    def set(namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        设置缓存值
        
        Args:
            namespace: 命名空间
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None使用默认值
            
        Returns:
            bool: 设置是否成功
        """
        try:
            if ttl is None:
                ttl = CacheService.DEFAULT_TTL
                
            cache_key = CacheService._get_cache_key(namespace, key)
            expire_time = time.time() + ttl if ttl > 0 else 0
            
            CacheService._cache_store[cache_key] = {
                'value': value,
                'expire_time': expire_time,
                'created_time': time.time()
            }
            
            logger.debug(f"缓存设置成功: {cache_key}, TTL: {ttl}秒")
            return True
            
        except Exception as e:
            logger.error(f"设置缓存失败: namespace={namespace}, key={key}, error={e}")
            return False
    
    @staticmethod
    def get(namespace: str, key: str, default: Any = None) -> Any:
        """
        获取缓存值
        
        Args:
            namespace: 命名空间
            key: 缓存键
            default: 默认值
            
        Returns:
            Any: 缓存值或默认值
        """
        try:
            cache_key = CacheService._get_cache_key(namespace, key)
            cache_entry = CacheService._cache_store.get(cache_key)
            
            if not cache_entry:
                return default
            
            # 检查是否过期
            if cache_entry['expire_time'] > 0 and time.time() > cache_entry['expire_time']:
                # 删除过期缓存
                del CacheService._cache_store[cache_key]
                logger.debug(f"缓存已过期并删除: {cache_key}")
                return default
            
            logger.debug(f"缓存命中: {cache_key}")
            return cache_entry['value']
            
        except Exception as e:
            logger.error(f"获取缓存失败: namespace={namespace}, key={key}, error={e}")
            return default
    
    @staticmethod
    def delete(namespace: str, key: str) -> bool:
        """
        删除缓存
        
        Args:
            namespace: 命名空间
            key: 缓存键
            
        Returns:
            bool: 删除是否成功
        """
        try:
            cache_key = CacheService._get_cache_key(namespace, key)
            if cache_key in CacheService._cache_store:
                del CacheService._cache_store[cache_key]
                logger.debug(f"缓存删除成功: {cache_key}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"删除缓存失败: namespace={namespace}, key={key}, error={e}")
            return False
    
    @staticmethod
    def clear_namespace(namespace: str) -> int:
        """
        清空命名空间下的所有缓存
        
        Args:
            namespace: 命名空间
            
        Returns:
            int: 删除的缓存数量
        """
        try:
            prefix = f"{namespace}:"
            keys_to_delete = [key for key in CacheService._cache_store.keys() if key.startswith(prefix)]
            
            for key in keys_to_delete:
                del CacheService._cache_store[key]
            
            logger.info(f"清空命名空间缓存: {namespace}, 删除数量: {len(keys_to_delete)}")
            return len(keys_to_delete)
            
        except Exception as e:
            logger.error(f"清空命名空间缓存失败: namespace={namespace}, error={e}")
            return 0
    
    @staticmethod
    def exists(namespace: str, key: str) -> bool:
        """
        检查缓存是否存在且未过期
        
        Args:
            namespace: 命名空间
            key: 缓存键
            
        Returns:
            bool: 缓存是否存在
        """
        try:
            cache_key = CacheService._get_cache_key(namespace, key)
            cache_entry = CacheService._cache_store.get(cache_key)
            
            if not cache_entry:
                return False
            
            # 检查是否过期
            if cache_entry['expire_time'] > 0 and time.time() > cache_entry['expire_time']:
                # 删除过期缓存
                del CacheService._cache_store[cache_key]
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"检查缓存存在性失败: namespace={namespace}, key={key}, error={e}")
            return False
    
    @staticmethod
    async def get_or_set(namespace: str, key: str, fetch_func: Callable, ttl: Optional[int] = None) -> Any:
        """
        获取缓存或设置缓存（缓存穿透保护）
        
        Args:
            namespace: 命名空间
            key: 缓存键
            fetch_func: 获取数据的函数（可以是同步或异步）
            ttl: 过期时间（秒）
            
        Returns:
            Any: 缓存值或新获取的值
        """
        try:
            # 先尝试从缓存获取
            cached_value = CacheService.get(namespace, key, None)
            if cached_value is not None:
                return cached_value
            
            # 缓存未命中，调用函数获取数据
            if hasattr(fetch_func, '__call__'):
                if hasattr(fetch_func, '__await__'):
                    # 异步函数
                    value = await fetch_func()
                else:
                    # 同步函数
                    value = fetch_func()
            else:
                value = fetch_func
            
            # 设置缓存
            CacheService.set(namespace, key, value, ttl)
            return value
            
        except Exception as e:
            logger.error(f"获取或设置缓存失败: namespace={namespace}, key={key}, error={e}")
            # 如果缓存失败，尝试直接调用获取函数
            try:
                if hasattr(fetch_func, '__call__'):
                    if hasattr(fetch_func, '__await__'):
                        return await fetch_func()
                    else:
                        return fetch_func()
                return fetch_func
            except Exception as fetch_error:
                logger.error(f"获取数据函数执行失败: {fetch_error}")
                return None
    
    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            dict: 缓存统计信息
        """
        try:
            current_time = time.time()
            total_entries = len(CacheService._cache_store)
            expired_entries = 0
            namespaces = {}
            
            for cache_key, cache_entry in CacheService._cache_store.items():
                # 统计过期项
                if cache_entry['expire_time'] > 0 and current_time > cache_entry['expire_time']:
                    expired_entries += 1
                
                # 统计命名空间
                namespace = cache_key.split(':', 1)[0]
                namespaces[namespace] = namespaces.get(namespace, 0) + 1
            
            return {
                'total_entries': total_entries,
                'expired_entries': expired_entries,
                'active_entries': total_entries - expired_entries,
                'namespaces': namespaces,
                'cache_size_mb': len(str(CacheService._cache_store)) / (1024 * 1024)
            }
            
        except Exception as e:
            logger.error(f"获取缓存统计信息失败: {e}")
            return {
                'total_entries': 0,
                'expired_entries': 0,
                'active_entries': 0,
                'namespaces': {},
                'cache_size_mb': 0,
                'error': str(e)
            }
    
    @staticmethod
    def cleanup_expired() -> int:
        """
        清理过期缓存
        
        Returns:
            int: 清理的缓存数量
        """
        try:
            current_time = time.time()
            expired_keys = []
            
            for cache_key, cache_entry in CacheService._cache_store.items():
                if cache_entry['expire_time'] > 0 and current_time > cache_entry['expire_time']:
                    expired_keys.append(cache_key)
            
            for key in expired_keys:
                del CacheService._cache_store[key]
            
            if expired_keys:
                logger.info(f"清理过期缓存: {len(expired_keys)}条")
            
            return len(expired_keys)
            
        except Exception as e:
            logger.error(f"清理过期缓存失败: {e}")
            return 0