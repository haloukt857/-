# -*- coding: utf-8 -*-
"""
地区管理服务
从regions.py.old中提取的地区管理业务逻辑
"""

import logging
from typing import Dict, Any, List, Optional

# 导入数据库管理器
from database.db_regions import region_manager

# 导入缓存服务
from .cache_service import CacheService

logger = logging.getLogger(__name__)


class RegionMgmtService:
    """地区管理服务类"""
    
    CACHE_NAMESPACE = "region_mgmt"
    
    @staticmethod
    async def get_regions_list(
        city_search: Optional[str] = None,
        district_search: Optional[str] = None,
        status_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取地区列表
        
        Args:
            city_search: 城市搜索关键词
            district_search: 区县搜索关键词
            status_filter: 状态筛选 (enabled/disabled)
            
        Returns:
            dict: 地区列表数据
        """
        try:
            # 获取城市数据
            cities = await region_manager.get_all_cities()
            active_cities = [c for c in cities if c.get('is_active', True)]
            
            # 获取区县数据
            districts = await region_manager.get_all_districts()
            
            # 应用搜索筛选
            if city_search:
                cities = [c for c in cities if city_search.lower() in c['name'].lower()]
                
            if district_search:
                districts = [d for d in districts if district_search.lower() in d['name'].lower()]
            
            # 应用状态筛选
            if status_filter == 'enabled':
                cities = [c for c in cities if c['is_active']]
                districts = [d for d in districts if d['is_active']]
            elif status_filter == 'disabled':
                cities = [c for c in cities if not c['is_active']]
                districts = [d for d in districts if not d['is_active']]
            
            # 获取统计信息
            region_stats = await RegionMgmtService._get_region_statistics()
            
            return {
                'cities': cities,
                'districts': districts,
                'active_cities': active_cities,
                'filters': {
                    'city_search': city_search,
                    'district_search': district_search,
                    'status_filter': status_filter
                },
                'statistics': region_stats,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"获取地区列表失败: {e}")
            return {
                'cities': [],
                'districts': [],
                'active_cities': [],
                'filters': {},
                'statistics': {},
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    async def get_city_detail(city_id: int) -> Dict[str, Any]:
        """
        获取城市详情
        
        Args:
            city_id: 城市ID
            
        Returns:
            dict: 城市详情数据
        """
        try:
            city = await region_manager.get_city_by_id(city_id)
            if not city:
                return {'success': False, 'error': '城市不存在'}
            
            # 获取该城市下的所有区县
            districts = await region_manager.get_districts_by_city(city_id)
            
            return {
                'city': city,
                'districts': districts,
                'district_count': len(districts),
                'success': True
            }
            
        except Exception as e:
            logger.error(f"获取城市详情失败: city_id={city_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def create_city(name: str, is_active: bool = True, display_order: int = 0) -> Dict[str, Any]:
        """
        创建城市
        
        Args:
            name: 城市名称
            is_active: 是否激活
            
        Returns:
            dict: 创建结果
        """
        try:
            # 检查城市是否已存在
            existing_city = await region_manager.get_city_by_name(name)
            if existing_city:
                return {'success': False, 'error': '城市已存在'}
            
            city_id = await region_manager.create_city(name, is_active, display_order)
            
            if city_id:
                # 清除相关缓存
                CacheService.clear_namespace(RegionMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"城市创建成功: name={name}, city_id={city_id}")
                return {
                    'success': True, 
                    'message': '城市创建成功',
                    'city_id': city_id
                }
            else:
                return {'success': False, 'error': '城市创建失败'}
                
        except Exception as e:
            logger.error(f"创建城市失败: name={name}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def update_city(city_id: int, name: str, is_active: bool, display_order: int = 0) -> Dict[str, Any]:
        """
        更新城市
        
        Args:
            city_id: 城市ID
            name: 城市名称
            is_active: 是否激活
            display_order: 显示顺序
            
        Returns:
            dict: 更新结果
        """
        try:
            # 首先更新基本信息
            result = await region_manager.update_city(city_id, name, is_active)
            
            if result and display_order is not None:
                # 如果有显示顺序信息，也要更新
                display_result = await region_manager.update_city_display_order(city_id, display_order)
                if not display_result:
                    logger.warning(f"城市 {city_id} 显示顺序更新失败，但基本信息已更新")
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(RegionMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"城市更新成功: city_id={city_id}, name={name}, display_order={display_order}")
                return {'success': True, 'message': '城市更新成功'}
            else:
                return {'success': False, 'error': '城市更新失败'}
                
        except Exception as e:
            logger.error(f"更新城市失败: city_id={city_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def delete_city(city_id: int) -> Dict[str, Any]:
        """
        删除城市
        
        Args:
            city_id: 城市ID
            
        Returns:
            dict: 删除结果
        """
        try:
            # 检查是否有关联的区县（包括禁用的区县）
            districts = await region_manager.get_all_districts_by_city(city_id)
            if districts:
                enabled_count = len([d for d in districts if d.get('is_active', True)])
                disabled_count = len(districts) - enabled_count
                error_msg = f'该城市下还有 {len(districts)} 个区县'
                if disabled_count > 0:
                    error_msg += f'（启用: {enabled_count}，禁用: {disabled_count}）'
                error_msg += '，无法删除'
                return {'success': False, 'error': error_msg}
            
            result = await region_manager.delete_city(city_id)
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(RegionMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"城市删除成功: city_id={city_id}")
                return {'success': True, 'message': '城市删除成功'}
            else:
                return {'success': False, 'error': '城市删除失败'}
                
        except Exception as e:
            logger.error(f"删除城市失败: city_id={city_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def create_district(city_id: int, name: str, is_active: bool = True, display_order: int = 0) -> Dict[str, Any]:
        """
        创建区县
        
        Args:
            city_id: 城市ID
            name: 区县名称
            is_active: 是否激活
            
        Returns:
            dict: 创建结果
        """
        try:
            # 检查城市是否存在
            city = await region_manager.get_city_by_id(city_id)
            if not city:
                return {'success': False, 'error': '城市不存在'}
            
            # 检查区县是否已存在
            existing_district = await region_manager.get_district_by_name(city_id, name)
            if existing_district:
                return {'success': False, 'error': '该城市下区县已存在'}
            
            district_id = await region_manager.create_district(city_id, name, is_active, display_order)
            
            if district_id:
                # 清除相关缓存
                CacheService.clear_namespace(RegionMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"区县创建成功: city_id={city_id}, name={name}, district_id={district_id}")
                return {
                    'success': True, 
                    'message': '区县创建成功',
                    'district_id': district_id
                }
            else:
                return {'success': False, 'error': '区县创建失败'}
                
        except Exception as e:
            logger.error(f"创建区县失败: city_id={city_id}, name={name}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def update_district(district_id: int, city_id: int, name: str, is_active: bool, display_order: int = 0) -> Dict[str, Any]:
        """
        更新区县
        
        Args:
            district_id: 区县ID
            city_id: 城市ID
            name: 区县名称
            is_active: 是否激活
            display_order: 显示顺序
            
        Returns:
            dict: 更新结果
        """
        try:
            # 首先更新基本信息
            result = await region_manager.update_district(district_id, city_id, name, is_active)
            
            if result and display_order is not None:
                # 如果有显示顺序信息，也要更新
                display_result = await region_manager.update_district_display_order(district_id, display_order)
                if not display_result:
                    logger.warning(f"区县 {district_id} 显示顺序更新失败，但基本信息已更新")
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(RegionMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"区县更新成功: district_id={district_id}, name={name}, display_order={display_order}")
                return {'success': True, 'message': '区县更新成功'}
            else:
                return {'success': False, 'error': '区县更新失败'}
                
        except Exception as e:
            logger.error(f"更新区县失败: district_id={district_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def delete_district(district_id: int) -> Dict[str, Any]:
        """
        删除区县
        
        Args:
            district_id: 区县ID
            
        Returns:
            dict: 删除结果
        """
        try:
            result = await region_manager.delete_district(district_id)
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(RegionMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"区县删除成功: district_id={district_id}")
                return {'success': True, 'message': '区县删除成功'}
            else:
                return {'success': False, 'error': '区县删除失败'}
                
        except Exception as e:
            logger.error(f"删除区县失败: district_id={district_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def toggle_city_status(city_id: int) -> Dict[str, Any]:
        """
        切换城市状态
        
        Args:
            city_id: 城市ID
            
        Returns:
            dict: 切换结果
        """
        try:
            result = await region_manager.toggle_city_status(city_id)
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(RegionMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"城市状态切换成功: city_id={city_id}")
                return {'success': True, 'message': '城市状态切换成功'}
            else:
                return {'success': False, 'error': '城市状态切换失败'}
                
        except Exception as e:
            logger.error(f"切换城市状态失败: city_id={city_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def toggle_district_status(district_id: int) -> Dict[str, Any]:
        """
        切换区县状态
        
        Args:
            district_id: 区县ID
            
        Returns:
            dict: 切换结果
        """
        try:
            result = await region_manager.toggle_district_status(district_id)
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(RegionMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"区县状态切换成功: district_id={district_id}")
                return {'success': True, 'message': '区县状态切换成功'}
            else:
                return {'success': False, 'error': '区县状态切换失败'}
                
        except Exception as e:
            logger.error(f"切换区县状态失败: district_id={district_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def get_region_analytics() -> Dict[str, Any]:
        """
        获取地区分析数据
        
        Returns:
            dict: 地区分析数据
        """
        try:
            cache_key = "region_analytics"
            cached_data = CacheService.get(RegionMgmtService.CACHE_NAMESPACE, cache_key)
            if cached_data is not None:
                return cached_data
            
            # 获取地区分析数据
            analytics_data = {
                'total_cities': await RegionMgmtService._count_cities(),
                'active_cities': await RegionMgmtService._count_active_cities(),
                'total_districts': await RegionMgmtService._count_districts(),
                'active_districts': await RegionMgmtService._count_active_districts(),
                'cities_with_districts': await RegionMgmtService._count_cities_with_districts(),
                'coverage_stats': await RegionMgmtService._get_coverage_statistics(),
                'top_cities_by_districts': await RegionMgmtService._get_top_cities_by_districts()
            }
            
            # 缓存30分钟（地区数据变化较少）
            CacheService.set(RegionMgmtService.CACHE_NAMESPACE, cache_key, analytics_data, 1800)
            return analytics_data
            
        except Exception as e:
            logger.error(f"获取地区分析数据失败: {e}")
            return {'error': str(e)}
    
    @staticmethod
    async def _get_region_statistics() -> Dict[str, Any]:
        """获取地区统计"""
        try:
            cache_key = "region_stats"
            cached_stats = CacheService.get(RegionMgmtService.CACHE_NAMESPACE, cache_key)
            if cached_stats is not None:
                return cached_stats
            
            stats = {
                'total_cities': await RegionMgmtService._count_cities(),
                'active_cities': await RegionMgmtService._count_active_cities(),
                'total_districts': await RegionMgmtService._count_districts(),
                'active_districts': await RegionMgmtService._count_active_districts()
            }
            
            # 缓存15分钟
            CacheService.set(RegionMgmtService.CACHE_NAMESPACE, cache_key, stats, 900)
            return stats
            
        except Exception as e:
            logger.error(f"获取地区统计失败: {e}")
            return {}
    
    @staticmethod
    async def _count_cities() -> int:
        """计算城市总数"""
        try:
            cities = await region_manager.get_all_cities()
            return len(cities)
        except Exception as e:
            logger.error(f"计算城市总数失败: {e}")
            return 0
    
    @staticmethod
    async def _count_active_cities() -> int:
        """计算活跃城市数"""
        try:
            cities = await region_manager.get_all_cities()
            return len([c for c in cities if c.get('is_active', True)])
        except Exception as e:
            logger.error(f"计算活跃城市数失败: {e}")
            return 0
    
    @staticmethod
    async def _count_districts() -> int:
        """计算区县总数"""
        try:
            districts = await region_manager.get_all_districts()
            return len(districts)
        except Exception as e:
            logger.error(f"计算区县总数失败: {e}")
            return 0
    
    @staticmethod
    async def _count_active_districts() -> int:
        """计算活跃区县数"""
        try:
            districts = await region_manager.get_all_districts()
            return len([d for d in districts if d.get('is_active', True)])
        except Exception as e:
            logger.error(f"计算活跃区县数失败: {e}")
            return 0
    
    @staticmethod
    async def _count_cities_with_districts() -> int:
        """计算有区县的城市数"""
        try:
            cities = await region_manager.get_all_cities()
            count = 0
            for city in cities:
                districts = await region_manager.get_districts_by_city(city['id'])
                if districts:
                    count += 1
            return count
        except Exception as e:
            logger.error(f"计算有区县的城市数失败: {e}")
            return 0
    
    @staticmethod
    async def _get_coverage_statistics() -> Dict[str, Any]:
        """获取覆盖统计"""
        try:
            total_cities = await RegionMgmtService._count_cities()
            cities_with_districts = await RegionMgmtService._count_cities_with_districts()
            coverage_rate = (cities_with_districts / total_cities * 100) if total_cities > 0 else 0
            
            return {
                'total_cities': total_cities,
                'cities_with_districts': cities_with_districts,
                'cities_without_districts': total_cities - cities_with_districts,
                'coverage_rate': round(coverage_rate, 2)
            }
        except Exception as e:
            logger.error(f"获取覆盖统计失败: {e}")
            return {}
    
    @staticmethod
    async def _get_top_cities_by_districts(limit: int = 10) -> List[Dict[str, Any]]:
        """获取区县数最多的城市"""
        try:
            cities = await region_manager.get_all_cities()
            city_stats = []
            
            for city in cities:
                districts = await region_manager.get_districts_by_city(city['id'])
                city_stats.append({
                    'city': city,
                    'district_count': len(districts)
                })
            
            # 按区县数排序
            city_stats.sort(key=lambda x: x['district_count'], reverse=True)
            return city_stats[:limit]
            
        except Exception as e:
            logger.error(f"获取区县数最多的城市失败: {e}")
            return []
