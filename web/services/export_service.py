# -*- coding: utf-8 -*-
"""
导出服务
提供各种数据的导出功能，支持CSV、JSON等格式
"""

import csv
import io
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from starlette.responses import StreamingResponse

logger = logging.getLogger(__name__)


class ExportService:
    """导出服务类"""
    
    @staticmethod
    def export_to_csv(data: List[Dict[str, Any]], filename: str, headers: Optional[List[str]] = None) -> StreamingResponse:
        """
        导出数据到CSV格式
        
        Args:
            data: 要导出的数据列表
            filename: 导出文件名
            headers: CSV列头（可选，自动从数据推断）
            
        Returns:
            StreamingResponse: CSV文件流响应
        """
        try:
            if not data:
                # 空数据时创建空CSV
                output = io.StringIO()
                if headers:
                    writer = csv.DictWriter(output, fieldnames=headers)
                    writer.writeheader()
                content = output.getvalue()
            else:
                # 自动推断列头
                if headers is None:
                    headers = list(data[0].keys()) if data else []
                
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=headers)
                writer.writeheader()
                
                for row in data:
                    # 处理中文和特殊字符
                    clean_row = {}
                    for key, value in row.items():
                        if key in headers:
                            # 转换为字符串并处理None值
                            clean_row[key] = str(value) if value is not None else ''
                    writer.writerow(clean_row)
                
                content = output.getvalue()
            
            # 创建文件名（包含时间戳）
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            full_filename = f"{filename}_{timestamp}.csv"
            
            # 返回流响应
            def generate():
                yield content.encode('utf-8-sig')  # 使用UTF-8 BOM以正确显示中文
            
            return StreamingResponse(
                generate(),
                media_type='text/csv',
                headers={
                    'Content-Disposition': f'attachment; filename="{full_filename}"'
                }
            )
            
        except Exception as e:
            logger.error(f"导出CSV失败: {e}")
            raise
    
    @staticmethod
    def export_to_json(data: Union[Dict, List], filename: str, pretty_print: bool = True) -> StreamingResponse:
        """
        导出数据到JSON格式
        
        Args:
            data: 要导出的数据
            filename: 导出文件名
            pretty_print: 是否格式化JSON
            
        Returns:
            StreamingResponse: JSON文件流响应
        """
        try:
            # JSON序列化配置
            json_params = {
                'ensure_ascii': False,  # 支持中文
                'default': str  # 处理datetime等不可序列化的对象
            }
            
            if pretty_print:
                json_params.update({'indent': 2, 'separators': (',', ': ')})
            
            content = json.dumps(data, **json_params)
            
            # 创建文件名（包含时间戳）
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            full_filename = f"{filename}_{timestamp}.json"
            
            def generate():
                yield content.encode('utf-8')
            
            return StreamingResponse(
                generate(),
                media_type='application/json',
                headers={
                    'Content-Disposition': f'attachment; filename="{full_filename}"'
                }
            )
            
        except Exception as e:
            logger.error(f"导出JSON失败: {e}")
            raise
    
    @staticmethod
    async def export_merchants_csv(filters: Optional[Dict[str, Any]] = None) -> StreamingResponse:
        """
        导出商户数据为CSV
        
        Args:
            filters: 筛选条件
            
        Returns:
            StreamingResponse: CSV文件流响应
        """
        try:
            from database.db_merchants import merchant_manager
            
            # 获取商户数据
            merchants = await merchant_manager.get_merchants(
                status=filters.get('status') if filters else None,
                search=filters.get('search') if filters else None
            )
            
            # 定义CSV列头
            headers = [
                'id', 'permanent_id', 'telegram_chat_id', 'telegram_username',
                'business_name', 'contact_person', 'contact_phone', 'service_type',
                'service_area', 'service_address', 'business_hours', 'description',
                'status', 'created_time', 'updated_time', 'publish_time', 'expire_time'
            ]
            
            return ExportService.export_to_csv(merchants, 'merchants', headers)
            
        except Exception as e:
            logger.error(f"导出商户CSV失败: {e}")
            raise
    
    @staticmethod
    async def export_users_csv(filters: Optional[Dict[str, Any]] = None) -> StreamingResponse:
        """
        导出用户数据为CSV
        
        Args:
            filters: 筛选条件
            
        Returns:
            StreamingResponse: CSV文件流响应
        """
        try:
            from database.db_users import user_manager
            
            # 获取用户数据
            users = await user_manager.get_users_with_pagination(
                level_name=filters.get('level') if filters else None,
                search=filters.get('search') if filters else None,
                limit=10000  # 导出时不限制数量
            )
            
            # 定义CSV列头
            headers = [
                'user_id', 'telegram_chat_id', 'telegram_username', 'telegram_first_name',
                'points', 'experience', 'level_name', 'registration_time', 'last_activity',
                'is_subscribed', 'subscription_verified_time'
            ]
            
            return ExportService.export_to_csv(users, 'users', headers)
            
        except Exception as e:
            logger.error(f"导出用户CSV失败: {e}")
            raise
    
    @staticmethod
    async def export_orders_csv(filters: Optional[Dict[str, Any]] = None) -> StreamingResponse:
        """
        导出订单数据为CSV
        
        Args:
            filters: 筛选条件
            
        Returns:
            StreamingResponse: CSV文件流响应
        """
        try:
            from database.db_orders import OrderManager
            
            order_manager = OrderManager()
            
            # 获取订单数据
            orders = await order_manager.get_orders_with_filters(
                status=filters.get('status') if filters else None,
                merchant_id=filters.get('merchant_id') if filters else None,
                user_id=filters.get('user_id') if filters else None,
                date_from=filters.get('date_from') if filters else None,
                date_to=filters.get('date_to') if filters else None,
                limit=10000
            )
            
            # 定义CSV列头
            headers = [
                'id', 'merchant_id', 'user_id', 'service_details', 'order_time',
                'status', 'notes', 'user_rating', 'user_review_comment',
                'merchant_rating', 'merchant_review_comment', 'updated_time'
            ]
            
            return ExportService.export_to_csv(orders, 'orders', headers)
            
        except Exception as e:
            logger.error(f"导出订单CSV失败: {e}")
            raise
    
    @staticmethod
    async def export_binding_codes_csv() -> StreamingResponse:
        """
        导出绑定码数据为CSV
        
        Returns:
            StreamingResponse: CSV文件流响应
        """
        try:
            from database.db_binding_codes import binding_codes_manager
            
            # 获取绑定码数据
            result = await binding_codes_manager.get_all_binding_codes()
            binding_codes = (result or {}).get('codes', result or [])
            
            # 定义CSV列头
            headers = [
                'id', 'binding_code', 'is_used', 'merchant_id',
                'created_time', 'used_time', 'notes'
            ]
            
            return ExportService.export_to_csv(binding_codes, 'binding_codes', headers)
            
        except Exception as e:
            logger.error(f"导出绑定码CSV失败: {e}")
            raise
    
    @staticmethod
    async def export_dashboard_summary_json() -> StreamingResponse:
        """
        导出仪表板摘要数据为JSON
        
        Returns:
            StreamingResponse: JSON文件流响应
        """
        try:
            from .dashboard_service import DashboardService
            
            # 获取仪表板数据
            dashboard_data = await DashboardService.get_dashboard_data()
            
            # 添加导出信息
            export_data = {
                'export_info': {
                    'exported_at': datetime.now().isoformat(),
                    'data_source': 'dashboard_service',
                    'version': '2.0.0'
                },
                'dashboard_data': dashboard_data
            }
            
            return ExportService.export_to_json(export_data, 'dashboard_summary')
            
        except Exception as e:
            logger.error(f"导出仪表板摘要JSON失败: {e}")
            raise
    
    @staticmethod
    def create_export_response(content: str, filename: str, content_type: str = 'text/plain') -> StreamingResponse:
        """
        创建通用的导出响应
        
        Args:
            content: 文件内容
            filename: 文件名
            content_type: MIME类型
            
        Returns:
            StreamingResponse: 文件流响应
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            full_filename = f"{filename}_{timestamp}"
            
            def generate():
                if isinstance(content, str):
                    yield content.encode('utf-8')
                else:
                    yield content
            
            return StreamingResponse(
                generate(),
                media_type=content_type,
                headers={
                    'Content-Disposition': f'attachment; filename="{full_filename}"'
                }
            )
            
        except Exception as e:
            logger.error(f"创建导出响应失败: {e}")
            raise
