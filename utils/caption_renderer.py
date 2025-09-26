# -*- coding: utf-8 -*-
"""
频道贴文渲染（MarkdownV2）统一工具

唯一真源：此处生成的 MarkdownV2 caption 同时用于
- 调度器定时发布（scheduler）
- Web 后台“立即发布”（post_mgmt_service）
- 机器人端“我的资料”预览（handlers/user）

这样可以避免多处实现导致样式漂移。
"""

from __future__ import annotations

import re
from html import escape as _esc_html
from typing import Dict, Any, List, Tuple

from database.db_connection import db_manager


def _esc_md(s: str) -> str:
    if not isinstance(s, str):
        s = str(s or "")
    # 转义 MarkdownV2 保留字符
    return re.sub(r"([_\*\[\]\(\)~`>#+\-=|{}\.!])", r"\\\1", s)


async def _build_caption_context(
    merchant: Dict[str, Any], bot_username: str
) -> Dict[str, Any]:
    """构造渲染所需上下文（供 MD / HTML 共享），避免文案与顺序漂移。"""
    mid = merchant.get("id")
    did = merchant.get("district_id")
    cid = merchant.get("city_id")
    name = merchant.get("name") or "-"
    district_name = merchant.get("district_name") or "-"
    p_price = str(merchant.get("p_price") or "").strip()
    pp_price = str(merchant.get("pp_price") or "").strip()
    adv_text = (merchant.get("adv_sentence") or "").strip()

    bot_u = (bot_username or "").lstrip("@")
    link_merchant = f"https://t.me/{bot_u}?start=m_{mid}" if bot_u and mid else ""
    link_district = f"https://t.me/{bot_u}?start=d_{did}" if bot_u and did else ""
    city_suffix = f"_c_{cid}" if cid else ""
    link_price_p = f"https://t.me/{bot_u}?start=price_p_{p_price}{city_suffix}" if bot_u and p_price else ""
    link_price_pp = f"https://t.me/{bot_u}?start=price_pp_{pp_price}{city_suffix}" if bot_u and pp_price else ""
    link_report = f"https://t.me/{bot_u}?start=report_{mid}" if bot_u and mid else ""

    # 关键词（最多3个）
    tags: List[Tuple[str, str]] = []  # (显示名, 链接URL或空)
    try:
        rows: List[Dict[str, Any]] = await db_manager.fetch_all(
            "SELECT k.id, k.name FROM keywords k JOIN merchant_keywords mk ON mk.keyword_id = k.id "
            "WHERE mk.merchant_id = ? ORDER BY k.display_order ASC, k.id ASC LIMIT 3",
            (mid,),
        )
        for r in rows or []:
            kid, nm = r["id"], r["name"]
            url = f"https://t.me/{bot_u}?start=kw_{kid}" if bot_u and kid else ""
            tags.append((nm, url))
    except Exception:
        tags = []

    return {
        "name": name,
        "district_name": district_name,
        "p_price": p_price,
        "pp_price": pp_price,
        "adv_text": adv_text,
        "link_merchant": link_merchant,
        "link_district": link_district,
        "link_price_p": link_price_p,
        "link_price_pp": link_price_pp,
        "link_report": link_report,
        "tags": tags,
    }


