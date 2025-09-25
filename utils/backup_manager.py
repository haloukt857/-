"""
数据库备份管理器
提供自动备份、恢复和数据完整性验证功能
"""

import os
import sys
import shutil
import gzip
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import sqlite3

from database.db_connection import db_manager
from path_manager import PathManager

logger = logging.getLogger(__name__)


class BackupManager:
    """数据库备份管理器"""
    
    def __init__(
        self,
        backup_dir: Optional[str] = None,
        max_backups: int = 10,
        compression: bool = True
    ):
        """
        初始化备份管理器
        
        Args:
            backup_dir: 备份目录，默认为data/backups
            max_backups: 最大备份文件数量
            compression: 是否压缩备份文件
        """
        self.backup_dir = Path(backup_dir or PathManager.get_data_path("backups"))
        self.max_backups = max_backups
        self.compression = compression
        
        # 确保备份目录存在
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"备份管理器初始化 - 目录: {self.backup_dir}, 最大备份数: {max_backups}")
    
    async def create_backup(
        self, 
        backup_name: Optional[str] = None,
        include_logs: bool = True,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        创建数据库备份
        
        Args:
            backup_name: 备份名称，默认使用时间戳
            include_logs: 是否包含日志数据
            include_metadata: 是否包含元数据
            
        Returns:
            备份信息字典
        """
        try:
            if not backup_name:
                backup_name = datetime.now().strftime("backup_%Y%m%d_%H%M%S")
            
            backup_info = {
                "name": backup_name,
                "timestamp": datetime.now().isoformat(),
                "version": "1.0",
                "compression": self.compression,
                "include_logs": include_logs,
                "include_metadata": include_metadata
            }
            
            logger.info(f"开始创建备份: {backup_name}")
            
            # 创建临时备份目录
            temp_backup_dir = self.backup_dir / f"temp_{backup_name}"
            temp_backup_dir.mkdir(exist_ok=True)
            
            try:
                # 1. 备份主数据库
                db_backup_path = await self._backup_database(temp_backup_dir)
                backup_info["database_file"] = db_backup_path.name
                backup_info["database_size"] = db_backup_path.stat().st_size
                
                # 2. 备份配置文件
                config_backup_path = await self._backup_config(temp_backup_dir)
                backup_info["config_file"] = config_backup_path.name
                
                # 3. 生成数据完整性校验
                checksums = await self._generate_checksums(temp_backup_dir)
                backup_info["checksums"] = checksums
                
                # 4. 备份元数据
                if include_metadata:
                    metadata_path = await self._backup_metadata(temp_backup_dir, backup_info)
                    backup_info["metadata_file"] = metadata_path.name
                
                # 5. 创建最终备份文件
                final_backup_path = await self._create_final_backup(
                    temp_backup_dir, 
                    backup_name, 
                    backup_info
                )
                
                backup_info["backup_file"] = final_backup_path.name
                backup_info["backup_size"] = final_backup_path.stat().st_size
                backup_info["status"] = "success"
                
                # 6. 清理旧备份
                await self._cleanup_old_backups()
                
                logger.info(f"备份创建成功: {final_backup_path}")
                return backup_info
                
            finally:
                # 清理临时目录
                if temp_backup_dir.exists():
                    shutil.rmtree(temp_backup_dir)
        
        except Exception as e:
            logger.error(f"备份创建失败: {e}")
            backup_info = backup_info if 'backup_info' in locals() else {}
            backup_info.update({
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            return backup_info
    
    async def _backup_database(self, backup_dir: Path) -> Path:
        """备份数据库文件"""
        try:
            db_path = PathManager.get_db_path()
            backup_db_path = backup_dir / "database.db"
            
            # 使用SQLite的VACUUM INTO命令创建干净的备份
            async with db_manager.get_connection() as conn:
                await conn.execute(f"VACUUM INTO '{backup_db_path}'")
            
            logger.info(f"数据库备份完成: {backup_db_path}")
            return backup_db_path
            
        except Exception as e:
            logger.error(f"数据库备份失败: {e}")
            # 备用方法：直接复制文件
            db_path = PathManager.get_db_path()
            backup_db_path = backup_dir / "database.db"
            shutil.copy2(db_path, backup_db_path)
            return backup_db_path
    
    async def _backup_config(self, backup_dir: Path) -> Path:
        """备份配置信息"""
        config_data = {
            "timestamp": datetime.now().isoformat(),
            "message_templates": {},
            "button_templates": {},
            "system_settings": {}
        }
        
        try:
            # 备份消息模板
            from config import MESSAGE_TEMPLATES, BUTTON_TEMPLATES
            config_data["message_templates"] = MESSAGE_TEMPLATES
            config_data["button_templates"] = BUTTON_TEMPLATES
            
            # 备份系统设置
            config_data["system_settings"] = {
                "use_webhook": os.getenv("USE_WEBHOOK", "true"),
                "log_level": os.getenv("LOG_LEVEL", "INFO"),
                "rate_limits": {
                    "default": os.getenv("RATE_LIMIT_DEFAULT", "10"),
                    "admin": os.getenv("RATE_LIMIT_ADMIN", "100")
                }
            }
            
        except Exception as e:
            logger.warning(f"配置备份部分失败: {e}")
        
        config_backup_path = backup_dir / "config.json"
        with open(config_backup_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"配置备份完成: {config_backup_path}")
        return config_backup_path
    
    async def _generate_checksums(self, backup_dir: Path) -> Dict[str, str]:
        """生成文件校验和"""
        checksums = {}
        
        for file_path in backup_dir.glob("*"):
            if file_path.is_file():
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                    checksums[file_path.name] = file_hash
        
        return checksums
    
    async def _backup_metadata(self, backup_dir: Path, backup_info: Dict[str, Any]) -> Path:
        """备份元数据和统计信息"""
        metadata = {
            "backup_info": backup_info,
            "database_stats": await self._get_database_stats(),
            "system_info": {
                "python_version": sys.version,
                "timestamp": datetime.now().isoformat(),
                "hostname": os.uname().nodename if hasattr(os, 'uname') else 'unknown'
            }
        }
        
        metadata_path = backup_dir / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        return metadata_path
    
    async def _get_database_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        try:
            stats = {}
            
            # 获取各表的行数
            tables = ['merchants', 'orders', 'binding_codes', 'activity_logs', 'fsm_states']
            
            for table in tables:
                try:
                    count = await db_manager.fetch_one(f"SELECT COUNT(*) FROM {table}")
                    stats[f"{table}_count"] = count[0] if count else 0
                except Exception:
                    stats[f"{table}_count"] = 0
            
            # 获取数据库大小
            db_path = PathManager.get_db_path()
            if os.path.exists(db_path):
                stats["database_size_bytes"] = os.path.getsize(db_path)
            
            return stats
            
        except Exception as e:
            logger.warning(f"获取数据库统计信息失败: {e}")
            return {}
    
    async def _create_final_backup(
        self, 
        temp_dir: Path, 
        backup_name: str, 
        backup_info: Dict[str, Any]
    ) -> Path:
        """创建最终备份文件"""
        
        # 写入备份信息文件
        backup_info_path = temp_dir / "backup_info.json"
        with open(backup_info_path, 'w', encoding='utf-8') as f:
            json.dump(backup_info, f, indent=2, ensure_ascii=False)
        
        if self.compression:
            # 创建压缩备份
            backup_file = self.backup_dir / f"{backup_name}.tar.gz"
            
            import tarfile
            with tarfile.open(backup_file, 'w:gz') as tar:
                for file_path in temp_dir.glob("*"):
                    if file_path.is_file():
                        tar.add(file_path, arcname=file_path.name)
        else:
            # 创建目录备份
            backup_file = self.backup_dir / backup_name
            shutil.copytree(temp_dir, backup_file)
        
        return backup_file
    
    async def _cleanup_old_backups(self):
        """清理旧备份文件"""
        try:
            # 获取所有备份文件
            if self.compression:
                backup_files = list(self.backup_dir.glob("backup_*.tar.gz"))
            else:
                backup_files = [d for d in self.backup_dir.iterdir() 
                              if d.is_dir() and d.name.startswith("backup_")]
            
            # 按修改时间排序
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # 删除超出数量限制的备份
            if len(backup_files) > self.max_backups:
                for old_backup in backup_files[self.max_backups:]:
                    if old_backup.is_dir():
                        shutil.rmtree(old_backup)
                    else:
                        old_backup.unlink()
                    logger.info(f"删除旧备份: {old_backup}")
        
        except Exception as e:
            logger.warning(f"清理旧备份失败: {e}")
    
    async def list_backups(self) -> List[Dict[str, Any]]:
        """列出所有备份"""
        backups = []
        
        try:
            if self.compression:
                backup_files = list(self.backup_dir.glob("backup_*.tar.gz"))
            else:
                backup_files = [d for d in self.backup_dir.iterdir() 
                              if d.is_dir() and d.name.startswith("backup_")]
            
            for backup_path in sorted(backup_files, key=lambda x: x.stat().st_mtime, reverse=True):
                backup_info = {
                    "name": backup_path.name,
                    "path": str(backup_path),
                    "size": backup_path.stat().st_size if backup_path.is_file() else self._get_dir_size(backup_path),
                    "created": datetime.fromtimestamp(backup_path.stat().st_mtime).isoformat(),
                    "type": "compressed" if self.compression else "directory"
                }
                
                # 尝试读取备份信息
                try:
                    if self.compression:
                        import tarfile
                        with tarfile.open(backup_path, 'r:gz') as tar:
                            info_member = tar.getmember("backup_info.json")
                            info_data = json.loads(tar.extractfile(info_member).read().decode('utf-8'))
                            backup_info.update(info_data)
                    else:
                        info_file = backup_path / "backup_info.json"
                        if info_file.exists():
                            with open(info_file, 'r', encoding='utf-8') as f:
                                info_data = json.load(f)
                                backup_info.update(info_data)
                except Exception as e:
                    logger.warning(f"读取备份信息失败 {backup_path}: {e}")
                
                backups.append(backup_info)
        
        except Exception as e:
            logger.error(f"列出备份失败: {e}")
        
        return backups
    
    def _get_dir_size(self, path: Path) -> int:
        """获取目录大小"""
        total_size = 0
        try:
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except Exception:
            pass
        return total_size
    
    async def restore_backup(self, backup_name: str, verify_integrity: bool = True) -> Dict[str, Any]:
        """
        恢复备份
        
        Args:
            backup_name: 备份名称
            verify_integrity: 是否验证完整性
            
        Returns:
            恢复结果信息
        """
        try:
            logger.info(f"开始恢复备份: {backup_name}")
            
            # 查找备份文件
            if self.compression:
                backup_path = self.backup_dir / f"{backup_name}.tar.gz"
                if not backup_path.exists():
                    backup_path = self.backup_dir / backup_name
            else:
                backup_path = self.backup_dir / backup_name
            
            if not backup_path.exists():
                raise FileNotFoundError(f"备份文件不存在: {backup_name}")
            
            # 创建临时恢复目录
            temp_restore_dir = self.backup_dir / f"restore_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            temp_restore_dir.mkdir(exist_ok=True)
            
            try:
                # 解压备份文件
                if self.compression and backup_path.suffix == '.gz':
                    import tarfile
                    with tarfile.open(backup_path, 'r:gz') as tar:
                        tar.extractall(temp_restore_dir)
                else:
                    for item in backup_path.iterdir():
                        if item.is_file():
                            shutil.copy2(item, temp_restore_dir)
                        elif item.is_dir():
                            shutil.copytree(item, temp_restore_dir / item.name)
                
                # 验证完整性
                if verify_integrity:
                    if not await self._verify_backup_integrity(temp_restore_dir):
                        raise ValueError("备份完整性验证失败")
                
                # 执行恢复
                await self._perform_restore(temp_restore_dir)
                
                logger.info(f"备份恢复成功: {backup_name}")
                return {
                    "status": "success",
                    "backup_name": backup_name,
                    "restored_at": datetime.now().isoformat(),
                    "message": "备份恢复成功"
                }
            
            finally:
                # 清理临时目录
                if temp_restore_dir.exists():
                    shutil.rmtree(temp_restore_dir)
        
        except Exception as e:
            logger.error(f"备份恢复失败: {e}")
            return {
                "status": "failed",
                "backup_name": backup_name,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _verify_backup_integrity(self, restore_dir: Path) -> bool:
        """验证备份完整性"""
        try:
            # 检查必需文件
            required_files = ["database.db", "config.json", "backup_info.json"]
            for file_name in required_files:
                if not (restore_dir / file_name).exists():
                    logger.error(f"备份完整性验证失败：缺少文件 {file_name}")
                    return False
            
            # 验证校验和（如果存在）
            backup_info_path = restore_dir / "backup_info.json"
            if backup_info_path.exists():
                with open(backup_info_path, 'r', encoding='utf-8') as f:
                    backup_info = json.load(f)
                
                checksums = backup_info.get("checksums", {})
                if checksums:
                    for file_name, expected_hash in checksums.items():
                        file_path = restore_dir / file_name
                        if file_path.exists():
                            with open(file_path, 'rb') as f:
                                actual_hash = hashlib.sha256(f.read()).hexdigest()
                                if actual_hash != expected_hash:
                                    logger.error(f"文件校验和不匹配: {file_name}")
                                    return False
            
            # 验证数据库文件
            db_path = restore_dir / "database.db"
            if db_path.exists():
                # 尝试打开数据库检查完整性
                conn = sqlite3.connect(db_path)
                try:
                    cursor = conn.execute("PRAGMA integrity_check")
                    result = cursor.fetchone()
                    if result[0] != "ok":
                        logger.error(f"数据库完整性检查失败: {result[0]}")
                        return False
                finally:
                    conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"备份完整性验证异常: {e}")
            return False
    
    async def _perform_restore(self, restore_dir: Path):
        """执行恢复操作"""
        try:
            # 关闭数据库连接
            await db_manager.close()
            
            # 备份当前数据库
            current_db_path = PathManager.get_db_path()
            backup_current_path = f"{current_db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            if os.path.exists(current_db_path):
                shutil.copy2(current_db_path, backup_current_path)
                logger.info(f"当前数据库已备份至: {backup_current_path}")
            
            # 恢复数据库
            restore_db_path = restore_dir / "database.db"
            if restore_db_path.exists():
                shutil.copy2(restore_db_path, current_db_path)
                logger.info("数据库恢复完成")
            
            # 重新初始化数据库连接
            await db_manager.initialize()
            
        except Exception as e:
            logger.error(f"执行恢复失败: {e}")
            raise
    
    async def create_scheduled_backup(self) -> Dict[str, Any]:
        """创建定时备份"""
        backup_name = f"scheduled_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return await self.create_backup(
            backup_name=backup_name,
            include_logs=True,
            include_metadata=True
        )
    
    async def get_backup_statistics(self) -> Dict[str, Any]:
        """获取备份统计信息"""
        try:
            backups = await self.list_backups()
            
            total_size = sum(backup.get("size", 0) for backup in backups)
            
            return {
                "total_backups": len(backups),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "oldest_backup": backups[-1]["created"] if backups else None,
                "newest_backup": backups[0]["created"] if backups else None,
                "backup_directory": str(self.backup_dir),
                "max_backups": self.max_backups,
                "compression_enabled": self.compression
            }
            
        except Exception as e:
            logger.error(f"获取备份统计失败: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# 全局备份管理器实例
backup_manager = BackupManager()