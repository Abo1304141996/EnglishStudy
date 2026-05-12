"""
学习包 / 场景数据模型
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SceneMeta(BaseModel):
    """场景元信息（不含卡片，用于列表展示）"""

    id: str = Field(description="场景 slug 唯一标识")
    name: str = Field(description="场景显示名")
    card_count: int = Field(default=0, description="卡片数量")
    created_at: datetime = Field(default_factory=datetime.now)


class Scene(BaseModel):
    """场景完整数据（含卡片）"""

    id: str
    name: str
    pack_id: str
    cards: List[dict] = Field(default_factory=list, description="该场景下的所有卡片")
    created_at: datetime = Field(default_factory=datetime.now)


class PackMeta(BaseModel):
    """学习包元信息"""

    id: str = Field(description="学习包 slug 唯一标识")
    name: str = Field(description="学习包显示名")
    tag: str = Field(default="日常生活", description="分类标签")
    created_at: datetime = Field(default_factory=datetime.now)


class PackSummary(BaseModel):
    """学习包摘要（用于前端列表）"""

    id: str
    name: str
    tag: str
    scene_count: int
    total_cards: int
    scenes: List[dict]  # [{id, name, card_count}]


class PackCreate(BaseModel):
    name: str
    tag: Optional[str] = "日常生活"


class PackUpdate(BaseModel):
    name: Optional[str] = None
    tag: Optional[str] = None


class SceneCreate(BaseModel):
    name: str


class SceneUpdate(BaseModel):
    name: Optional[str] = None
