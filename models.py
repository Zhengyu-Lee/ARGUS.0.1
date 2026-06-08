"""数据模型 - 基于 ARGUS types 精简"""
import uuid
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class RawData(db.Model):
    """原始采集数据"""
    __tablename__ = "raw_data"

    id = db.Column(db.String(64), primary_key=True, default=lambda: uuid.uuid4().hex)
    source = db.Column(db.String(32), nullable=False, default="rsshub")
    platform = db.Column(db.String(64), default="")
    url = db.Column(db.String(1024), default="")
    title = db.Column(db.String(512), default="")
    content = db.Column(db.Text, default="")
    author = db.Column(db.String(128), default="")
    published = db.Column(db.DateTime, default=datetime.utcnow)
    collected = db.Column(db.DateTime, default=datetime.utcnow)
    metadata_json = db.Column(db.Text, default="{}")

    # 推送原因（采集时记录）
    reason = db.Column(db.Text, default="")

    # AI 分析结果
    confidence = db.Column(db.Integer, default=0)
    category = db.Column(db.String(32), default="")
    tags = db.Column(db.Text, default="")
    sentiment = db.Column(db.String(16), default="neutral")
    ai_analysis = db.Column(db.Text, default="")      # AI分析摘要
    ai_reasoning = db.Column(db.Text, default="")     # AI研判逻辑

    # 审核状态
    reviewed = db.Column(db.Boolean, default=False)
    decision = db.Column(db.String(16), default="pending")
    reviewer = db.Column(db.String(64), default="")
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reject_reason = db.Column(db.Text, default="")

    def to_dict(self):
        return {
            "id": self.id,
            "source": self.source,
            "platform": self.platform,
            "url": self.url,
            "title": self.title,
            "content": self.content[:2000] if self.content else "",
            "author": self.author,
            "published": self.published.isoformat() if self.published else "",
            "collected": self.collected.isoformat() if self.collected else "",
            "reason": self.reason or "",
            "confidence": self.confidence,
            "category": self.category,
            "tags": self.tags.split(",") if self.tags else [],
            "sentiment": self.sentiment,
            "ai_analysis": self.ai_analysis or "",
            "ai_reasoning": self.ai_reasoning or "",
            "reviewed": self.reviewed,
            "decision": self.decision,
            "reviewer": self.reviewer,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else "",
            "reject_reason": self.reject_reason or "",
        }
