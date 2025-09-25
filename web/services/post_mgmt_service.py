# -*- coding: utf-8 -*-
"""
帖子管理服务
从posts_routes_v2.py.old中提取的帖子管理业务逻辑
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# 导入数据库管理器
from database.db_merchants import merchant_manager
from database.db_binding_codes import BindingCodesDatabase
from database.db_connection import db_manager
from database.db_media import media_db
from database.db_regions import region_manager
from utils.enums import MERCHANT_STATUS
from database.db_channels import posting_channels_db
from config import BOT_TOKEN
import aiohttp

# 导入缓存服务
from .cache_service import CacheService

logger = logging.getLogger(__name__)


class PostMgmtService:
    """帖子管理服务类"""
    
    CACHE_NAMESPACE = "post_mgmt"
    
    # 帖子状态显示映射
    STATUS_DISPLAY_MAP = {
        MERCHANT_STATUS.PENDING_SUBMISSION.value: "待提交",
        MERCHANT_STATUS.PENDING_APPROVAL.value: "待审核", 
        MERCHANT_STATUS.APPROVED.value: "已审核",
        MERCHANT_STATUS.PUBLISHED.value: "已发布",
        MERCHANT_STATUS.EXPIRED.value: "已过期"
    }
    
    # 帖子状态操作映射
    STATUS_ACTIONS = {
        MERCHANT_STATUS.PENDING_APPROVAL.value: ["批准发布", "驳回修改"],
        MERCHANT_STATUS.APPROVED.value: ["立即发布", "修改时间", "暂停发布"],
        MERCHANT_STATUS.PUBLISHED.value: ["设为过期", "延长时间"],
        MERCHANT_STATUS.EXPIRED.value: ["重新发布", "删除帖子"]
    }
    
    @staticmethod
    def get_status_color(status: str) -> str:
        """根据帖子状态返回对应的颜色样式"""
        color_map = {
            MERCHANT_STATUS.PENDING_SUBMISSION.value: "secondary",
            MERCHANT_STATUS.PENDING_APPROVAL.value: "warning", 
            MERCHANT_STATUS.APPROVED.value: "info",
            MERCHANT_STATUS.PUBLISHED.value: "success",
            MERCHANT_STATUS.EXPIRED.value: "error"
        }
        return color_map.get(status, "ghost")
    
    @staticmethod
    def get_next_status_options(current_status: str) -> List[str]:
        """根据当前状态返回可转换的下一状态选项"""
        status_transitions = {
            MERCHANT_STATUS.PENDING_APPROVAL.value: [
                MERCHANT_STATUS.APPROVED.value,
                MERCHANT_STATUS.PENDING_SUBMISSION.value
            ],
            MERCHANT_STATUS.APPROVED.value: [
                MERCHANT_STATUS.PUBLISHED.value,
                MERCHANT_STATUS.PENDING_APPROVAL.value
            ],
            MERCHANT_STATUS.PUBLISHED.value: [
                MERCHANT_STATUS.EXPIRED.value,
                MERCHANT_STATUS.APPROVED.value
            ],
            MERCHANT_STATUS.EXPIRED.value: [
                MERCHANT_STATUS.APPROVED.value,
                MERCHANT_STATUS.PENDING_APPROVAL.value
            ]
        }
        return status_transitions.get(current_status, [])
    
    @staticmethod
    async def get_posts_list(
        status_filter: Optional[str] = None,
        region_filter: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        search_query: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
        kw_id: Optional[int] = None,
        price_p: Optional[int] = None,
        price_pp: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        获取帖子列表
        
        Args:
            status_filter: 状态筛选
            region_filter: 地区筛选
            date_from: 开始日期
            date_to: 结束日期
            search_query: 搜索关键词
            page: 页码
            per_page: 每页数量
            
        Returns:
            dict: 帖子列表数据
        """
        try:
            # 唯一口径：当提供 kw/price/region 筛选时，使用统一服务
            merchants = []
            total_posts = 0
            if kw_id is not None:
                merchants = await merchant_manager.list_active_by_keyword(int(kw_id), limit=per_page, offset=(page-1)*per_page)
                total_posts = len(merchants)
            elif price_p is not None:
                merchants = await merchant_manager.list_active_by_price('p_price', int(price_p), limit=per_page, offset=(page-1)*per_page)
                total_posts = len(merchants)
            elif price_pp is not None:
                merchants = await merchant_manager.list_active_by_price('pp_price', int(price_pp), limit=per_page, offset=(page-1)*per_page)
                total_posts = len(merchants)
            elif region_filter:
                merchants = await merchant_manager.list_active_by_district(int(region_filter), limit=per_page, offset=(page-1)*per_page)
                total_posts = len(merchants)
            else:
                # 回到帖子管理既有列表：分页、排序、状态筛选
                merchants_data = await merchant_manager.get_merchants_list(
                    page=page,
                    per_page=per_page,
                    status=status_filter,
                    district_id=int(region_filter) if region_filter else None,
                    search=search_query
                )
                merchants = merchants_data.get('posts', [])
                total_posts = merchants_data.get('total', 0)
            
            # 获取帖子统计
            post_stats = await PostMgmtService._get_post_statistics()
            
            # 获取地区列表用于筛选
            regions = await region_manager.get_all_districts()
            
            return {
                'posts': merchants,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total_posts,
                    'pages': (total_posts + per_page - 1) // per_page
                },
                'filters': {
                    'status_filter': status_filter,
                    'region_filter': region_filter,
                    'date_from': date_from,
                    'date_to': date_to,
                    'search_query': search_query
                },
                'regions': regions[:50],  # 限制数量以提升性能
                'statistics': post_stats,
                'status_options': PostMgmtService.STATUS_DISPLAY_MAP,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"获取帖子列表失败: {e}")
            return {
                'posts': [],
                'pagination': {'page': page, 'per_page': per_page, 'total': 0, 'pages': 0},
                'filters': {},
                'regions': [],
                'statistics': {},
                'status_options': {},
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    async def get_post_detail(merchant_id: int) -> Dict[str, Any]:
        """
        获取帖子详情
        
        Args:
            merchant_id: 商户ID（帖子ID）
            
        Returns:
            dict: 帖子详情数据
        """
        try:
            merchant = await merchant_manager.get_merchant_by_id(merchant_id)
            if not merchant:
                return {'success': False, 'error': '帖子不存在'}
            
            # 获取帖子媒体文件
            media_files = await media_db.get_media_by_merchant_id(merchant_id)
            
            # 获取地区信息
            region_info = None
            if merchant.get('service_area'):
                region_info = await PostMgmtService._get_region_info(merchant['service_area'])
            
            return {
                'post': merchant,
                'media_files': media_files,
                'region_info': region_info,
                'status_info': {
                    'display_name': PostMgmtService.STATUS_DISPLAY_MAP.get(merchant.get('status'), '未知'),
                    'color': PostMgmtService.get_status_color(merchant.get('status')),
                    'next_options': PostMgmtService.get_next_status_options(merchant.get('status')),
                    'actions': PostMgmtService.STATUS_ACTIONS.get(merchant.get('status'), [])
                },
                'success': True
            }
            
        except Exception as e:
            logger.error(f"获取帖子详情失败: merchant_id={merchant_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def update_post_status(
        merchant_id: int, 
        status: str, 
        publish_time: Optional[datetime] = None,
        expire_time: Optional[datetime] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        更新帖子状态
        
        Args:
            merchant_id: 商户ID
            status: 新状态
            publish_time: 发布时间
            expire_time: 过期时间
            notes: 备注
            
        Returns:
            dict: 更新结果
        """
        try:
            # 验证状态有效性
            if status not in [s.value for s in MERCHANT_STATUS]:
                return {'success': False, 'error': '无效的状态值'}
            
            # 审核需至少1张；发布必须正好6张
            if status == MERCHANT_STATUS.APPROVED.value:
                try:
                    mf = await media_db.get_media_by_merchant_id(merchant_id)
                    if not mf or len(mf) < 1:
                        return {'success': False, 'error': '审核前至少需要1个媒体文件'}
                except Exception:
                    return {'success': False, 'error': '媒体校验失败，请稍后再试'}
            if status == MERCHANT_STATUS.PUBLISHED.value:
                try:
                    mf = await media_db.get_media_by_merchant_id(merchant_id)
                    if not mf or len(mf) < 6:
                        return {'success': False, 'error': '发布前至少需要6个媒体文件'}
                except Exception:
                    return {'success': False, 'error': '媒体校验失败，请稍后再试'}
            
            # 默认时间处理：立即发布/设为过期时补充时间戳
            if status == MERCHANT_STATUS.PUBLISHED.value and publish_time is None:
                publish_time = datetime.now()
            if status == MERCHANT_STATUS.EXPIRED.value and expire_time is None:
                expire_time = datetime.now()
            
            # 如为“立即发布”，尝试直接发布到当前频道
            sent_ok = True
            if status == MERCHANT_STATUS.PUBLISHED.value:
                try:
                    merchant = await merchant_manager.get_merchant_by_id(merchant_id)
                    if merchant:
                        # 生成内容：强制使用 channel_post_template，与调度器完全一致
                        from utils.template_utils import get_template_async
                        from config import DEEPLINK_BOT_USERNAME
                        from html import escape as _esc
                        bot_u = (DEEPLINK_BOT_USERNAME or '').lstrip('@')
                        mid = merchant.get('id')
                        did = merchant.get('district_id')
                        p_price = str(merchant.get('p_price') or '').strip()
                        pp_price = str(merchant.get('pp_price') or '').strip()
                        link_merchant = f"https://t.me/{bot_u}?start=m_{mid}" if bot_u and mid else ''
                        link_district = f"https://t.me/{bot_u}?start=d_{did}" if bot_u and did else ''
                        link_price_p = f"https://t.me/{bot_u}?start=price_p_{p_price}" if bot_u and p_price else ''
                        link_price_pp = f"https://t.me/{bot_u}?start=price_pp_{pp_price}" if bot_u and pp_price else ''
                        link_report = f"https://t.me/{bot_u}?start=report_{mid}" if bot_u and mid else ''
                        # 标签（<=3，带deeplink）
                        try:
                            kw_rows = await db_manager.fetch_all(
                                "SELECT k.id, k.name FROM keywords k JOIN merchant_keywords mk ON mk.keyword_id = k.id WHERE mk.merchant_id = ? ORDER BY k.display_order ASC, k.id ASC LIMIT 3",
                                (merchant_id,)
                            )
                            parts = []
                            for r in kw_rows or []:
                                kid, nm = r['id'], r['name']
                                if bot_u and kid:
                                    parts.append(f"<a href=\"https://t.me/{_esc(bot_u)}?start=kw_{kid}\">#{_esc(nm)}</a>")
                                else:
                                    parts.append(_esc(f"#{nm}"))
                            tags_html = ' '.join(parts)
                        except Exception:
                            tags_html = ''
                        # 采用 MarkdownV2 文本，避免 HTML 在媒体组 caption 中不被解析
                        from utils.caption_renderer import render_channel_caption_md
                        content = await render_channel_caption_md(merchant, bot_u)
                        # 解析频道
                        channel_chat_id = None
                        try:
                            active = await posting_channels_db.get_active_channel()
                            if active:
                                channel_chat_id = active.get('channel_chat_id')
                        except Exception:
                            pass
                        if channel_chat_id and content:
                            final_text = content or ''

                            # 发送媒体：取前6个（发布时已保证=6），使用 sendMediaGroup 一次性发送
                            media_files = await media_db.get_media_by_merchant_id(merchant_id)
                            media_files = media_files or []
                            if len(media_files) < 6:
                                logger.error(f"商户 {merchant_id}: 媒体数量为 {len(media_files)}，少于6，无法立即发布")
                                sent_ok = False
                            elif final_text and len(final_text) > 1024:
                                logger.error(f"商户 {merchant_id}: caption 超长({len(final_text)}>1024)，无法立即发布")
                                sent_ok = False
                            else:
                                api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMediaGroup"
                                media_payload = []
                                for idx, m in enumerate(media_files[:6]):
                                    item = {
                                        'type': 'photo' if m.get('media_type') == 'photo' else 'video',
                                        'media': m.get('telegram_file_id')
                                    }
                                    if idx == 0 and final_text:
                                        item['caption'] = final_text
                                        item['parse_mode'] = 'MarkdownV2'
                                    media_payload.append(item)
                                async with aiohttp.ClientSession() as session:
                                    async with session.post(api_url, json={'chat_id': channel_chat_id, 'media': media_payload}, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                                        data = await resp.json()
                                        sent_ok = bool(data.get('ok'))
                                        if not sent_ok:
                                            logger.error(f"发送媒体组失败: {data}")
                        else:
                            sent_ok = False
                except Exception:
                    sent_ok = False

            # 发布时的到期时间优先级：
            # 1) 管理员显式传入 expire_time（路由传参）
            # 2) 若未传参，则读取商户当前的 expiration_time（若存在且在发布时间之后，视为管理员在详情页手动设置，尊重之）
            # 3) 否则根据最近一次绑定码 plan_days 计算：publish_time + plan_days
            if status == MERCHANT_STATUS.PUBLISHED.value:
                try:
                    merchant_row = await merchant_manager.get_merchant_by_id(merchant_id)
                except Exception:
                    merchant_row = None
                if expire_time is None:
                    admin_override = None
                    try:
                        raw = merchant_row.get('expiration_time') if merchant_row else None
                        if raw:
                            if isinstance(raw, str):
                                from datetime import datetime as _dt
                                try:
                                    admin_override = _dt.fromisoformat(raw)
                                except Exception:
                                    admin_override = None
                            elif isinstance(raw, datetime):
                                admin_override = raw
                    except Exception:
                        admin_override = None

                    if admin_override and publish_time and admin_override > publish_time:
                        expire_time = admin_override
                    else:
                        try:
                            plan_days = await BindingCodesDatabase.get_last_used_plan_days(merchant_id)
                            if plan_days and plan_days > 0:
                                expire_time = publish_time + timedelta(days=int(plan_days))
                        except Exception:
                            pass

            result = False
            if status != MERCHANT_STATUS.PUBLISHED.value or sent_ok:
                result = await merchant_manager.update_merchant_status(
                    merchant_id, status, publish_time, expire_time
                )
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(PostMgmtService.CACHE_NAMESPACE)
                CacheService.clear_namespace("dashboard")
                
                logger.info(f"帖子状态更新成功: merchant_id={merchant_id}, status={status}")
                return {'success': True, 'message': '帖子状态更新成功'}
            else:
                return {'success': False, 'error': '帖子状态更新失败'}
                
        except Exception as e:
            logger.error(f"更新帖子状态失败: merchant_id={merchant_id}, status={status}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def batch_update_status(merchant_ids: List[int], status: str, publish_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        批量更新帖子状态
        
        Args:
            merchant_ids: 商户ID列表
            status: 新状态
            publish_time: 发布时间
            
        Returns:
            dict: 批量更新结果
        """
        try:
            if not merchant_ids:
                return {'success': False, 'error': '未选择帖子'}
            
            if status not in [s.value for s in MERCHANT_STATUS]:
                return {'success': False, 'error': '无效的状态值'}
            
            success_count = 0
            failed_count = 0
            errors = []
            
            for merchant_id in merchant_ids:
                try:
                    result = await merchant_manager.update_merchant_status(
                        merchant_id, status, publish_time
                    )
                    if result:
                        success_count += 1
                    else:
                        failed_count += 1
                        errors.append(f"帖子 {merchant_id} 更新失败")
                except Exception as e:
                    failed_count += 1
                    errors.append(f"帖子 {merchant_id} 更新异常: {str(e)}")
            
            # 清除相关缓存
            if success_count > 0:
                CacheService.clear_namespace(PostMgmtService.CACHE_NAMESPACE)
                CacheService.clear_namespace("dashboard")
            
            return {
                'success': success_count > 0,
                'success_count': success_count,
                'failed_count': failed_count,
                'errors': errors,
                'message': f'成功更新 {success_count} 个帖子，失败 {failed_count} 个'
            }
            
        except Exception as e:
            logger.error(f"批量更新帖子状态失败: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def schedule_post_publish(merchant_id: int, publish_time: datetime) -> Dict[str, Any]:
        """
        安排帖子发布
        
        Args:
            merchant_id: 商户ID
            publish_time: 发布时间
            
        Returns:
            dict: 安排结果
        """
        try:
            # 将帖子状态设为已审核，并设置发布时间
            result = await merchant_manager.update_merchant_status(
                merchant_id,
                MERCHANT_STATUS.APPROVED.value,
                publish_time
            )
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(PostMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"帖子发布安排成功: merchant_id={merchant_id}, publish_time={publish_time}")
                return {'success': True, 'message': '帖子发布安排成功'}
            else:
                return {'success': False, 'error': '帖子发布安排失败'}
                
        except Exception as e:
            logger.error(f"安排帖子发布失败: merchant_id={merchant_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def extend_post_expiry(merchant_id: int, extend_days: int) -> Dict[str, Any]:
        """
        延长帖子过期时间
        
        Args:
            merchant_id: 商户ID
            extend_days: 延长天数
            
        Returns:
            dict: 延长结果
        """
        try:
            merchant = await merchant_manager.get_merchant_by_id(merchant_id)
            if not merchant:
                return {'success': False, 'error': '帖子不存在'}
            
            # 计算新的过期时间
            current_expire_time = merchant.get('expire_time')
            if current_expire_time:
                new_expire_time = current_expire_time + timedelta(days=extend_days)
            else:
                new_expire_time = datetime.now() + timedelta(days=extend_days)
            
            result = await merchant_manager.update_merchant_status(
                merchant_id,
                merchant['status'],
                merchant.get('publish_time'),
                new_expire_time
            )
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(PostMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"帖子过期时间延长成功: merchant_id={merchant_id}, extend_days={extend_days}")
                return {
                    'success': True, 
                    'message': f'帖子过期时间已延长 {extend_days} 天',
                    'new_expire_time': new_expire_time.isoformat()
                }
            else:
                return {'success': False, 'error': '过期时间延长失败'}
                
        except Exception as e:
            logger.error(f"延长帖子过期时间失败: merchant_id={merchant_id}, error={e}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def delete_post(merchant_id: int) -> Dict[str, Any]:
        """删除帖子（即删除对应商户记录）"""
        try:
            result = await merchant_manager.delete_merchant(merchant_id)
            if result:
                CacheService.clear_namespace(PostMgmtService.CACHE_NAMESPACE)
                CacheService.clear_namespace("dashboard")
                logger.info(f"帖子删除成功: merchant_id={merchant_id}")
                return {'success': True, 'message': '帖子已删除'}
            else:
                return {'success': False, 'error': '帖子删除失败'}
        except Exception as e:
            logger.error(f"删除帖子失败: merchant_id={merchant_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def get_post_analytics() -> Dict[str, Any]:
        """
        获取帖子分析数据
        
        Returns:
            dict: 帖子分析数据
        """
        try:
            cache_key = "post_analytics"
            cached_data = CacheService.get(PostMgmtService.CACHE_NAMESPACE, cache_key)
            if cached_data is not None:
                return cached_data
            
            # 获取帖子分析数据
            analytics_data = {
                'total_posts': await merchant_manager.count_merchants(),
                'posts_by_status': await PostMgmtService._get_posts_by_status(),
                'posts_by_region': await PostMgmtService._get_posts_by_region(),
                'publishing_trends': await PostMgmtService._get_publishing_trends(),
                'approval_rate': await PostMgmtService._calculate_approval_rate(),
                'expiry_analysis': await PostMgmtService._get_expiry_analysis()
            }
            
            # 缓存15分钟
            CacheService.set(PostMgmtService.CACHE_NAMESPACE, cache_key, analytics_data, 900)
            return analytics_data
            
        except Exception as e:
            logger.error(f"获取帖子分析数据失败: {e}")
            return {'error': str(e)}
    
    @staticmethod
    async def _get_post_statistics() -> Dict[str, Any]:
        """获取帖子统计"""
        try:
            cache_key = "post_stats"
            cached_stats = CacheService.get(PostMgmtService.CACHE_NAMESPACE, cache_key)
            if cached_stats is not None:
                return cached_stats
            
            stats = await merchant_manager.get_merchant_statistics()
            
            post_stats = {
                'total_posts': stats.get('total', 0),
                'pending_approval': stats.get('pending_approval', 0),
                'approved': stats.get('approved', 0),
                'published': stats.get('published', 0),
                'expired': stats.get('expired', 0),
                'approval_rate': stats.get('approval_rate', 0.0)
            }
            
            # 缓存10分钟
            CacheService.set(PostMgmtService.CACHE_NAMESPACE, cache_key, post_stats, 600)
            return post_stats
            
        except Exception as e:
            logger.error(f"获取帖子统计失败: {e}")
            return {
                'total_posts': 0,
                'pending_approval': 0,
                'approved': 0,
                'published': 0,
                'expired': 0,
                'approval_rate': 0.0
            }
    
    @staticmethod
    async def _get_posts_by_status() -> Dict[str, int]:
        """按状态统计帖子"""
        try:
            stats = await PostMgmtService._get_post_statistics()
            return {
                MERCHANT_STATUS.PENDING_SUBMISSION.value: stats.get('pending_submission', 0),
                MERCHANT_STATUS.PENDING_APPROVAL.value: stats.get('pending_approval', 0),
                MERCHANT_STATUS.APPROVED.value: stats.get('approved', 0),
                MERCHANT_STATUS.PUBLISHED.value: stats.get('published', 0),
                MERCHANT_STATUS.EXPIRED.value: stats.get('expired', 0)
            }
        except Exception as e:
            logger.error(f"按状态统计帖子失败: {e}")
            return {}
    
    @staticmethod
    async def _get_posts_by_region() -> Dict[str, int]:
        """按地区统计帖子"""
        try:
            return await merchant_manager.get_merchants_count_by_region()
        except Exception as e:
            logger.error(f"按地区统计帖子失败: {e}")
            return {}
    
    @staticmethod
    async def _get_publishing_trends() -> Dict[str, Any]:
        """获取发布趋势"""
        try:
            # TODO: 实现发布趋势统计逻辑
            return {}
        except Exception as e:
            logger.error(f"获取发布趋势失败: {e}")
            return {}
    
    @staticmethod
    async def _calculate_approval_rate() -> float:
        """计算审核通过率"""
        try:
            stats = await PostMgmtService._get_post_statistics()
            return stats.get('approval_rate', 0.0)
        except Exception as e:
            logger.error(f"计算审核通过率失败: {e}")
            return 0.0
    
    @staticmethod
    async def _get_expiry_analysis() -> Dict[str, Any]:
        """获取过期分析"""
        try:
            # TODO: 实现过期分析逻辑
            return {}
        except Exception as e:
            logger.error(f"获取过期分析失败: {e}")
            return {}
    
    @staticmethod
    async def _get_region_info(service_area: str) -> Dict[str, Any]:
        """获取地区信息"""
        try:
            # 解析地区信息（假设格式为"城市-区县"）
            if '-' in service_area:
                city_name, district_name = service_area.split('-', 1)
                city = await region_manager.get_city_by_name(city_name.strip())
                district = await region_manager.get_district_by_name_and_city(district_name.strip(), city['id']) if city else None
                
                return {
                    'city': city,
                    'district': district,
                    'formatted_address': service_area
                }
            else:
                city = await region_manager.get_city_by_name(service_area)
                return {
                    'city': city,
                    'district': None,
                    'formatted_address': service_area
                }
        except Exception as e:
            logger.error(f"获取地区信息失败: service_area={service_area}, error={e}")
            return {'formatted_address': service_area}
