"""
学习记录数据模型
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class StudyRecord(BaseModel):
    """学习记录"""

    id: str = Field(description="记录ID")
    card_id: str = Field(description="关联的卡片ID")
    rating: str = Field(description="评分: know | fuzzy | unknown")
    studied_at: datetime = Field(default_factory=datetime.now, description="学习时间")
    session_id: Optional[str] = Field(default=None, description="所属学习会话ID")

    # SRS 预留字段
    ease_factor: float = Field(default=2.5, description="SM-2 难度因子")
    interval: int = Field(default=0, description="下次复习间隔（天）")
    next_review: Optional[datetime] = Field(default=None, description="下次复习时间")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "rec_001",
                "card_id": "card_0",
                "rating": "know",
                "studied_at": "2026-04-02T17:00:00",
                "session_id": "sess_001",
            }
        }


class StudyRecordCreate(BaseModel):
    """创建学习记录请求"""

    card_id: str
    rating: str  # know | fuzzy | unknown
    session_id: Optional[str] = None
