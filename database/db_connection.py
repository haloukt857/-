"""
数据库连接管理器
提供线程安全的SQLite异步连接管理，包括连接池、查询执行和错误处理
"""

import aiosqlite
import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from contextlib import asynccontextmanager
import os
from pathlib import Path

# 导入路径管理器
from pathmanager import PathManager

# 配置日志
logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    数据库连接管理器类
    提供异步SQLite连接管理、查询执行和错误处理功能
    """
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        """单例模式确保只有一个数据库管理器实例"""
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化数据库管理器"""
        if not hasattr(self, 'initialized'):
            self.db_path = PathManager.get_database_path()
            self.connection_pool = []
            self.max_connections = 10
            self.initialized = True
            logger.info(f"数据库管理器初始化完成，数据库路径: {self.db_path}")

    async def close_all_connections(self):
        """关闭连接池中的所有连接，清空连接池（用于重置数据库场景）。"""
        try:
            async with self._lock:
                while self.connection_pool:
                    conn = self.connection_pool.pop()
                    try:
                        await conn.close()
                    except Exception:
                        pass
            logger.info("数据库连接池已清空")
        except Exception as e:
            logger.warning(f"清空连接池时出错: {e}")

    def set_db_path(self, new_path: str):
        """更新数据库文件路径（在重置数据库后调用）。"""
        self.db_path = new_path
        logger.info(f"数据库路径已更新为: {self.db_path}")
    
    async def _create_connection(self) -> aiosqlite.Connection:
        """
        创建新的数据库连接
        返回配置好的aiosqlite连接对象
        """
        try:
            # 确保数据库目录存在
            PathManager.ensure_parent_directory(self.db_path)
            
            # 创建连接并配置
            conn = await aiosqlite.connect(
                self.db_path,
                timeout=30.0,
                isolation_level=None  # 启用自动提交模式
            )
            
            # 设置行工厂以支持字典访问
            conn.row_factory = aiosqlite.Row
            
            # 配置SQLite参数以提高性能和并发性
            await conn.execute("PRAGMA journal_mode=WAL")  # 启用WAL模式提高并发性
            await conn.execute("PRAGMA synchronous=NORMAL")  # 平衡性能和安全性
            await conn.execute("PRAGMA cache_size=10000")  # 增加缓存大小
            await conn.execute("PRAGMA temp_store=MEMORY")  # 临时表存储在内存中
            await conn.execute("PRAGMA foreign_keys=ON")  # 启用外键约束
            
            logger.debug("创建新的数据库连接成功")
            return conn
            
        except Exception as e:
            logger.error(f"创建数据库连接失败: {e}")
            raise
    
    @asynccontextmanager
    async def get_connection(self):
        """
        获取数据库连接的异步上下文管理器
        自动处理连接的获取和释放
        """
        conn = None
        try:
            async with self._lock:
                # 尝试从连接池获取连接
                if self.connection_pool:
                    conn = self.connection_pool.pop()
                    logger.debug("从连接池获取连接")
                else:
                    conn = await self._create_connection()
                    logger.debug("创建新连接")
            
            yield conn
            
        except Exception as e:
            logger.error(f"数据库连接操作失败: {e}")
            if conn:
                await conn.close()
                conn = None
            raise
        finally:
            # 将连接返回到连接池
            if conn:
                async with self._lock:
                    if len(self.connection_pool) < self.max_connections:
                        self.connection_pool.append(conn)
                        logger.debug("连接返回到连接池")
                    else:
                        await conn.close()
                        logger.debug("连接池已满，关闭连接")
    
    async def execute_query(
        self, 
        query: str, 
        params: Optional[Union[Tuple, Dict]] = None,
        fetch_result: bool = False
    ) -> Optional[Union[List[aiosqlite.Row], aiosqlite.Row, int]]:
        """
        执行SQL查询
        
        Args:
            query: SQL查询语句
            params: 查询参数
            fetch_result: 是否获取查询结果
            
        Returns:
            查询结果或受影响的行数
        """
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                async with self.get_connection() as conn:
                    if params:
                        cursor = await conn.execute(query, params)
                    else:
                        cursor = await conn.execute(query)
                    
                    if fetch_result:
                        if query.strip().upper().startswith('SELECT'):
                            # 对于SELECT查询，返回所有结果
                            result = await cursor.fetchall()
                            logger.debug(f"查询执行成功，返回 {len(result)} 行数据")
                            return result
                        else:
                            # 对于其他查询，返回受影响的行数
                            await conn.commit()
                            result = cursor.rowcount
                            logger.debug(f"查询执行成功，影响 {result} 行")
                            return result
                    else:
                        await conn.commit()
                        result = cursor.rowcount
                        logger.debug(f"查询执行成功，影响 {result} 行")
                        return result
                        
            except aiosqlite.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    logger.warning(f"数据库锁定，第 {attempt + 1} 次重试...")
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    logger.error(f"数据库操作错误: {e}")
                    raise
            except Exception as e:
                logger.error(f"执行查询失败: {e}, SQL: {query}")
                raise
        
        raise Exception(f"查询执行失败，已重试 {max_retries} 次")
    
    async def fetch_one(
        self, 
        query: str, 
        params: Optional[Union[Tuple, Dict]] = None
    ) -> Optional[aiosqlite.Row]:
        """
        获取单行查询结果
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            单行查询结果或None
        """
        try:
            async with self.get_connection() as conn:
                if params:
                    cursor = await conn.execute(query, params)
                else:
                    cursor = await conn.execute(query)
                
                result = await cursor.fetchone()
                logger.debug(f"单行查询执行成功: {query[:50]}...")
                return result
                
        except Exception as e:
            logger.error(f"单行查询失败: {e}, SQL: {query}")
            raise
    
    async def fetch_all(
        self, 
        query: str, 
        params: Optional[Union[Tuple, Dict]] = None
    ) -> List[aiosqlite.Row]:
        """
        获取所有查询结果
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            查询结果列表
        """
        try:
            async with self.get_connection() as conn:
                if params:
                    cursor = await conn.execute(query, params)
                else:
                    cursor = await conn.execute(query)
                
                result = await cursor.fetchall()
                logger.debug(f"多行查询执行成功，返回 {len(result)} 行: {query[:50]}...")
                return result
                
        except Exception as e:
            logger.error(f"多行查询失败: {e}, SQL: {query}")
            raise
    
    async def execute_transaction(self, queries: List[Tuple[str, Optional[Union[Tuple, Dict]]]]) -> bool:
        """
        执行事务操作
        
        Args:
            queries: 查询列表，每个元素为(query, params)元组
            
        Returns:
            事务是否成功执行
        """
        try:
            async with self.get_connection() as conn:
                # 开始事务
                await conn.execute("BEGIN TRANSACTION")
                
                try:
                    for query, params in queries:
                        if params:
                            await conn.execute(query, params)
                        else:
                            await conn.execute(query)
                    
                    # 提交事务
                    await conn.commit()
                    logger.info(f"事务执行成功，包含 {len(queries)} 个查询")
                    return True
                    
                except Exception as e:
                    # 回滚事务
                    await conn.rollback()
                    logger.error(f"事务执行失败，已回滚: {e}")
                    raise
                    
        except Exception as e:
            logger.error(f"事务操作失败: {e}")
            return False
    
    async def get_last_insert_id(self, query: str, params: Optional[Union[Tuple, Dict]] = None) -> int:
        """
        执行插入操作并返回最后插入的ID
        
        Args:
            query: INSERT SQL语句
            params: 查询参数
            
        Returns:
            最后插入的行ID
        """
        try:
            async with self.get_connection() as conn:
                if params:
                    cursor = await conn.execute(query, params)
                else:
                    cursor = await conn.execute(query)
                
                await conn.commit()
                last_id = cursor.lastrowid
                logger.debug(f"插入操作成功，返回ID: {last_id}")
                return last_id
                
        except Exception as e:
            logger.error(f"插入操作失败: {e}, SQL: {query}")
            raise
    
    async def close_all_connections(self):
        """关闭所有连接池中的连接"""
        async with self._lock:
            for conn in self.connection_pool:
                try:
                    await conn.close()
                except Exception as e:
                    logger.error(f"关闭连接失败: {e}")
            
            self.connection_pool.clear()
            logger.info("所有数据库连接已关闭")
    
    async def health_check(self) -> bool:
        """
        数据库健康检查
        
        Returns:
            数据库是否正常工作
        """
        try:
            result = await self.fetch_one("SELECT 1 as health_check")
            return result is not None and result[0] == 1
        except Exception as e:
            logger.error(f"数据库健康检查失败: {e}")
            return False

# 创建全局数据库管理器实例
db_manager = DatabaseManager()
