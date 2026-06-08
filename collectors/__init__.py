"""采集管理器"""
import logging

from collectors.rss import collect_all

logger = logging.getLogger(__name__)


def collect_and_enqueue() -> list[dict]:
    """采集 RSSHub 数据（后续可推入 Redis）"""
    logger.info("=== RSSHub collection ===")
    items = collect_all()
    logger.info("Total: %d items", len(items))
    return items
