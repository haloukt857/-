# -*- coding: utf-8 -*-
"""
集中化路径管理系统 (PathManager)
统一管理项目中所有文件和目录路径，支持开发/生产环境自动切换。

用法示例:
    from pathmanager import PathManager
    
    # 获取数据库路径
    db_path = PathManager.get_database_path()
    
    # 获取日志目录
    log_dir = PathManager.get_logs_directory()
    
    # 获取静态文件路径
    static_path = PathManager.get_static_file_path("css/style.css")
"""

import os
import logging
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger(__name__)


class PathManager:
    """
    集中化路径管理器
    使用静态方法模式提供项目所有路径的统一管理
    """
    
    # 项目根目录 - 自动检测
    _ROOT_DIR = Path(__file__).parent.absolute()
    
    # 环境检测
    _IS_PRODUCTION = os.getenv("NODE_ENV") == "production"
    _IS_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT"))
    
    @classmethod
    def _ensure_directory(cls, path: Union[str, Path]) -> Path:
        """
        确保目录存在，如不存在则创建
        
        Args:
            path: 目录路径
            
        Returns:
            Path对象
        """
        directory = Path(path)
        try:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"目录确保存在: {directory}")
        except Exception as e:
            logger.error(f"创建目录失败 {directory}: {e}")
            raise
        return directory
    
    @classmethod
    def _ensure_parent_directory(cls, file_path: Union[str, Path]) -> Path:
        """
        确保文件的父目录存在
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件路径的Path对象
        """
        file_path = Path(file_path)
        cls._ensure_directory(file_path.parent)
        return file_path
    
    # ============================================================================
    # 根目录和环境信息
    # ============================================================================
    
    @classmethod
    def get_root_directory(cls) -> str:
        """获取项目根目录的绝对路径"""
        return str(cls._ROOT_DIR)
    
    @classmethod
    def get_environment_info(cls) -> dict:
        """
        获取当前环境信息
        
        Returns:
            包含环境信息的字典
        """
        return {
            "is_production": cls._IS_PRODUCTION,
            "is_railway": cls._IS_RAILWAY,
            "node_env": os.getenv("NODE_ENV", "development"),
            "railway_env": os.getenv("RAILWAY_ENVIRONMENT"),
            "root_directory": str(cls._ROOT_DIR)
        }
    
    # ============================================================================
    # 数据库文件路径
    # ============================================================================
    
    @classmethod
    def get_database_path(cls, db_name: Optional[str] = None) -> str:
        """
        获取主数据库文件路径
        根据环境自动选择开发或生产数据库
        
        Args:
            db_name: 自定义数据库名称，默认使用环境配置
            
        Returns:
            数据库文件的绝对路径
        """
        if db_name:
            filename = db_name
        elif cls._IS_PRODUCTION:
            filename = "lanyangyang.db"
        else:
            filename = "lanyangyang_dev.db"
        
        db_path = cls._ensure_parent_directory(cls._ROOT_DIR / "data" / filename)
        logger.debug(f"数据库路径: {db_path}")
        return str(db_path)
    
    @classmethod
    def get_backup_database_path(cls, backup_name: Optional[str] = None) -> str:
        """
        获取数据库备份文件路径
        
        Args:
            backup_name: 备份文件名，默认自动生成时间戳
            
        Returns:
            备份文件的绝对路径
        """
        if backup_name is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}.db"
        
        backup_path = cls._ensure_parent_directory(cls._ROOT_DIR / "data" / "backups" / backup_name)
        return str(backup_path)
    
    @classmethod
    def get_database_schema_path(cls, schema_file: str = "schema.sql") -> str:
        """
        获取数据库Schema文件路径
        
        Args:
            schema_file: Schema文件名
            
        Returns:
            Schema文件的绝对路径
        """
        schema_path = cls._ROOT_DIR / "database" / schema_file
        if not schema_path.exists():
            logger.warning(f"Schema文件不存在: {schema_path}")
        return str(schema_path)
    
    @classmethod
    def get_migration_directory(cls) -> str:
        """
        获取数据库迁移文件目录
        
        Returns:
            迁移目录的绝对路径
        """
        migration_dir = cls._ensure_directory(cls._ROOT_DIR / "database" / "migrations")
        return str(migration_dir)
    
    @classmethod
    def get_database_migration_path(cls) -> str:
        """
        获取数据库迁移文件目录（别名方法）
        
        Returns:
            迁移目录的绝对路径
        """
        return cls.get_migration_directory()
    
    @classmethod
    def get_database_migration_file_path(cls, filename: str) -> str:
        """
        获取特定迁移文件的完整路径
        
        Args:
            filename: 迁移文件名
            
        Returns:
            迁移文件的绝对路径
        """
        migration_path = Path(cls.get_migration_directory()) / filename
        return str(migration_path)
    
    @classmethod
    def get_database_directory(cls) -> str:
        """
        获取数据库模块目录路径
        
        Returns:
            数据库目录的绝对路径
        """
        database_dir = cls._ROOT_DIR / "database"
        return str(database_dir)
    
    @classmethod
    def ensure_directory(cls, path: Union[str, Path]) -> str:
        """
        确保目录存在（别名方法）
        
        Args:
            path: 目录路径
            
        Returns:
            目录的绝对路径字符串
        """
        return str(cls._ensure_directory(path))
    
    @classmethod 
    def ensure_parent_directory(cls, path: Union[str, Path]) -> str:
        """
        确保父目录存在（别名方法）
        
        Args:
            path: 文件路径
            
        Returns:
            文件路径字符串
        """
        return str(cls._ensure_parent_directory(path))
    
    # ============================================================================
    # 日志文件路径
    # ============================================================================
    
    @classmethod
    def get_logs_directory(cls) -> str:
        """
        获取日志文件目录
        
        Returns:
            日志目录的绝对路径
        """
        logs_dir = cls._ensure_directory(cls._ROOT_DIR / "data" / "logs")
        return str(logs_dir)
    
    @classmethod
    def get_log_file_path(cls, log_type: str = "app") -> str:
        """
        获取特定类型的日志文件路径
        
        Args:
            log_type: 日志类型 (app, error, access, performance, bot等)
            
        Returns:
            日志文件的绝对路径
        """
        filename = f"{log_type}.log"
        log_path = cls._ensure_parent_directory(cls._ROOT_DIR / "data" / "logs" / filename)
        return str(log_path)
    
    # ============================================================================
    # 配置文件路径
    # ============================================================================
    
    @classmethod
    def get_config_directory(cls) -> str:
        """
        获取配置文件目录
        
        Returns:
            配置目录的绝对路径
        """
        config_dir = cls._ensure_directory(cls._ROOT_DIR / "config")
        return str(config_dir)
    
    @classmethod
    def get_env_file_path(cls, env_type: str = "") -> str:
        """
        获取环境配置文件路径
        
        Args:
            env_type: 环境类型后缀 ("", "example", "local", "production"等)
            
        Returns:
            .env文件的绝对路径
        """
        if env_type:
            filename = f".env.{env_type}"
        else:
            filename = ".env"
            
        env_path = cls._ROOT_DIR / "config" / filename
        return str(env_path)
    
    @classmethod
    def get_requirements_path(cls, req_type: str = "") -> str:
        """
        获取requirements文件路径
        
        Args:
            req_type: requirements类型 ("", "dev", "local", "prod"等)
            
        Returns:
            requirements文件的绝对路径
        """
        if req_type:
            filename = f"requirements-{req_type}.txt"
        else:
            filename = "requirements.txt"
            
        req_path = cls._ROOT_DIR / "config" / filename
        return str(req_path)
    
    # ============================================================================
    # 静态资源路径
    # ============================================================================
    
    @classmethod
    def get_static_directory(cls) -> str:
        """
        获取静态文件根目录
        
        Returns:
            静态文件目录的绝对路径
        """
        static_dir = cls._ensure_directory(cls._ROOT_DIR / "static")
        return str(static_dir)
    
    @classmethod
    def get_static_file_path(cls, relative_path: str) -> str:
        """
        获取静态文件的绝对路径
        
        Args:
            relative_path: 相对于static目录的路径 (如: "css/style.css")
            
        Returns:
            静态文件的绝对路径
        """
        static_path = cls._ensure_parent_directory(cls._ROOT_DIR / "static" / relative_path)
        return str(static_path)
    
    @classmethod
    def get_css_file_path(cls, css_file: str) -> str:
        """
        获取CSS文件路径
        
        Args:
            css_file: CSS文件名 (如: "okx-theme.css")
            
        Returns:
            CSS文件的绝对路径
        """
        return cls.get_static_file_path(f"css/{css_file}")
    
    @classmethod
    def get_js_file_path(cls, js_file: str) -> str:
        """
        获取JavaScript文件路径
        
        Args:
            js_file: JS文件名 (如: "app.js")
            
        Returns:
            JavaScript文件的绝对路径
        """
        return cls.get_static_file_path(f"js/{js_file}")
    
    @classmethod
    def get_images_directory(cls) -> str:
        """
        获取图片文件目录
        
        Returns:
            图片目录的绝对路径
        """
        images_dir = cls._ensure_directory(cls._ROOT_DIR / "static" / "images")
        return str(images_dir)
    
    # ============================================================================
    # Web模板路径
    # ============================================================================
    
    @classmethod
    def get_templates_directory(cls) -> str:
        """
        获取Web模板文件目录
        
        Returns:
            模板目录的绝对路径
        """
        templates_dir = cls._ensure_directory(cls._ROOT_DIR / "web" / "templates")
        return str(templates_dir)
    
    @classmethod
    def get_template_file_path(cls, template_name: str) -> str:
        """
        获取模板文件路径
        
        Args:
            template_name: 模板文件名 (如: "merchants.html")
            
        Returns:
            模板文件的绝对路径
        """
        template_path = cls._ROOT_DIR / "web" / "templates" / template_name
        return str(template_path)
    
    # ============================================================================
    # 上传和临时文件路径
    # ============================================================================
    
    @classmethod
    def get_uploads_directory(cls) -> str:
        """
        获取上传文件目录
        
        Returns:
            上传目录的绝对路径
        """
        uploads_dir = cls._ensure_directory(cls._ROOT_DIR / "data" / "uploads")
        return str(uploads_dir)
    
    @classmethod
    def get_temp_directory(cls) -> str:
        """
        获取临时文件目录
        
        Returns:
            临时目录的绝对路径
        """
        temp_dir = cls._ensure_directory(cls._ROOT_DIR / "data" / "temp")
        return str(temp_dir)
    
    @classmethod
    def get_temp_file_path(cls, filename: str) -> str:
        """
        获取临时文件路径
        
        Args:
            filename: 临时文件名
            
        Returns:
            临时文件的绝对路径
        """
        temp_path = cls._ensure_parent_directory(cls._ROOT_DIR / "data" / "temp" / filename)
        return str(temp_path)
    
    # ============================================================================
    # 缓存文件路径
    # ============================================================================
    
    @classmethod
    def get_cache_directory(cls) -> str:
        """
        获取缓存文件目录
        
        Returns:
            缓存目录的绝对路径
        """
        cache_dir = cls._ensure_directory(cls._ROOT_DIR / "data" / "cache")
        return str(cache_dir)
    
    @classmethod
    def get_cache_file_path(cls, cache_name: str) -> str:
        """
        获取缓存文件路径
        
        Args:
            cache_name: 缓存文件名
            
        Returns:
            缓存文件的绝对路径
        """
        cache_path = cls._ensure_parent_directory(cls._ROOT_DIR / "data" / "cache" / cache_name)
        return str(cache_path)
    
    # ============================================================================
    # 脚本和工具路径
    # ============================================================================
    
    @classmethod
    def get_scripts_directory(cls) -> str:
        """
        获取脚本文件目录
        
        Returns:
            脚本目录的绝对路径
        """
        scripts_dir = cls._ROOT_DIR / "scripts"
        return str(scripts_dir)
    
    @classmethod
    def get_script_path(cls, script_name: str) -> str:
        """
        获取脚本文件路径
        
        Args:
            script_name: 脚本文件名 (如: "migrate_to_v2.py")
            
        Returns:
            脚本文件的绝对路径
        """
        script_path = cls._ROOT_DIR / "scripts" / script_name
        return str(script_path)
    
    # ============================================================================
    # 测试相关路径
    # ============================================================================
    
    @classmethod
    def get_tests_directory(cls) -> str:
        """
        获取测试文件目录
        
        Returns:
            测试目录的绝对路径
        """
        tests_dir = cls._ROOT_DIR / "tests"
        return str(tests_dir)
    
    @classmethod
    def get_test_data_directory(cls) -> str:
        """
        获取测试数据目录
        
        Returns:
            测试数据目录的绝对路径
        """
        test_data_dir = cls._ensure_directory(cls._ROOT_DIR / "tests" / "data")
        return str(test_data_dir)
    
    @classmethod
    def get_test_reports_directory(cls) -> str:
        """
        获取测试报告目录
        
        Returns:
            测试报告目录的绝对路径
        """
        reports_dir = cls._ensure_directory(cls._ROOT_DIR / "tests" / "reports")
        return str(reports_dir)
    
    # ============================================================================
    # 文档路径
    # ============================================================================
    
    @classmethod
    def get_docs_directory(cls) -> str:
        """
        获取文档目录
        
        Returns:
            文档目录的绝对路径
        """
        docs_dir = cls._ROOT_DIR / "docs"
        return str(docs_dir)
    
    @classmethod
    def get_modules_docs_directory(cls) -> str:
        """
        获取模块文档目录
        
        Returns:
            模块文档目录的绝对路径
        """
        modules_docs_dir = cls._ROOT_DIR / "docs" / "modules"
        return str(modules_docs_dir)
    
    # ============================================================================
    # 特殊目录路径 (Claude Flow, Swarm等)
    # ============================================================================
    
    @classmethod
    def get_claude_flow_directory(cls) -> str:
        """
        获取Claude Flow工作目录
        
        Returns:
            Claude Flow目录的绝对路径
        """
        claude_flow_dir = cls._ensure_directory(cls._ROOT_DIR / ".claude-flow")
        return str(claude_flow_dir)
    
    @classmethod
    def get_swarm_directory(cls) -> str:
        """
        获取Swarm协作目录
        
        Returns:
            Swarm目录的绝对路径
        """
        swarm_dir = cls._ensure_directory(cls._ROOT_DIR / ".swarm")
        return str(swarm_dir)
    
    @classmethod
    def get_memory_directory(cls) -> str:
        """
        获取记忆存储目录
        
        Returns:
            记忆目录的绝对路径
        """
        memory_dir = cls._ensure_directory(cls._ROOT_DIR / "memory")
        return str(memory_dir)
    
    # ============================================================================
    # 工具方法
    # ============================================================================
    
    @classmethod
    def path_exists(cls, path: Union[str, Path]) -> bool:
        """
        检查路径是否存在
        
        Args:
            path: 要检查的路径
            
        Returns:
            路径是否存在
        """
        return Path(path).exists()
    
    @classmethod
    def is_file(cls, path: Union[str, Path]) -> bool:
        """
        检查路径是否为文件
        
        Args:
            path: 要检查的路径
            
        Returns:
            是否为文件
        """
        return Path(path).is_file()
    
    @classmethod
    def is_directory(cls, path: Union[str, Path]) -> bool:
        """
        检查路径是否为目录
        
        Args:
            path: 要检查的路径
            
        Returns:
            是否为目录
        """
        return Path(path).is_dir()
    
    @classmethod
    def get_file_size(cls, path: Union[str, Path]) -> int:
        """
        获取文件大小
        
        Args:
            path: 文件路径
            
        Returns:
            文件大小（字节）
        """
        try:
            return Path(path).stat().st_size
        except OSError:
            return 0
    
    @classmethod
    def create_directory_structure(cls) -> bool:
        """
        创建完整的项目目录结构
        用于初始化部署或确保所有必要目录存在
        
        Returns:
            创建是否成功
        """
        try:
            # 创建所有必要的目录
            directories = [
                cls.get_logs_directory(),
                cls.get_static_directory(),
                cls.get_uploads_directory(),
                cls.get_temp_directory(),
                cls.get_cache_directory(),
                cls.get_templates_directory(),
                cls.get_migration_directory(),
                cls.get_test_data_directory(),
                cls.get_test_reports_directory(),
                cls.get_images_directory(),
                cls._ensure_directory(cls._ROOT_DIR / "data" / "backups"),
                cls._ensure_directory(cls._ROOT_DIR / "static" / "css"),
                cls._ensure_directory(cls._ROOT_DIR / "static" / "js"),
            ]
            
            logger.info(f"成功创建 {len(directories)} 个目录结构")
            return True
            
        except Exception as e:
            logger.error(f"创建目录结构失败: {e}")
            return False
    
    @classmethod
    def get_deployment_info(cls) -> dict:
        """
        获取部署相关的路径信息
        用于Railway等云平台部署时的环境检查
        
        Returns:
            包含部署信息的字典
        """
        return {
            "root_directory": cls.get_root_directory(),
            "database_path": cls.get_database_path(),
            "logs_directory": cls.get_logs_directory(),
            "static_directory": cls.get_static_directory(),
            "is_production": cls._IS_PRODUCTION,
            "is_railway": cls._IS_RAILWAY,
            "environment": cls.get_environment_info(),
            "directories_exist": {
                "data": cls.path_exists(cls._ROOT_DIR / "data"),
                "logs": cls.path_exists(cls.get_logs_directory()),
                "static": cls.path_exists(cls.get_static_directory()),
                "config": cls.path_exists(cls.get_config_directory()),
                "templates": cls.path_exists(cls.get_templates_directory()),
            }
        }


# ============================================================================
# 便捷函数和向后兼容性支持
# ============================================================================

def get_db_path() -> str:
    """
    向后兼容: 获取数据库路径
    与config.py中的get_db_path()函数保持兼容
    """
    return PathManager.get_database_path()

def ensure_directories():
    """
    向后兼容: 确保关键目录存在
    """
    return PathManager.create_directory_structure()


# ============================================================================
# 模块初始化
# ============================================================================

if __name__ == "__main__":
    # 测试模式：显示所有路径信息
    print("=== PathManager 路径信息 ===")
    print(f"项目根目录: {PathManager.get_root_directory()}")
    print(f"环境信息: {PathManager.get_environment_info()}")
    print(f"数据库路径: {PathManager.get_database_path()}")
    print(f"日志目录: {PathManager.get_logs_directory()}")
    print(f"静态文件目录: {PathManager.get_static_directory()}")
    print(f"部署信息: {PathManager.get_deployment_info()}")
    
    # 创建目录结构
    if PathManager.create_directory_structure():
        print("✅ 目录结构创建成功")
    else:
        print("❌ 目录结构创建失败")