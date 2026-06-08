"""RSS 采集器 - 对接本地 RSSHub (localhost:1200)"""
import hashlib
import logging
import os
import re
from datetime import datetime, timezone

import feedparser
import requests

logger = logging.getLogger(__name__)

RSSHUB_BASE = os.getenv("RSSHUB_BASE", "http://localhost:1200")
FETCH_TIMEOUT = int(os.getenv("RSSHUB_TIMEOUT", "30"))

# RSSHub 路由配置
ROUTES = [
    {"name": "微博热搜", "route": "/weibo/search/hot"},
    {"name": "百度热搜", "route": "/baidu/hot"},
    {"name": "知乎日报", "route": "/zhihu/daily"},
    {"name": "豆瓣热门", "route": "/douban/latest"},
    {"name": "36氪",      "route": "/36kr/motif/1"},
    {"name": "虎嗅",      "route": "/huxiu"},
    {"name": "IT之家",    "route": "/ithome"},
    {"name": "安全客",    "route": "/anquanke"},
    {"name": "FreeBuf",   "route": "/freebuf"},
    {"name": "HackerNews","route": "/thehackernews"},
    {"name": "BBC中文",   "route": "/bbc/chinese"},
    {"name": "纽约时报",  "route": "/nytimes"},
    {"name": "Reuters",   "route": "/reuters"},
    {"name": "Solidot",   "route": "/solidot"},
]


def fetch_route(name: str, route: str) -> list[dict]:
    """从 RSSHub 拉取一个路由并解析"""
    url = f"{RSSHUB_BASE}{route}"
    logger.info("fetching %s from %s", name, url)
    try:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            logger.warning("parse error for %s: %s", name, feed.bozo_exception)
            return []
    except Exception as e:
        logger.warning("fetch %s failed: %s", name, e)
        return []

    now = datetime.now(timezone.utc).isoformat()
    items = []
    for entry in feed.entries[:30]:
        content = ""
        if hasattr(entry, "content") and entry.content:
            content = entry.content[0].get("value", "")
        elif hasattr(entry, "summary"):
            content = entry.summary
        content = re.sub(r"<[^>]+>", " ", content)
        content = re.sub(r"\s+", " ", content).strip()[:2000]

        pub = ""
        if hasattr(entry, "published"):
            pub = entry.published
        elif hasattr(entry, "updated"):
            pub = entry.updated

        items.append({
            "title": entry.get("title", "").strip() if hasattr(entry, "title") else "",
            "url": entry.get("link", "").strip() if hasattr(entry, "link") else "",
            "content": content,
            "author": entry.get("author", "").strip() if hasattr(entry, "author") else "",
            "published": pub or now,
            "collected": now,
        })

    logger.info("%s: %d items", name, len(items))
    return items


def collect_all(routes: list[dict] = None) -> list[dict]:
    """采集所有路由"""
    if routes is None:
        routes = ROUTES
    all_items = []
    for r in routes:
        items = fetch_route(r["name"], r["route"])
        for item in items:
            uid = hashlib.md5(f'{r["name"]}_{item["url"]}_{item["title"]}'.encode()).hexdigest()
            item["_id"] = uid
            item["source"] = "rsshub"
            item["platform"] = r["name"]
            item["reason"] = f"来自 RSSHub 路由 {r['route']}，平台 {r['name']}"
        all_items.extend(items)
    return all_items
