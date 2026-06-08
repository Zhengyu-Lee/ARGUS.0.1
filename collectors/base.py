"""采集器基类 - 统一数据模型"""
import logging
import uuid
import re
from datetime import datetime, timezone
import requests as _req
import feedparser

logger = logging.getLogger("collector")

class Article:
    """统一数据模型"""
    def __init__(self, title="", url="", content="", author="", platform="",
                 source="", reason=""):
        self._id = uuid.uuid4().hex
        self.title = title
        self.url = url
        self.content = content
        self.author = author
        self.platform = platform
        self.source = source or "scraper"
        self.collected = datetime.now(timezone.utc).isoformat()
        self.reason = reason

    def to_dict(self):
        return {
            "_id": self._id, "title": self.title, "url": self.url,
            "content": self.content[:5000], "author": self.author,
            "platform": self.platform, "source": self.source,
            "collected": self.collected, "reason": self.reason,
        }


class BaseScraper:
    """爬虫基类 - 所有数据源继承此类"""
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    def __init__(self, source_id, name, url, type_="rss", **kwargs):
        self.id = source_id
        self.name = name
        self.url = url
        self.type = type_  # rss / scrape / mock
        self.enabled = kwargs.get("enabled", True)
        self.interval = kwargs.get("interval", 300)
        self.category = kwargs.get("category", "other")
        self.extra = kwargs

    def fetch(self):
        """子类重写此方法"""
        raise NotImplementedError

    def get(self, url=None, **kwargs):
        """统一 HTTP GET 请求"""
        headers = {"User-Agent": self.UA}
        headers.update(kwargs.pop("headers", {}))
        return _req.get(url or self.url, timeout=kwargs.pop("timeout", 15),
                        headers=headers, **kwargs)

    def make_item(self, title="", url="", content="", author="", reason=""):
        """创建统一数据条目"""
        return Article(
            title=title.strip(), url=url.strip(),
            content=re.sub(r"<[^>]+>", " ", content).strip()[:2000],
            author=author, platform=self.id, source=self.type,
            reason=reason or f"来源: {self.name}",
        ).to_dict()


class RSSScraper(BaseScraper):
    """RSS/Atom 订阅采集器（一行配置即可）"""
    def fetch(self):
        items = []
        try:
            resp = _req.get(self.url, timeout=15, headers={"User-Agent": self.UA})
            feed = feedparser.parse(resp.content)
            for e in feed.entries[:30]:
                c = ""
                if hasattr(e, "content") and e.content:
                    c = e.content[0].get("value", "")
                elif hasattr(e, "summary"):
                    c = e.summary
                items.append(self.make_item(
                    title=e.get("title", ""),
                    url=e.get("link", "") if hasattr(e, "link") else "",
                    content=c,
                    author=e.get("author", self.name) if hasattr(e, "author") else self.name,
                ))
            logger.info("%s: %d items (RSS)", self.name, len(items))
        except Exception as e:
            logger.warning("%s fetch fail: %s", self.name, e)
        return items


class MockScraper(BaseScraper):
    """模拟数据采集器（用于测试或API不可用的情况）"""
    def __init__(self, source_id, name, data, **kwargs):
        super().__init__(source_id, name, url="", type_="mock", **kwargs)
        self.mock_data = data

    def fetch(self):
        items = []
        for title, content, author in self.mock_data:
            items.append(self.make_item(
                title=title, content=content, author=author,
                reason=f"模拟数据 - {self.name}"
            ))
        logger.info("%s: %d items (Mock)", self.name, len(items))
        return items
