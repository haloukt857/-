# -*- coding: utf-8 -*-
"""
最小化广播服务（内存任务 + 速率控制）

功能：
- 启动一次文本消息广播任务（支持仅测试单用户）
- 遵循 Telegram Bot API 速率：私聊约 30 条/秒
- 命中 429 时读取 retry_after 并退避重试（每条最多 3 次）

不持久化：任务信息仅存在内存，进程重启后丢失。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Optional, Any

import aiohttp

from config import BOT_TOKEN
from database.db_connection import db_manager

logger = logging.getLogger(__name__)


class BroadcastJob:
    def __init__(self, job_id: str, total: int, text: str, opts: Dict[str, Any]):
        self.id = job_id
        self.status = "pending"  # pending | running | done | failed
        self.total = total
        self.sent = 0
        self.success = 0
        self.failed = 0
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None
        self.last_error: Optional[str] = None
        self.opts = opts or {}
        # 预检统计
        self.stage = "pending"  # pending | precheck | sending | done | failed
        self.prechecked_total: Optional[int] = None
        self.eligible_total: Optional[int] = None
        self.skipped_inactive: Optional[int] = None

    def as_dict(self) -> Dict[str, Any]:
        now = time.time()
        started = self.started_at or now
        elapsed = max(0.0, (now - started)) if self.started_at else 0.0
        sent = max(0, int(self.sent))
        rate = (sent / elapsed) if elapsed > 0 else 0.0
        remaining = max(0, self.total - sent)
        eta = int(remaining / rate) if rate > 0 else None
        return {
            "job_id": self.id,
            "status": self.status,
            "stage": self.stage,
            "total": self.total,
            "sent": self.sent,
            "success": self.success,
            "failed": self.failed,
            "rate": round(rate, 2),
            "eta_seconds": eta,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "last_error": self.last_error,
            "prechecked_total": self.prechecked_total,
            "eligible_total": self.eligible_total,
            "skipped_inactive": self.skipped_inactive,
        }


JOBS: Dict[str, BroadcastJob] = {}


async def _fetch_targets(test_user_id: Optional[int]) -> List[int]:
    if test_user_id:
        return [int(test_user_id)]
    try:
        rows = await db_manager.fetch_all("SELECT user_id FROM users ORDER BY user_id")
        return [int(r[0]) for r in rows]
    except Exception as e:
        logger.error(f"读取用户列表失败: {e}")
        return []


async def start_broadcast(
    text: str,
    *,
    test_user_id: Optional[int] = None,
    disable_notification: bool = False,
    protect_content: bool = False,
    precheck_active: bool = True,
    dry_run: bool = False,
) -> str:
    """启动广播任务，返回 job_id。"""
    targets = await _fetch_targets(test_user_id)
    job_id = uuid.uuid4().hex
    job = BroadcastJob(job_id, total=len(targets), text=text, opts={
        "disable_notification": bool(disable_notification),
        "protect_content": bool(protect_content),
        "precheck_active": bool(precheck_active),
        "dry_run": bool(dry_run),
    })
    JOBS[job_id] = job
    asyncio.create_task(_run_job(job_id, targets, text))
    return job_id


async def get_status(job_id: str) -> Dict[str, Any]:
    job = JOBS.get(job_id)
    if not job:
        return {"error": "job_not_found"}
    return job.as_dict()


async def _run_job(job_id: str, targets: List[int], text: str) -> None:
    job = JOBS.get(job_id)
    if not job:
        return
    if not BOT_TOKEN or not str(BOT_TOKEN).strip():
        job.status = "failed"
        job.last_error = "BOT_TOKEN 未配置"
        job.finished_at = time.time()
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    job.status = "running"
    # 若仅检测，则强制进行预检
    precheck_enabled = bool(job.opts.get("precheck_active") or job.opts.get("dry_run"))
    job.stage = "precheck" if precheck_enabled else "sending"
    job.started_at = time.time()

    # 简单的每秒窗口 30 条节流（私聊标准）
    window_start = time.monotonic()
    sent_in_window = 0

    timeout = aiohttp.ClientTimeout(total=20)
    headers = {"Content-Type": "application/json"}

    async with aiohttp.ClientSession(timeout=timeout) as session:
        # 可选：预检用户活跃性（dry_run 时强制开启）
        if precheck_enabled and targets:
            eligibles: List[int] = []
            total_pre = 0
            # 复用相同的窗口节流
            pre_window_start = time.monotonic()
            pre_sent_in_window = 0
            get_member_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
            get_chat_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChat"

            for uid in targets:
                # 节流控制（每秒最多30次请求）
                nowp = time.monotonic()
                if nowp - pre_window_start >= 1.0:
                    pre_window_start = nowp
                    pre_sent_in_window = 0
                if pre_sent_in_window >= 30:
                    await asyncio.sleep(max(0.0, 1.0 - (nowp - pre_window_start)))
                    pre_window_start = time.monotonic()
                    pre_sent_in_window = 0

                active = False
                tries = 0
                last_err = None
                while tries < 2 and not active:
                    tries += 1
                    # 优先 getChatMember（私聊可用），失败则回退 getChat
                    try:
                        async with session.get(get_member_url, params={"chat_id": int(uid), "user_id": int(uid)}) as resp:
                            data = await resp.json()
                            if data.get("ok"):
                                st = str((data.get("result") or {}).get("status", "")).lower()
                                # member/creator/administrator 视为可达
                                if st in {"member", "creator", "administrator"}:
                                    active = True
                                    break
                                # left/kicked 视为不可达
                                else:
                                    active = False
                                    break
                            else:
                                code = data.get("error_code")
                                desc = str(data.get("description"))
                                if code == 429:
                                    ra = int((data.get("parameters") or {}).get("retry_after", 1))
                                    await asyncio.sleep(max(1, ra))
                                    continue
                                # 回退 getChat
                    except Exception as e:
                        last_err = str(e)

                    # 回退：getChat
                    try:
                        async with session.get(get_chat_url, params={"chat_id": int(uid)}) as resp2:
                            data2 = await resp2.json()
                            if data2.get("ok"):
                                active = True
                                break
                            else:
                                code2 = data2.get("error_code")
                                if code2 == 429:
                                    ra2 = int((data2.get("parameters") or {}).get("retry_after", 1))
                                    await asyncio.sleep(max(1, ra2))
                                    continue
                                active = False
                                break
                    except Exception as e2:
                        last_err = str(e2)
                        active = False
                        break

                total_pre += 1
                pre_sent_in_window += 1
                if active:
                    eligibles.append(int(uid))

            job.prechecked_total = total_pre
            job.eligible_total = len(eligibles)
            job.skipped_inactive = max(0, (total_pre - len(eligibles)))
            targets = eligibles
            job.total = len(eligibles)
            # 仅检测模式：到此结束
            if job.opts.get("dry_run"):
                job.status = "done"
                job.stage = "done"
                job.finished_at = time.time()
                return
            # 进入发送阶段
            job.stage = "sending"

        # 若无可发送目标，直接完成
        if not targets:
            job.total = 0
            job.status = "done"
            job.finished_at = time.time()
            return

        for chat_id in targets:
            # 速率窗口控制
            now = time.monotonic()
            if now - window_start >= 1.0:
                window_start = now
                sent_in_window = 0
            if sent_in_window >= 30:
                await asyncio.sleep(max(0.0, 1.0 - (now - window_start)))
                window_start = time.monotonic()
                sent_in_window = 0

            payload = {
                "chat_id": int(chat_id),
                "text": text,
            }
            if job.opts.get("disable_notification"):
                payload["disable_notification"] = True
            if job.opts.get("protect_content"):
                payload["protect_content"] = True

            tries = 0
            ok = False
            last_err = None

            while tries < 3 and not ok:
                tries += 1
                try:
                    async with session.post(url, json=payload, headers=headers) as resp:
                        data = await resp.json()
                        if data.get("ok"):
                            ok = True
                            break
                        # 错误处理
                        desc = str(data.get("description"))
                        code = data.get("error_code")
                        params = data.get("parameters") or {}
                        last_err = desc
                        if code == 429:
                            retry_after = int(params.get("retry_after", 1))
                            await asyncio.sleep(max(1, retry_after))
                            continue
                        elif code in (400, 403):
                            # 常见不可恢复错误：chat not found / blocked
                            break
                        else:
                            # 其他错误短暂退避
                            await asyncio.sleep(0.5)
                except Exception as e:
                    last_err = str(e)
                    await asyncio.sleep(0.5)

            sent_in_window += 1
            job.sent += 1
            if ok:
                job.success += 1
            else:
                job.failed += 1
                job.last_error = last_err

    job.status = "done"
    job.stage = "done"
    job.finished_at = time.time()
