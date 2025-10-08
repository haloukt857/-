# -*- coding: utf-8 -*-
"""
一个轻量级进程内异步任务队列，用于把耗时的外部I/O（如 Telegram API）改为后台执行。

使用方式：
    from services.task_queue import enqueue_task, start_task_workers
    await start_task_workers()  # 在应用启动时调用一次
    enqueue_task(coro_func, *args, **kwargs)

特性：
    - 简单可靠：asyncio.Queue + 后台 worker
    - 自动重试：最多3次，指数退避
    - 无持久化：进程内最佳努力；需要持久化可后续升级为 DB 任务表
"""

import asyncio
import logging
from typing import Awaitable, Callable, Any, Tuple

logger = logging.getLogger(__name__)

_queue: asyncio.Queue | None = None
_workers_started: bool = False
_worker_tasks: list[asyncio.Task] = []


async def start_task_workers(worker_count: int = 3) -> None:
    """启动后台 worker（幂等）。"""
    global _queue, _workers_started, _worker_tasks
    if _workers_started:
        return
    if _queue is None:
        _queue = asyncio.Queue()
    _workers_started = True
    for i in range(max(1, worker_count)):
        t = asyncio.create_task(_worker_loop(i))
        _worker_tasks.append(t)
    logger.info(f"后台任务队列已启动，workers={worker_count}")


def enqueue_task(coro_func: Callable[..., Awaitable[Any]], *args, **kwargs) -> None:
    """把协程函数任务入队，由后台 worker 执行。"""
    if _queue is None:
        # 在未显式启动时也允许入队；创建临时队列，稍后 start_task_workers 会接管
        loop = asyncio.get_event_loop()
        logger.debug("任务队列尚未启动，临时创建")
        _init_tmp_queue()
    _queue.put_nowait((coro_func, args, kwargs, 0))


def _init_tmp_queue():
    global _queue
    if _queue is None:
        _queue = asyncio.Queue()


async def _worker_loop(worker_id: int):
    global _queue
    assert _queue is not None
    while True:
        func, args, kwargs, retry = await _queue.get()
        try:
            await func(*args, **kwargs)
        except Exception as e:
            if retry < 3:
                backoff = 2 ** retry
                logger.warning(f"任务执行失败，重试{retry+1}/3，backoff={backoff}s: {e}")
                await asyncio.sleep(backoff)
                await _queue.put((func, args, kwargs, retry + 1))
            else:
                logger.error(f"任务执行失败（已达最大重试）: {e}")
        finally:
            _queue.task_done()

