"""
抽认卡数据模型
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class Flashcard(BaseModel):
    """抽认卡"""

    id: str = Field(description="唯一标识")
    category: str = Field(default="基础口语", description="单词所属大类（如：基础口语, Shameless-S02E01）")
    scene: str = Field(default="默认场景", description="单词所属的情景剧场（如：【日常寒暄】, 【场景11：酒吧闲聊】）")
    question: str = Field(description="中文问题")
    answer: str = Field(description="英文答案")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "card_0",
                "category": "基础口语",
                "scene": "默认场景",
                "question": "用英语询问对方\"你今天怎么样？\"最常见的表达是什么？",
                "answer": "How are you today?",
                "created_at": "2026-04-02T17:00:00",
            }
        }


class FlashcardCreate(BaseModel):
    """创建抽认卡请求"""

    question: str
    answer: str
    category: Optional[str] = "基础口语"
    scene: Optional[str] = "默认场景"
