#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APScheduler定时任务Worker

基于ADR-004决策，采用APScheduler作为内部调度器处理所有定时任务
独立Worker进程，与主ASGI应用解耦，提高系统稳定性和可靠性

核心定时任务:
1. 商家平均分计算 (每日3:00)
2. 帖子自动发布 (每分钟)
3. 服务到期处理 (每日1:00)
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Optional, List

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# APScheduler相关导入
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

# 项目数据库管理器导入
from database.db_connection import db_manager
from database.db_reviews import ReviewManager
from database.db_orders import OrderManager
from database.db_merchants import MerchantManager
from database.db_system_config import system_config_manager
from database.db_channels import posting_channels_db
from database.db_scheduling import posting_time_slots_db
from database.db_media import media_db
from config import BOT_TOKEN
import aiohttp

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('scheduler.log')
    ]
)
logger = logging.getLogger(__name__)

class SchedulerWorker:
    """APScheduler调度器Worker
    
    负责执行所有定时任务，包括:
    - 商家评分计算
    - 帖子自动发布
    - 服务到期处理
    """
    
    def __init__(self):
        """初始化调度器"""
        # 配置调度器
        jobstores = {
            'default': MemoryJobStore()
        }
        executors = {
            'default': AsyncIOExecutor()
        }
        job_defaults = {
            'coalesce': False,  # 不合并同类任务
            'max_instances': 1,  # 每个任务最多同时运行1个实例
            'misfire_grace_time': 30  # 错过任务的容忍时间(秒)
        }
        
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='Asia/Shanghai'
        )
        
        # 添加事件监听器
        self.scheduler.add_listener(self._job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        
        # 动态时间槽调度相关
        self._slot_job_ids = set()
        self._time_slot_signature = None

        logger.info("APScheduler调度器Worker初始化完成")
    
    def _job_listener(self, event):
        """任务执行事件监听器"""
        if event.exception:
            logger.error(f"任务执行失败: {event.job_id}, 异常: {event.exception}")
        else:
            logger.info(f"任务执行成功: {event.job_id}")
    
    async def update_all_merchant_scores(self):
        """
        定时任务1: 更新所有商家的平均评分
        执行时间: 每日 3:00 AM
        
        逻辑:
        1. 获取所有有评价的商家列表
        2. 为每个商家计算各维度平均分
        3. 更新merchant_scores表
        4. 记录处理结果
        """
        start_time = datetime.now()
        logger.info("开始执行商家平均分计算任务")
        
        try:
            # 1. 获取所有有评价的商家ID列表
            query_merchants = """
                SELECT DISTINCT merchant_id 
                FROM reviews 
                WHERE is_confirmed_by_merchant = TRUE
            """
            
            merchant_results = await db_manager.fetch_all(query_merchants)
            merchant_ids = [row['merchant_id'] for row in merchant_results]
            
            if not merchant_ids:
                logger.info("没有找到有评价的商家，跳过计算")
                return
            
            logger.info(f"找到 {len(merchant_ids)} 个需要计算平均分的商家")
            
            # 2. 为每个商家计算并更新平均分
            success_count = 0
            error_count = 0
            
            for merchant_id in merchant_ids:
                try:
                    # 使用ReviewManager的方法计算并更新平均分
                    if await ReviewManager.calculate_and_update_merchant_scores(merchant_id):
                        success_count += 1
                    else:
                        error_count += 1
                        logger.warning(f"商家 {merchant_id} 平均分计算失败")
                        
                except Exception as e:
                    error_count += 1
                    logger.error(f"商家 {merchant_id} 平均分计算异常: {e}")
            
            # 3. 记录处理结果
            logger.info(f"商家平均分计算任务完成: 成功 {success_count}, 失败 {error_count}")
            
            # 4. 清理过期数据(可选)
            # 可以在这里添加清理长时间未更新的merchant_scores记录的逻辑
            
        except Exception as e:
            logger.error(f"商家平均分计算任务执行失败: {e}", exc_info=True)
            raise
        finally:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"商家平均分计算任务执行完毕，耗时: {execution_time:.2f}秒")
    
    async def publish_pending_posts(self):
        """
        定时任务2: 发布待发布的帖子
        执行时间: 每分钟
        
        逻辑:
        1. 查询状态为'approved'且publish_time <= 当前时间的帖子
        2. 发布到指定Telegram频道
        3. 更新帖子状态为'published'
        4. 记录发布结果
        """
        start_time = datetime.now()
        logger.debug("开始执行帖子自动发布任务")
        
        try:
            current_time = datetime.now()
            
            # 1. 查询符合发布条件的帖子（基于结构化地区字段）
            query = """
                SELECT m.id, m.telegram_chat_id, m.name, m.merchant_type,
                       m.p_price, m.pp_price, m.adv_sentence, m.publish_time,
                       m.channel_chat_id, m.channel_link,
                       m.city_id, m.district_id,
                       c.name AS city_name, d.name AS district_name
                FROM merchants m
                LEFT JOIN cities c ON m.city_id = c.id
                LEFT JOIN districts d ON m.district_id = d.id
                WHERE m.status = 'approved' 
                  AND (m.publish_time IS NULL OR m.publish_time <= ?)
                ORDER BY m.publish_time ASC
            """
            pending_posts = await db_manager.fetch_all(query, (current_time,))
            
            if not pending_posts:
                logger.debug("没有找到需要发布的帖子")
                return
            
            logger.info(f"找到 {len(pending_posts)} 个待发布帖子")
            
            # 2. 逐个发布帖子
            success_count = 0
            error_count = 0
            
            for post in pending_posts:
                try:
                    merchant_id = post['id']
                    
                    # 解析发布频道：仅允许使用“频道配置”的当前频道；未配置则跳过
                    channel_chat_id = None
                    try:
                        active_ch = await posting_channels_db.get_active_channel()
                        if active_ch:
                            channel_chat_id = active_ch.get('channel_chat_id')
                    except Exception as _e:
                        logger.warning(f"读取频道配置失败: {_e}")

                    if not channel_chat_id:
                        logger.warning(f"缺少发布频道配置，跳过商户 {merchant_id} 的发布")
                        continue
                    
                    # 生成帖子内容
                    post_content = await self._generate_post_content(post)
                    
                    # 内容必须存在（不做兜底文本）
                    if not post_content:
                        logger.error(f"商户 {merchant_id}: 模板渲染为空，跳过发布")
                        continue
                    # 调用Telegram Bot API发布帖子
                    sent_ok = False
                    first_msg_id = None
                    try:
                        from html import escape as _escape
                        adv = None
                        try:
                            adv_val = post.get('adv_sentence') if isinstance(post, dict) else None
                            adv = (adv_val or '').strip() if isinstance(adv_val, str) else None
                        except Exception:
                            adv = None
                        # 获取媒体（最多6个）
                        media_files = await media_db.get_media_by_merchant_id(merchant_id)
                        media_files = media_files or []

                        # 严格要求：必须正好6个媒体
                        if len(media_files) != 6:
                            logger.error(f"商户 {merchant_id}: 媒体数量为 {len(media_files)}，不等于6，跳过发布")
                            continue

                        # 构造caption（MarkdownV2 渲染）
                        final_text = _escape(post_content or '')

                        # 严格要求：只使用 sendMediaGroup，一次性发送；caption 长度不得超过 1024
                        if final_text and len(final_text) > 1024:
                            logger.error(f"商户 {merchant_id}: caption 超长({len(final_text)}>1024)，跳过发布")
                            continue

                        # 仅一种发送方式：发送媒体组（6个）+ 首图caption（MarkdownV2）
                        api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMediaGroup"
                        media_payload = []
                        for idx, m in enumerate(media_files):
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
                                if sent_ok:
                                    try:
                                        arr = data.get('result') or []
                                        if isinstance(arr, list) and arr:
                                            first_msg_id = int(arr[0].get('message_id'))
                                    except Exception:
                                        first_msg_id = None
                                else:
                                    logger.error(f"发送媒体组失败: {data}")
                    except Exception as send_e:
                        logger.error(f"调用Telegram发送失败: {send_e}")

                    # 3. 更新帖子状态为'published'
                    # 计算过期时间（按绑定码计划天数），精确到分钟
                    expire_time_calc = None
                    publish_time_value = post.get('publish_time')
                    try:
                        if isinstance(publish_time_value, str) and len(publish_time_value) >= 16:
                            ptime = datetime.fromisoformat(publish_time_value[:16] + (':00' if len(publish_time_value) == 16 else publish_time_value[16:]))
                        elif isinstance(publish_time_value, datetime):
                            ptime = publish_time_value
                        else:
                            ptime = current_time
                        ptime = ptime.replace(second=0, microsecond=0)
                        from database.db_binding_codes import BindingCodesDatabase
                        pdays = await BindingCodesDatabase.get_last_used_plan_days(merchant_id)
                        if pdays and pdays > 0:
                            # 规则：到期按日期计算，截止到“次日00:00”。
                            base_midnight = ptime.replace(hour=0, minute=0, second=0, microsecond=0)
                            expire_time_calc = base_midnight + timedelta(days=int(pdays))
                    except Exception:
                        expire_time_calc = None

                    update_success = await MerchantManager.update_merchant_status(
                        merchant_id, 'published', ptime if 'ptime' in locals() else None, expire_time_calc
                    ) if sent_ok else False
                    
                    if update_success and sent_ok:
                        # 保存帖子链接
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
                            if first_msg_id:
                                link = _build_post_link(str(channel_chat_id), int(first_msg_id))
                                if link:
                                    await MerchantManager.set_post_url(merchant_id, link)
                        except Exception as _e:
                            logger.warning(f"保存帖子链接失败: {_e}")
                        # 首次发布后刷新评价区（将所有U2M评价链接加入caption）
                        try:
                            from services.review_publish_service import refresh_merchant_post_reviews
                            await refresh_merchant_post_reviews(merchant_id)
                        except Exception as _e:
                            logger.warning(f"刷新帖子评价区失败: {_e}")
                        success_count += 1
                        logger.info(f"商户 {merchant_id} 帖子发布成功")
                    else:
                        error_count += 1
                        logger.error(f"商户 {merchant_id} 发布失败或状态更新失败")
                        
                except Exception as e:
                    error_count += 1
                    logger.error(f"发布帖子 {post.get('id', 'unknown')} 时出现异常: {e}")
            
            # 4. 记录发布结果
            if success_count > 0 or error_count > 0:
                logger.info(f"帖子发布任务完成: 成功 {success_count}, 失败 {error_count}")
            
        except Exception as e:
            logger.error(f"帖子自动发布任务执行失败: {e}", exc_info=True)
            raise
        finally:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.debug(f"帖子自动发布任务执行完毕，耗时: {execution_time:.2f}秒")
    
    async def _generate_post_content(self, merchant_data: dict) -> str:
        """生成频道贴文内容（MarkdownV2）。
        为避免 sendMediaGroup 在部分环境下不解析 HTML 的问题，这里改用 MarkdownV2。
        模板仍复用 `channel_post_template` 的占位含义，但以 MarkdownV2 链接渲染。
        返回的字符串用于 caption，长度需 <=1024。
        """
        try:
            from config import DEEPLINK_BOT_USERNAME
            from utils.caption_renderer import render_channel_caption_md
            # 关键词
            kw_names: List[str] = []
            kw_rows = []
            try:
                rows = kw_rows = await db_manager.fetch_all(
                    "SELECT k.name FROM keywords k JOIN merchant_keywords mk ON mk.keyword_id = k.id WHERE mk.merchant_id = ? ORDER BY k.display_order ASC, k.id ASC",
                    (merchant_data.get('id'),)
                )
                kw_names = [r['name'] for r in rows] if rows else []
            except Exception:
                kw_names = []

            # 计算deeplink
            bot_u = (DEEPLINK_BOT_USERNAME or '').lstrip('@')
            mid = merchant_data.get('id')
            did = merchant_data.get('district_id')
            p_price = str(merchant_data.get('p_price') or '').strip()
            pp_price = str(merchant_data.get('pp_price') or '').strip()

            link_merchant = f"https://t.me/{bot_u}?start=m_{mid}" if bot_u and mid else ''
            link_district = f"https://t.me/{bot_u}?start=d_{did}" if bot_u and did else ''
            link_price_p = f"https://t.me/{bot_u}?start=price_p_{p_price}" if bot_u and p_price else ''
            link_price_pp = f"https://t.me/{bot_u}?start=price_pp_{pp_price}" if bot_u and pp_price else ''
            link_report = f"https://t.me/{bot_u}?start=report_{mid}" if bot_u and mid else ''
            # 优惠占位
            offer_text = "-"
            # 优势一句话（不使用blockquote，由模板首行承载）
            adv_val = merchant_data.get('adv_sentence') if isinstance(merchant_data, dict) else None
            adv_text = (adv_val or '').strip() if isinstance(adv_val, str) else ''

            # 标签（最多3个，生成HTML链接）
            tags_html = ""
            try:
                kw_full_rows = await db_manager.fetch_all(
                    "SELECT k.id, k.name FROM keywords k JOIN merchant_keywords mk ON mk.keyword_id = k.id WHERE mk.merchant_id = ? ORDER BY k.display_order ASC, k.id ASC LIMIT 3",
                    (merchant_data.get('id'),)
                )
                parts = []
                for r in (kw_full_rows or [])[:3]:
                    kid = r['id']
                    nm = r['name']
                    if bot_u and kid:
                        parts.append(f"<a href=\"https://t.me/{bot_u}?start=kw_{kid}\">#{_esc(nm)}</a>")
                    else:
                        parts.append(_esc(f"#{nm}"))
                tags_html = ' '.join(parts)
            except Exception:
                # 回退到仅文本
                tags_html = _esc(' '.join([f"#{n}" for n in kw_names[:3]])) if kw_names else ''

            return await render_channel_caption_md(merchant_data, DEEPLINK_BOT_USERNAME or '')
            
        except Exception as e:
            logger.error(f"生成帖子内容时出错: {e}")
            return None
    
    async def handle_expired_services(self):
        """
        定时任务3: 处理到期的服务
        执行时间: 每日 1:00 AM
        
        逻辑:
        1. 查询到期的商家服务(expiration_time <= 当前时间)
        2. 更新状态为'expired'
        3. 发送到期通知(可选)
        4. 记录处理结果
        """
        start_time = datetime.now()
        logger.info("开始执行服务到期处理任务")
        
        try:
            current_time = datetime.now()
            
            # 1. 查询到期的商家服务
            # 查询条件：expiration_time <= 当前时间 且 状态不是'expired'
            query = """
                SELECT id, telegram_chat_id, name, status, expiration_time
                FROM merchants 
                WHERE expiration_time IS NOT NULL 
                AND expiration_time <= ?
                AND status != 'expired'
                ORDER BY expiration_time ASC
            """
            
            expired_services = await db_manager.fetch_all(query, (current_time,))
            
            if not expired_services:
                logger.info("没有找到需要处理的到期服务")
                return
            
            logger.info(f"找到 {len(expired_services)} 个到期服务")
            
            # 2. 逐个处理到期服务
            success_count = 0
            error_count = 0
            notification_count = 0
            
            for service in expired_services:
                try:
                    merchant_id = service['id']
                    merchant_name = service.get('name', '未知')
                    expiration_time = service.get('expiration_time')
                    current_status = service.get('status')
                    telegram_chat_id = service.get('telegram_chat_id')
                    
                    logger.info(f"处理到期服务 - 商户: {merchant_name}(ID:{merchant_id}), "
                              f"到期时间: {expiration_time}, 当前状态: {current_status}")
                    
                    # 更新状态为'expired'
                    update_success = await MerchantManager.update_merchant_status(
                        merchant_id, 'expired'
                    )
                    
                    if update_success:
                        success_count += 1
                        logger.info(f"商户 {merchant_id}({merchant_name}) 状态已更新为expired")
                        # 删除频道中的帖子（若记录了链接）
                        try:
                            row = await MerchantManager.get_merchant_by_id(merchant_id)
                            post_url = row.get('post_url') if row else None
                            if post_url:
                                chat_id_val = None
                                message_id_val = None
                                try:
                                    # 解析 https://t.me/c/<internal>/<mid> 或 https://t.me/<username>/<mid>
                                    import re as _re
                                    m = _re.search(r"https://t\.me/(c/([\d]+)/([\d]+)|([A-Za-z0-9_]+)/([\d]+))", str(post_url))
                                    if m:
                                        if m.group(2) and m.group(3):
                                            chat_id_val = f"-100{m.group(2)}"
                                            message_id_val = int(m.group(3))
                                        elif m.group(4) and m.group(5):
                                            chat_id_val = f"@{m.group(4)}"
                                            message_id_val = int(m.group(5))
                                except Exception:
                                    chat_id_val = None
                                    message_id_val = None
                                if chat_id_val and message_id_val:
                                    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
                                    async with aiohttp.ClientSession() as session:
                                        async with session.post(api_url, json={'chat_id': chat_id_val, 'message_id': message_id_val}, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                                            _ = await resp.json()
                        
                        # 3. 可选：发送到期通知
                        # 这里可以根据系统配置决定是否发送通知
                        notification_config = await system_config_manager.get_config(
                            'expiration_notification_config',
                            {'enabled': False, 'send_to_merchant': True}
                        )
                        
                        if notification_config.get('enabled', False):
                            # 实际实现中应该使用Bot API发送通知
                            # 这里只记录通知意图
                            logger.info(f"需要向商户 {merchant_id} 发送到期通知")
                            notification_count += 1
                        
                    else:
                        error_count += 1
                        logger.error(f"商户 {merchant_id}({merchant_name}) 状态更新失败")
                        
                except Exception as e:
                    error_count += 1
                    logger.error(f"处理到期服务 {service.get('id', 'unknown')} 时出现异常: {e}")
            
            # 4. 记录处理结果
            logger.info(f"服务到期处理任务完成:")
            logger.info(f"  - 成功处理: {success_count} 个")
            logger.info(f"  - 处理失败: {error_count} 个")
            if notification_count > 0:
                logger.info(f"  - 通知发送: {notification_count} 个")
            
            # 可选：清理长时间过期的记录
            cleanup_config = await system_config_manager.get_config(
                'expired_cleanup_config',
                {'enabled': False, 'days_threshold': 30}
            )
            
            if cleanup_config.get('enabled', False):
                days_threshold = cleanup_config.get('days_threshold', 30)
                cleanup_count = await self._cleanup_old_expired_services(days_threshold)
                if cleanup_count > 0:
                    logger.info(f"清理了 {cleanup_count} 个超过 {days_threshold} 天的过期记录")
            
        except Exception as e:
            logger.error(f"服务到期处理任务执行失败: {e}", exc_info=True)
            raise
        finally:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"服务到期处理任务执行完毕，耗时: {execution_time:.2f}秒")
    
    async def _cleanup_old_expired_services(self, days_threshold: int) -> int:
        """
        清理长时间过期的服务记录(可选功能)
        
        Args:
            days_threshold: 过期天数阈值
            
        Returns:
            int: 清理的记录数量
        """
        try:
            from datetime import timedelta
            
            threshold_date = datetime.now() - timedelta(days=days_threshold)
            
            # 查询超过阈值的过期记录数量
            count_query = """
                SELECT COUNT(*) as count
                FROM merchants 
                WHERE status = 'expired' 
                AND expiration_time IS NOT NULL 
                AND expiration_time <= ?
            """
            
            count_result = await db_manager.fetch_one(count_query, (threshold_date,))
            cleanup_count = count_result['count'] if count_result else 0
            
            if cleanup_count == 0:
                return 0
            
            # 可以选择删除记录或标记为归档状态
            # 这里采用标记方式，避免数据丢失
            cleanup_query = """
                UPDATE merchants 
                SET status = 'archived_expired', 
                    updated_at = CURRENT_TIMESTAMP
                WHERE status = 'expired' 
                AND expiration_time IS NOT NULL 
                AND expiration_time <= ?
            """
            
            await db_manager.execute_query(cleanup_query, (threshold_date,))
            
            logger.info(f"已将 {cleanup_count} 个超期记录标记为归档状态")
            return cleanup_count
            
        except Exception as e:
            logger.error(f"清理过期记录时出错: {e}")
            return 0
    
    def register_jobs(self):
        """注册所有定时任务到调度器"""
        logger.info("开始注册定时任务")
        
        # 任务1: 商家平均分计算 - 每日3:00
        self.scheduler.add_job(
            func=self.update_all_merchant_scores,
            trigger=CronTrigger(hour=3, minute=0),
            id='update_merchant_scores',
            name='更新商家平均评分',
            replace_existing=True
        )
        logger.info("已注册任务: 商家平均分计算 (每日3:00)")
        
        # 任务2: 帖子自动发布 - 按时间槽动态注册（在 start() 中首次加载，并定时热更新）
        # 注意：这里不再固定每分钟触发，改为读取DB的 posting_time_slots
        logger.info("帖子自动发布将按‘时间槽配置’动态注册")
        
        # 任务3: 服务到期处理 - 每日1:00
        self.scheduler.add_job(
            func=self.handle_expired_services,
            trigger=CronTrigger(hour=1, minute=0),
            id='handle_expired_services',
            name='服务到期处理',
            replace_existing=True
        )
        logger.info("已注册任务: 服务到期处理 (每日1:00)")
        
        logger.info("所有定时任务注册完成")

    async def _load_active_time_slots(self):
        """读取启用中的时间槽，返回规范化的 [(hour, minute)] 列表"""
        try:
            slots = await posting_time_slots_db.get_active_slots()
            result = []
            for s in slots or []:
                t = (s.get('time_str') or '').strip()
                if not t:
                    continue
                try:
                    parts = t.split(':')
                    hour = int(parts[0])
                    minute = int(parts[1]) if len(parts) > 1 else 0
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        result.append((hour, minute))
                except Exception:
                    continue
            # 去重并排序
            result = sorted(set(result))
            return result
        except Exception as e:
            logger.error(f"读取时间槽失败: {e}")
            return []

    def _compute_slots_signature(self, slots: list[tuple[int, int]]) -> str:
        try:
            return ','.join([f"{h:02d}:{m:02d}" for h, m in slots])
        except Exception:
            return ''

    def _clear_slot_jobs(self):
        for jid in list(self._slot_job_ids):
            try:
                self.scheduler.remove_job(jid)
            except Exception:
                pass
        self._slot_job_ids.clear()

    def _schedule_slot_jobs(self, slots: list[tuple[int, int]]):
        for hour, minute in slots:
            job_id = f"publish_posts_{hour:02d}{minute:02d}"
            try:
                self.scheduler.add_job(
                    func=self.publish_pending_posts,
                    trigger=CronTrigger(hour=hour, minute=minute),
                    id=job_id,
                    name=f"帖子自动发布 {hour:02d}:{minute:02d}",
                    replace_existing=True
                )
                self._slot_job_ids.add(job_id)
                logger.info(f"已注册时间槽任务: {hour:02d}:{minute:02d}")
            except Exception as e:
                logger.error(f"注册时间槽任务失败 {hour:02d}:{minute:02d}: {e}")

    async def refresh_time_slot_jobs(self):
        """热更新时间槽任务：当DB配置变化时，重载Cron任务"""
        slots = await self._load_active_time_slots()
        signature = self._compute_slots_signature(slots)
        if signature != self._time_slot_signature:
            logger.info(f"检测到时间槽变更，重载任务: {self._time_slot_signature} -> {signature}")
            self._clear_slot_jobs()
            self._schedule_slot_jobs(slots)
            self._time_slot_signature = signature
        else:
            logger.debug("时间槽未变化，无需重载")
    
    async def start(self):
        """启动调度器Worker"""
        logger.info("启动APScheduler调度器Worker")
        
        try:
            # 测试数据库连接
            test_result = await db_manager.fetch_one("SELECT 1 as test")
            if test_result:
                logger.info("数据库连接测试成功")
            
            # 注册定时任务（静态任务）
            self.register_jobs()
            
            # 首次加载“时间槽”并注册动态任务
            await self.refresh_time_slot_jobs()

            # 定时刷新时间槽配置，支持热更新（每60秒检查一次）
            try:
                self.scheduler.add_job(
                    func=self.refresh_time_slot_jobs,
                    trigger=IntervalTrigger(seconds=60),
                    id='refresh_time_slot_jobs',
                    name='刷新时间槽配置',
                    replace_existing=True
                )
                logger.info("已注册时间槽热更新任务 (每60秒)")
            except Exception as e:
                logger.error(f"注册时间槽热更新任务失败: {e}")
            
            # 启动调度器
            self.scheduler.start()
            logger.info("APScheduler调度器启动成功")
            logger.info(f"已注册 {len(self.scheduler.get_jobs())} 个定时任务")
            
            # 显示已注册的任务
            for job in self.scheduler.get_jobs():
                logger.info(f"任务: {job.name} ({job.id}) - 下次执行: {job.next_run_time}")
            
            return True
            
        except Exception as e:
            logger.error(f"调度器启动失败: {e}", exc_info=True)
            return False
    
    async def stop(self):
        """停止调度器Worker"""
        logger.info("停止APScheduler调度器Worker")
        
        try:
            # 关闭调度器
            if self.scheduler.running:
                self.scheduler.shutdown(wait=True)
                logger.info("调度器已停止")
            
            # 关闭数据库连接池
            await db_manager.close_all_connections()
            logger.info("数据库连接已关闭")
            
        except Exception as e:
            logger.error(f"调度器停止过程中出现错误: {e}", exc_info=True)
    
    async def run_forever(self):
        """保持Worker运行"""
        logger.info("APScheduler Worker开始运行，按Ctrl+C停止")
        
        try:
            # 启动调度器
            if not await self.start():
                logger.error("调度器启动失败，退出")
                return
            
            # 保持运行
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("接收到停止信号")
        except Exception as e:
            logger.error(f"Worker运行过程中出现错误: {e}", exc_info=True)
        finally:
            await self.stop()

async def main():
    """主入口函数"""
    logger.info("=" * 60)
    logger.info("APScheduler定时任务Worker")
    logger.info("基于ADR-004决策，独立Worker进程")
    logger.info("=" * 60)
    
    # 创建并运行Worker
    worker = SchedulerWorker()
    await worker.run_forever()

if __name__ == "__main__":
    # 运行调度器Worker
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
        sys.exit(1)
