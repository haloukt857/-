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
from config import BOT_TOKEN, DEEPLINK_BOT_USERNAME, ADMIN_IDS
import aiohttp
from database.db_channel_posts import record_posts, list_posts, delete_records_for_merchant
from services.review_publish_service import _parse_channel_post_link

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
        price_pp: Optional[int] = None,
        sort_by: str = 'publish_time'
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
            # 帖子管理页始终使用统一分页接口，支持状态/地区/搜索/排序
            # 规范化 district_id（防止传入“全部地区”等非数字）
            try:
                district_id_val = int(region_filter) if (region_filter is not None and str(region_filter).isdigit()) else None
            except Exception:
                district_id_val = None

            # 规范化 status（非法值折叠为None）
            valid_status = {s.value for s in MERCHANT_STATUS}
            status_val = status_filter if (status_filter in valid_status) else None

            merchants_data = await merchant_manager.get_merchants_list(
                page=page,
                per_page=per_page,
                status=status_val,
                district_id=district_id_val,
                search=search_query,
                sort_by=sort_by
            )
            merchants = merchants_data.get('posts', [])
            total_posts = merchants_data.get('total', 0)

            # 业务约束：帖子管理默认不显示“待提交”（包括被软删除后的商家）
            if not status_filter:
                merchants = [m for m in merchants if str(m.get('status')) != 'pending_submission']
                total_posts = len(merchants)
            
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
            # 统一到分钟粒度（秒和微秒清零）
            if status == MERCHANT_STATUS.PUBLISHED.value and isinstance(publish_time, datetime):
                publish_time = publish_time.replace(second=0, microsecond=0)
            if status == MERCHANT_STATUS.EXPIRED.value and expire_time is None:
                expire_time = datetime.now()
            # 管理员传入的过期时间统一规范为“所选日期的次日 00:00”
            try:
                if expire_time is not None:
                    if isinstance(expire_time, str):
                        try:
                            _et = datetime.fromisoformat(expire_time.replace('T', ' '))
                        except Exception:
                            _et = None
                    else:
                        _et = expire_time
                    if isinstance(_et, datetime):
                        base_midnight = _et.replace(hour=0, minute=0, second=0, microsecond=0)
                        expire_time = base_midnight + timedelta(days=1)
            except Exception:
                pass
            
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
                                        first_msg_id = None
                                        all_msg_ids = []
                                        if sent_ok:
                                            try:
                                                arr = data.get('result') or []
                                                if isinstance(arr, list) and arr:
                                                    first_msg_id = int(arr[0].get('message_id'))
                                                    for _m in arr:
                                                        try:
                                                            all_msg_ids.append(int(_m.get('message_id')))
                                                        except Exception:
                                                            pass
                                            except Exception:
                                                first_msg_id = None
                                        else:
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
                                # 规则：过期时间按日期计算，设置为“发布日00:00 + plan_days天”
                                base_midnight = publish_time.replace(hour=0, minute=0, second=0, microsecond=0)
                                expire_time = base_midnight + timedelta(days=int(plan_days))
                        except Exception:
                            pass

            result = False
            if status != MERCHANT_STATUS.PUBLISHED.value or sent_ok:
                result = await merchant_manager.update_merchant_status(
                    merchant_id, status, publish_time, expire_time
                )
            
            if result:
                # 如果是立即发布且成功，保存帖子链接并刷新“评价”区
                if status == MERCHANT_STATUS.PUBLISHED.value and sent_ok:
                    try:
                        def _build_post_link(chat_id_val: str, message_id_val: int) -> Optional[str]:
                            try:
                                s = str(chat_id_val)
                                if s.startswith('@'):
                                    username = s.lstrip('@')
                                    return f"https://t.me/{username}/{message_id_val}"
                                if s.startswith('-100'):
                                    internal = s[4:]
                                    return f"https://t.me/c/{internal}/{message_id_val}"
                                return f"https://t.me/{s}/{message_id_val}"
                            except Exception:
                                return None
                        if 'first_msg_id' in locals() and first_msg_id:
                            link = _build_post_link(str(channel_chat_id), int(first_msg_id))
                            if link:
                                await merchant_manager.set_post_url(merchant_id, link)
                        # 保存所有消息记录，便于后续删除或编辑
                        try:
                            await record_posts(
                                merchant_id,
                                str(channel_chat_id),
                                list(set(all_msg_ids)) if 'all_msg_ids' in locals() else ([] if 'first_msg_id' not in locals() else [int(first_msg_id)]),
                                url_builder=_build_post_link
                            )
                        except Exception as _re:
                            logger.warning(f"保存频道消息记录失败: {_re}")
                        from services.review_publish_service import refresh_merchant_post_reviews
                        await refresh_merchant_post_reviews(merchant_id)
                    except Exception as _e:
                        logger.warning(f"保存帖子链接或刷新评价区失败: {_e}")
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
            # 使用按日期的过期规则：基于“当前过期日的00:00”或“今天00:00”，再加天数
            current_expire_time = merchant.get('expiration_time')
            if isinstance(current_expire_time, str):
                try:
                    current_expire_time = datetime.fromisoformat(current_expire_time)
                except Exception:
                    current_expire_time = None
            base_midnight = None
            if isinstance(current_expire_time, datetime):
                base_midnight = current_expire_time.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                now = datetime.now()
                base_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            new_expire_time = base_midnight + timedelta(days=int(extend_days))
            
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
        """
        删除“本轮帖子信息”（软删除），保留商户永久ID与历史评价/订单等沉淀数据。

        动作：
        - 清空 merchants 表中的发帖相关字段，状态重置为 pending_submission；
        - 删除媒体 media 与关键词关联 merchant_keywords；
        - 不删除 reviews/merchant_scores/orders 等与历史沉淀有关的数据；
        - 保留 telegram_chat_id/name 等标识信息，便于下次机器人重新提交接力。
        """
        try:
            # 0) 先删除频道中的历史消息（若记录存在）
            try:
                rows = await list_posts(merchant_id)
                api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
                deleted_any = False
                if rows:
                    async with aiohttp.ClientSession() as session:
                        for r in rows:
                            try:
                                payload = {'chat_id': r.get('chat_id'), 'message_id': int(r.get('message_id'))}
                                async with session.post(api_url, json=payload, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                                    _d = await resp.json()
                                    if not _d.get('ok'):
                                        logger.warning(f"删除频道消息失败: {r} -> {_d}")
                                    else:
                                        deleted_any = True
                            except Exception as _e:
                                logger.warning(f"删除频道消息异常: {r} -> {_e}")
                    # 删除本地记录
                    await delete_records_for_merchant(merchant_id)
                # 兜底：若无记录，尝试解析 merchants.post_url 删除首条
                if not rows:
                    try:
                        merchant = await merchant_manager.get_merchant_by_id(merchant_id)
                        url = (merchant.get('post_url') or '').strip() if merchant else ''
                        parsed = _parse_channel_post_link(url) if url else None
                        if parsed:
                            chat_id_val, message_id_val = parsed
                            async with aiohttp.ClientSession() as session:
                                async with session.post(api_url, json={'chat_id': chat_id_val, 'message_id': int(message_id_val)}, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                                    _d = await resp.json()
                                    if not _d.get('ok'):
                                        logger.warning(f"删除频道消息失败(post_url兜底): {url} -> {_d}")
                                    else:
                                        deleted_any = True
                    except Exception as _fe:
                        logger.warning(f"post_url兜底删除异常: {url} -> {_fe}")
                if deleted_any:
                    logger.info(f"频道消息已删除（merchant_id={merchant_id}）")
            except Exception as e:
                logger.warning(f"清理频道消息记录时发生异常: {e}")

            # 1) 仅重置“本轮帖子相关字段”，不影响商户基础信息
            reset_fields = {
                'status': 'pending_submission',
                'publish_time': None,
                'expiration_time': None,
                'post_url': None,
                # 保留渠道、文案、价格、地区、关键词、媒体与联系方式等基础信息
            }
            set_clause = ", ".join([f"{k} = ?" for k in reset_fields.keys()])
            params = tuple(reset_fields.values()) + (merchant_id,)
            upd_sql = f"UPDATE merchants SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            result = await db_manager.execute_query(upd_sql, params)

            if result is None:
                return {'success': False, 'error': '帖子清理失败'}

            # 2) 清缓存
            CacheService.clear_namespace(PostMgmtService.CACHE_NAMESPACE)
            CacheService.clear_namespace("dashboard")
            logger.info(f"帖子软删除（本轮清理）成功: merchant_id={merchant_id}")
            return {'success': True, 'message': '帖子已删除（保留历史与ID）'}
        except Exception as e:
            logger.error(f"删除帖子失败(软删除): merchant_id={merchant_id}, error={e}")
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

    # ====== 审核驳回通知（机器人消息） ======
    @staticmethod
    async def notify_rejection(merchant_id: int, admin_username: Optional[str] = None) -> bool:
        """在审核“驳回修改”后，给商家发送引导消息 + “我的资料”按钮。

        - 文案：
          审核未通过，请按管理员意见修改后再提交。\n
          不清楚的地方请先与管理员沟通：@{admin_username}\n
          点击“我的资料”进行修改。

        Returns: 是否发送成功
        """
        try:
            merchant = await merchant_manager.get_merchant_by_id(merchant_id)
            if not merchant:
                return False
            chat_id = merchant.get('telegram_chat_id')
            if not chat_id:
                # 兜底1：尝试从 user_info JSON 解析
                try:
                    import json as _json
                    ui = merchant.get('user_info')
                    if isinstance(ui, str) and ui:
                        ui = _json.loads(ui)
                    if isinstance(ui, dict):
                        rid = ui.get('id') or (ui.get('raw_info') or {}).get('id')
                        if rid:
                            chat_id = rid
                except Exception:
                    pass
                # 兜底2：尝试主动刷新并重读
                if not chat_id:
                    try:
                        from .merchant_mgmt_service import MerchantMgmtService
                        await MerchantMgmtService.refresh_telegram_user_info(merchant_id)
                        merchant = await merchant_manager.get_merchant_by_id(merchant_id)
                        chat_id = merchant.get('telegram_chat_id') if merchant else None
                    except Exception:
                        chat_id = None
            if not chat_id:
                logger.warning(f"notify_rejection: 无法获取 telegram_chat_id, merchant_id={merchant_id}")
                return False

            # 解析管理员用户名（优先入参；否则取第一个 ADMIN_IDS 调 API 获取 username；兜底 @admin）
            if not admin_username:
                admin_username = None
                try:
                    if ADMIN_IDS:
                        aid = int(ADMIN_IDS[0])
                        api_get_chat = f"https://api.telegram.org/bot{BOT_TOKEN}/getChat"
                        async with aiohttp.ClientSession() as session:
                            async with session.get(api_get_chat, params={'chat_id': aid}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                                data = await resp.json()
                                if data.get('ok') and data.get('result', {}).get('username'):
                                    admin_username = f"@{data['result']['username']}"
                except Exception:
                    admin_username = None
                if not admin_username:
                    admin_username = '@admin'

            text = (
                "审核未通过，请按管理员意见修改后再提交。\n"
                f"不清楚的地方请先与管理员沟通：{admin_username}\n"
                "点击“我的资料”进行修改。"
            )

            payload = {
                'chat_id': chat_id,
                'text': text,
                'disable_web_page_preview': True,
            }
            # 按钮使用 callback_data，与 /start 后的“我的资料”一致
            payload['reply_markup'] = {
                'inline_keyboard': [[{'text': '我的资料', 'callback_data': 'profile'}]]
            }

            api_send = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            async with aiohttp.ClientSession() as session:
                async with session.post(api_send, json=payload, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    data = await resp.json()
                    ok = bool(data.get('ok'))
                    if not ok:
                        logger.warning(f"notify_rejection 发送失败: merchant_id={merchant_id}, resp={data}")
                    return ok
        except Exception as e:
            logger.error(f"notify_rejection 异常: merchant_id={merchant_id}, error={e}")
            return False
    
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
