"""
存储管理器抽象基类
定义 StudyStorage 的接口规范，支持多种存储后端
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

from app.models.flashcard import Flashcard, FlashcardCreate
from app.models.study_record import StudyRecord, StudyRecordCreate
from app.models.study_session import StudySession


class BaseStudyStorage(ABC):
    """学习数据存储抽象基类

    支持以下存储后端：
    - json: JSON 文件存储（默认，适合个人使用/开发环境）
    - postgres: PostgreSQL 存储（后续，适合多用户/生产环境）
    """

    # ========== 抽认卡管理 ==========

    @abstractmethod
    async def list_flashcards(self, category: Optional[str] = None, scene: Optional[str] = None) -> List[Flashcard]:
        """列出所有抽认卡（支持分类和场景过滤）"""
        pass

    @abstractmethod
    async def get_categories(self) -> List[Dict[str, Any]]:
        """获取丰富的分类目录结构，返回列表，每项包含:
        name, tag, scene_count, total_cards, scenes: [{name, card_count}]
        """
        pass

    @abstractmethod
    async def get_flashcard(self, card_id: str) -> Optional[Flashcard]:
        """根据ID获取抽认卡"""
        pass

    @abstractmethod
    async def add_flashcard(self, card: FlashcardCreate) -> Flashcard:
        """添加抽认卡"""
        pass

    @abstractmethod
    async def add_flashcards_bulk(self, cards: List[FlashcardCreate]) -> int:
        """批量添加抽认卡（CSV 导入用）

        Returns:
            成功导入的数量
        """
        pass

    @abstractmethod
    async def get_flashcard_count(self) -> int:
        """获取抽认卡总数"""
        pass

    # ========== 学习记录管理 ==========

    @abstractmethod
    async def add_study_record(self, record: StudyRecordCreate) -> StudyRecord:
        """添加学习记录"""
        pass

    @abstractmethod
    async def get_card_progress(self) -> Dict[str, str]:
        """获取每张卡片的最新评分状态

        Returns:
            {card_id: latest_rating} 映射
        """
        pass

    @abstractmethod
    async def get_records_by_days(self, days: int = 7) -> List[StudyRecord]:
        """获取最近N天的学习记录"""
        pass

    @abstractmethod
    async def get_study_stats(self) -> Dict[str, Any]:
        """获取学习统计数据

        Returns:
            {total, studied, know, fuzzy, unknown, accuracy, daily_counts}
        """
        pass

    @abstractmethod
    async def get_daily_counts(self, days: int = 30) -> Dict[str, int]:
        """获取每日学习数量（日历热力图数据）

        Returns:
            {"2026-04-01": 15, "2026-04-02": 8, ...}
        """
        pass

    # ========== 学习会话管理 ==========

    @abstractmethod
    async def create_session(self) -> StudySession:
        """创建新的学习会话"""
        pass

    @abstractmethod
    async def end_session(self, session_id: str) -> Optional[StudySession]:
        """结束学习会话"""
        pass

    @abstractmethod
    async def list_sessions(self, limit: int = 20) -> List[StudySession]:
        """列出最近的学习会话"""
        pass

    # ========== 生命周期管理 ==========

    async def initialize(self) -> None:
        """初始化存储（子类可选实现）"""
        pass

    async def close(self) -> None:
        """关闭连接（子类可选实现）"""
        pass