async def render_channel_caption_md(
    merchant: Dict[str, Any],
    bot_username: str,
    *,
    offers: List[Dict[str, Any]] | None = None,
    reviews: List[Dict[str, Any]] | None = None,
) -> str:
    """
    渲染频道 caption（MarkdownV2）。

    Args:
        merchant: 包含商户字段的字典（至少需 id/name/district_id/district_name/p_price/pp_price/adv_sentence）
        bot_username: 机器人用户名（不带 @）

    Returns:
        str: MarkdownV2 格式 caption，长度需自行把控（<= 1024）。
    """
    ctx = await _build_caption_context(merchant, bot_username)

    # 字段/片段（MD）
    name_md = (
        f"[{_esc_md(ctx['name'])}]({ctx['link_merchant']})" if ctx["link_merchant"] else _esc_md(ctx["name"])
    )
    district_md = (
        f"[{_esc_md(ctx['district_name'])}]({ctx['link_district']})"
        if ctx["link_district"]
        else _esc_md(ctx["district_name"])
    )
    p_md_link = (
        f"[{_esc_md(ctx['p_price'])}/p]({ctx['link_price_p']})" if ctx["link_price_p"] else _esc_md(ctx["p_price"] + "/p")
    )
    pp_md_link = (
        f"[{_esc_md(ctx['pp_price'])}/pp]({ctx['link_price_pp']})" if ctx["link_price_pp"] else _esc_md(ctx["pp_price"] + "/pp")
    )
    report_md = f"[{_esc_md('报告')}]({ctx['link_report']})" if ctx["link_report"] else _esc_md("报告")
    adv_md = _esc_md(ctx["adv_text"])

    # 标签（MD）
    tag_parts: List[str] = []
    for nm, url in ctx["tags"]:
        if url:
            tag_parts.append(f"[{_esc_md('#'+nm)}]({url})")
        else:
            tag_parts.append(_esc_md('#' + nm))
    tags_md = " ".join(tag_parts)

    # 动态片段：优惠与评价（聚合成 MarkdownV2 文本）
    offers = offers or []
    reviews = reviews or []
    offers_md = " ".join([_esc_md(o.get("text", "")) for o in offers if o.get("text")])
    reviews_md = "\n".join([
        f"• [{_esc_md(r.get('text','评价'))}]({_esc_html(r.get('url',''))})" if r.get("url") else f"• {_esc_md(r.get('text','评价'))}"
        for r in reviews
        if r
    ])

    # 统一代码控制样式（不走数据库模板）
    # 默认首行使用块引用，使频道内展示更突出
    body = [
        (f"> {adv_md}" if adv_md else None),
        "",
        f"💃🏻昵称：{name_md}",
        f"🌈地区：{district_md}",
        f"🎫课费：{p_md_link}      {pp_md_link}",
        f"🏷️标签：{tags_md}",
        f"✍️评价：「{report_md}」",
    ]
    if reviews_md:
        body.append("")
        body.append("📝评价：")
        body.append(reviews_md)
    if offers_md:
        body.append("")
        body.append(f"🎉优惠：{offers_md}")

    return "\n".join([line for line in body if line is not None])


async def render_channel_caption_html(
    merchant: Dict[str, Any],
    bot_username: str,
    *,
    offers: List[Dict[str, Any]] | None = None,
    reviews: List[Dict[str, Any]] | None = None,
) -> str:
    """渲染频道 caption 的 HTML 版本，用于 Web 预览。

    注意：
    - 仅输出受控标签：blockquote/div/a
    - 对所有动态文本进行 HTML 转义
    - 仅对我们拼装的 deeplink 生成可点击 <a>
    - 为避免 Markdown 细节偏差，直接从结构化数据渲染
    """
    ctx = await _build_caption_context(merchant, bot_username)

    def a_or_text(text: str, href: str) -> str:
        t = _esc_html(text)
        h = (href or "").strip()
        # 白名单：仅允许我们自己的 t.me 深链
        if h.startswith("https://t.me/"):
            return f"<a href=\"{_esc_html(h)}\">{t}</a>"
        return t

    lines: List[str] = []
    # 首行引用块（可空）
    adv = ctx["adv_text"].strip()
    if adv:
        lines.append(f"<blockquote class=\"tg-adv\">{_esc_html(adv)}</blockquote>")

    # 其它行
    name_html = a_or_text(ctx["name"], ctx["link_merchant"])
    district_html = a_or_text(ctx["district_name"], ctx["link_district"])
    price_p_html = a_or_text(f"{ctx['p_price']}/p", ctx["link_price_p"]) if ctx["p_price"] else _esc_html("/p")
    price_pp_html = a_or_text(f"{ctx['pp_price']}/pp", ctx["link_price_pp"]) if ctx["pp_price"] else _esc_html("/pp")

    # 标签
    tag_items: List[str] = []
    for nm, url in ctx["tags"]:
        tag_items.append(a_or_text(f"#{nm}", url))
    tags_html = " ".join(tag_items)

    # 固定行
    lines.append(f"<div class=\"line\">💃🏻昵称：{name_html}</div>")
    lines.append(f"<div class=\"line\">🌈地区：{district_html}</div>")
    lines.append(f"<div class=\"line\">🎫课费：{price_p_html} &nbsp;&nbsp;&nbsp; {price_pp_html}</div>")
    lines.append(f"<div class=\"line\">🏷️标签：{tags_html}</div>")
    report_html = a_or_text("报告", ctx["link_report"])
    lines.append(f"<div class=\"line\">✍️评价：「{report_html}」</div>")

    # 可选区块：评价与优惠（仅文本，避免外链）
    offers = offers or []
    reviews = reviews or []
    if reviews:
        lines.append("<div class=\"line\">📝评价：</div>")
        for r in reviews:
            if not r:
                continue
            txt = _esc_html(r.get("text", "评价"))
            # 不生成外链（白名单仅允许 t.me 深链）
            lines.append(f"<div class=\"line\">• {txt}</div>")
    if offers:
        offer_text = " ".join([_esc_html(o.get("text", "")) for o in offers if o.get("text")])
        if offer_text:
            lines.append(f"<div class=\"line\">🎉优惠：{offer_text}</div>")

    return "\n".join(lines)
