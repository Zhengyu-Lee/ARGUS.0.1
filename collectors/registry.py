"""采集器注册表 - RSSHub 为主，直连爬虫为兜底"""
import logging
import os
import re
from datetime import datetime, timezone
import uuid
import feedparser
import requests as _req

logger = logging.getLogger("collector")

RSSHUB_BASE = os.getenv("RSSHUB_BASE", "http://localhost:1200")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ──────────── 数据源配置 ────────────
# primary: 优先走 RSSHub；fallback 是直连爬虫函数名（None 则 RSSHub 失败时跳过）
# RSSHub 路由格式: /<platform>/<route>
SOURCES = {
    "36kr":         {"name": "36氪",        "rsshub": "/36kr/motif/1",         "fallback": "_fetch_36kr"},
    "hackernews":   {"name": "The Hacker News", "rsshub": "/thehackernews",   "fallback": "_fetch_thn"},
    "anquanke":     {"name": "安全KER",      "rsshub": "/anquanke",            "fallback": "_fetch_anquanke"},
    "weibo":        {"name": "微博热搜",     "rsshub": "/weibo/search/hot",    "fallback": None},
    "baidu":        {"name": "百度热搜",     "rsshub": "/baidu/hot",           "fallback": None},
    "ithome":       {"name": "IT之家",       "rsshub": "/ithome",              "fallback": None},
    "huxiu":        {"name": "虎嗅网",       "rsshub": "/huxiu",               "fallback": None},
    "sspai":        {"name": "少数派",       "rsshub": "/sspai/index",         "fallback": None},
    "zhihu":        {"name": "知乎日报",     "rsshub": "/zhihu/daily",         "fallback": None},
    "freebuf":      {"name": "FreeBuf",      "rsshub": "/freebuf",             "fallback": None},
    "solidot":      {"name": "Solidot",      "rsshub": "/solidot",             "fallback": None},
    "douban":       {"name": "豆瓣热门",     "rsshub": "/douban/latest",       "fallback": None},
    "bbc":          {"name": "BBC中文",      "rsshub": "/bbc/chinese",         "fallback": None},
    "nytimes":      {"name": "纽约时报",     "rsshub": "/nytimes",             "fallback": None},
    "reuters":      {"name": "Reuters",      "rsshub": "/reuters",             "fallback": None},
    "theverge":     {"name": "The Verge",    "rsshub": "/theverge",            "fallback": None},
    "techcrunch":   {"name": "TechCrunch",   "rsshub": "/techcrunch",          "fallback": None},
    "pingwest":     {"name": "品玩",         "rsshub": "/pingwest",            "fallback": None},
    "geekpark":     {"name": "极客公园",     "rsshub": "/geekpark",            "fallback": None},
    "producthunt":  {"name": "Product Hunt", "rsshub": "/producthunt/today",   "fallback": None},
    "github_trend": {"name": "GitHub Trending", "rsshub": "/github/trending/daily", "fallback": None},
    "apnews":       {"name": "AP News",      "rsshub": "/apnews",              "fallback": None},
    "wired":        {"name": "Wired",        "rsshub": "/wired",               "fallback": None},
    "arstechnica":  {"name": "Ars Technica", "rsshub": "/arstechnica",         "fallback": None},
    "bleeping":     {"name": "BleepingComputer", "rsshub": "/bleepingcomputer", "fallback": None},
    "theregister":  {"name": "The Register", "rsshub": "/theregister",         "fallback": None},
    "securityweek": {"name": "SecurityWeek", "rsshub": "/securityweek",        "fallback": None},
    "darkreading":  {"name": "Dark Reading", "rsshub": "/darkreading",         "fallback": None},
    "portswigger":  {"name": "PortSwigger",  "rsshub": "/portswigger",         "fallback": None},
    "mit_tr":       {"name": "MIT Tech Review", "rsshub": "/technologyreview", "fallback": None},
    "zaobao":       {"name": "联合早报",     "rsshub": "/zaobao",              "fallback": None},
}


def _fetch_rsshub(sid, cfg):
    """通过 RSSHub 采集"""
    items = []
    url = RSSHUB_BASE + cfg["rsshub"]
    try:
        resp = _req.get(url, timeout=15)
        feed = feedparser.parse(resp.content)
        for e in feed.entries[:30]:
            c = ""
            if hasattr(e, "content") and e.content:
                c = e.content[0].get("value", "")
            elif hasattr(e, "summary"):
                c = e.summary
            c = re.sub(r"<[^>]+>", " ", c).strip()[:2000]
            items.append({
                "_id": uuid.uuid4().hex, "source": "rsshub", "platform": sid,
                "title": e.get("title", "").strip() if hasattr(e, "title") else "",
                "url": e.get("link", "").strip() if hasattr(e, "link") else "",
                "content": c,
                "author": e.get("author", "").strip() if hasattr(e, "author") else cfg["name"],
                "collected": datetime.now(timezone.utc).isoformat(),
                "reason": f"来源: RSSHub/{cfg['name']}",
            })
    except Exception as e:
        logger.warning("RSSHub %s failed: %s", sid, e)
        return None  # 返回 None 表示失败，触发 fallback
    return items


