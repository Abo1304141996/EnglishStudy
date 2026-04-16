"""
学习会话数据模型
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class StudySession(BaseModel):
    """学习会话"""

    id: str = Field(description="会话ID")
    started_at: datetime = Field(default_factory=datetime.now, description="开始时间")
    ended_at: Optional[datetime] = Field(default=None, description="结束时间")
    total_cards: int = Field(default=0, description="学习卡片数")
    know_count: int = Field(default=0, description="认识数量")
    fuzzy_count: int = Field(default=0, description="模糊数量")
    unknown_count: int = Field(default=0, description="不认识数量")


class StudySessionCreate(BaseModel):
    """创建学习会话请求"""
    pass  # 会话创建不需要额外参数
