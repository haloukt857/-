# -*- coding: utf-8 -*-
"""
媒体代理路由

负责处理所有与媒体文件展示相关的路由，特别是核心的机器人代理功能。
"""

import logging
import io
from typing import Any
from starlette.routing import Route
from starlette.responses import Response
from starlette.exceptions import HTTPException
from starlette.requests import Request

# 导入项目模块
from database.db_media import media_db

logger = logging.getLogger(__name__)

async def media_proxy(request: Request):
    """
    核心媒体代理路由。
    根据URL中的media_id，从Telegram实时下载文件并作为HTTP响应返回。
    
    使用 request.app.state.bot 获取Bot实例（标准Starlette/FastAPI模式）
    """
    media_id = request.path_params.get('media_id')
    if not media_id:
        raise HTTPException(status_code=400, detail="缺少媒体ID")

    # 优先使用直连Telegram API的方式，避免依赖 app.state.bot
    # 读取机器人令牌
    from config import BOT_TOKEN
    bot_token = BOT_TOKEN
    if not bot_token:
        logger.error("媒体代理失败：未配置BOT_TOKEN。")
        raise HTTPException(status_code=500, detail="服务器未配置机器人令牌")

    try:
        media_id = int(media_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="无效的媒体ID格式")

    # 1. 从数据库获取 telegram_file_id
    telegram_file_id = await media_db.get_telegram_file_id(media_id)
    if not telegram_file_id:
        logger.warning(f"请求的 media_id {media_id} 在数据库中不存在。")
        raise HTTPException(status_code=404, detail="找不到指定的媒体文件")

    try:
        # 2. 通过HTTP请求Telegram API获取文件路径并流式回传
        import aiohttp
        api_base = f"https://api.telegram.org/bot{bot_token}"
        file_base = f"https://api.telegram.org/file/bot{bot_token}"

        # 支持从环境变量读取代理，并允许走系统代理（trust_env=True）
        import os
        proxy_url = os.getenv('TG_PROXY') or os.getenv('HTTPS_PROXY') or os.getenv('HTTP_PROXY')
        async with aiohttp.ClientSession(trust_env=True) as session:
            # 获取 file_path
            getfile_kwargs = {"timeout": aiohttp.ClientTimeout(total=15)}
            if proxy_url:
                getfile_kwargs["proxy"] = proxy_url
            async with session.get(f"{api_base}/getFile", params={"file_id": telegram_file_id}, **getfile_kwargs) as r:
                data = await r.json()
                if not data.get('ok'):
                    raise RuntimeError(f"getFile失败: {data}")
                file_path = data['result']['file_path']

            # 根据扩展名推断 MIME
            import os
            ext = os.path.splitext(file_path)[1].lower()
            mime_map = {
                '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                '.gif': 'image/gif', '.webp': 'image/webp', '.mp4': 'video/mp4'
            }
            media_type = mime_map.get(ext, 'application/octet-stream')

            # 拉取文件并以完整响应返回（避免 chunked 传输在浏览器侧报错）
            file_kwargs = {"timeout": aiohttp.ClientTimeout(total=30)}
            if proxy_url:
                file_kwargs["proxy"] = proxy_url
            async with session.get(f"{file_base}/{file_path}", **file_kwargs) as rf:
                if rf.status != 200:
                    raise RuntimeError(f"下载文件失败: HTTP {rf.status}")
                content = await rf.read()
                return Response(content, media_type=media_type, headers={"Content-Length": str(len(content))})

    except Exception as e:
        # 处理各种可能的Telegram API错误
        logger.error(f"处理 media_id {media_id} (file_id: {telegram_file_id}) 时发生Telegram API或IO错误: {e}")
        raise HTTPException(status_code=502, detail="无法从Telegram获取媒体文件")

# 导出路由列表
media_routes = [
    Route("/media-proxy/{media_id:int}", endpoint=media_proxy, methods=["GET"])
]