# ──── 直连爬虫（fallback）────

def _fetch_thn():
    import html.parser
    items = []
    try:
        resp = _req.get("https://thehackernews.com/", timeout=15, headers={"User-Agent": UA})
        class Parser(html.parser.HTMLParser):
            def __init__(self):
                super().__init__(); self.in_s = False; self.in_t = False; self.in_d = False
                self.u = ""; self.t = ""; self.d = ""; self.a = []
            def handle_starttag(self, tag, attrs):
                d = dict(attrs)
                if tag == "a" and d.get("class") == "story-link":
                    self.in_s = True; self.u = d.get("href", "")
                if self.in_s:
                    if tag == "h2" and d.get("class") == "home-title": self.in_t = True
                    if tag == "div" and d.get("class") == "home-desc": self.in_d = True
            def handle_data(self, data):
                if self.in_t and data.strip(): self.t = data.strip(); self.in_t = False
                elif self.in_d and data.strip(): self.d = data.strip()
            def handle_endtag(self, tag):
                if tag == "a" and self.in_s:
                    self.in_s = False
                    if self.u and self.t: self.a.append((self.u, self.t, self.d[:500]))
                    self.u = ""; self.t = ""; self.d = ""
        p = Parser()
        idx = resp.text.find("<div class='blog-posts clear'>")
        if idx >= 0:
            p.feed(resp.text[idx:])
            for u, t, d in p.a[:20]:
                items.append({"_id": uuid.uuid4().hex, "source": "direct", "platform": "hackernews",
                    "url": u, "title": t, "content": d, "author": "The Hacker News",
                    "collected": datetime.now(timezone.utc).isoformat(), "reason": "来源: The Hacker News"})
    except Exception as e:
        logger.warning("THN direct fail: %s", e)
    return items

def _fetch_anquanke():
    items = []
    try:
        resp = _req.get("https://www.anquanke.com/news", timeout=15, headers={"User-Agent": UA})
        for m in re.finditer(r'<a href="/post/id/(\d+)"[^>]*>.*?<div class="title"[^>]*>(.*?)</div>', resp.text, re.DOTALL):
            pid, title = m.group(1), re.sub(r"<[^>]+>", " ", m.group(2)).strip()
            if pid and title:
                items.append({"_id": uuid.uuid4().hex, "source": "direct", "platform": "anquanke",
                    "url": "https://www.anquanke.com/post/id/" + pid, "title": title, "content": "", "author": "安全KER",
                    "collected": datetime.now(timezone.utc).isoformat(), "reason": "来源: 安全KER"})
    except Exception as e:
        logger.warning("AnQuanke direct fail: %s", e)
    return items

def _fetch_36kr():
    items = []
    try:
        resp = _req.get("https://36kr.com/feed", timeout=15, headers={"User-Agent": UA})
        feed = feedparser.parse(resp.content)
        for e in feed.entries[:20]:
            c = ""; 
            if hasattr(e, "content") and e.content: c = e.content[0].get("value", "")
            elif hasattr(e, "summary"): c = e.summary
            c = re.sub(r"<[^>]+>", " ", c).strip()[:2000]
            items.append({"_id": uuid.uuid4().hex, "source": "direct", "platform": "36kr",
                "url": e.get("link", ""), "title": e.get("title", ""), "content": c,
                "author": e.get("author", "36氪"), "collected": datetime.now(timezone.utc).isoformat(),
                "reason": "来源: 36氪RSS"})
    except Exception as e:
        logger.warning("36kr direct fail: %s", e)
    return items


# fallback 函数映射
_FALLBACKS = {
    "_fetch_thn": _fetch_thn,
    "_fetch_anquanke": _fetch_anquanke,
    "_fetch_36kr": _fetch_36kr,
}


def fetch_all():
    """主采集函数：RSSHub 优先，失败则直连兜底"""
    all_items = []
    for sid, cfg in SOURCES.items():
        # 尝试 RSSHub
        items = _fetch_rsshub(sid, cfg)
        if items is None:
            # RSSHub 失败，尝试 fallback
            fb_name = cfg.get("fallback")
            if fb_name and fb_name in _FALLBACKS:
                items = _FALLBACKS[fb_name]()
                logger.info("Fallback %s: %d items", sid, len(items) if items else 0)
            else:
                items = []
                logger.warning("No fallback for %s", sid)
        if items:
            all_items.extend(items)
    logger.info("Total collected: %d items", len(all_items))
    return all_items
