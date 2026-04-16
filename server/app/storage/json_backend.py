"""
JSON 文件存储后端
适合个人使用和开发环境
"""
import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

from app.config import settings
from app.models.flashcard import Flashcard, FlashcardCreate
from app.models.study_record import StudyRecord, StudyRecordCreate
from app.models.study_session import StudySession
from app.storage.base import BaseStudyStorage

logger = logging.getLogger(__name__)


class JSONStudyStorage(BaseStudyStorage):
    """JSON 文件存储实现"""

    def __init__(self):
        self.data_dir = Path(settings.data_dir)
        self.flashcards_file = self.data_dir / "flashcards.json"
        self.records_file = self.data_dir / "study_records.json"
        self.sessions_file = self.data_dir / "study_sessions.json"

        self.flashcards: List[Flashcard] = []
        self.records: List[StudyRecord] = []
        self.sessions: List[StudySession] = []

    async def initialize(self) -> None:
        """初始化：加载所有数据文件"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        await self._load_all()
        logger.info(
            f"JSONStudyStorage initialized: "
            f"{len(self.flashcards)} cards, "
            f"{len(self.records)} records, "
            f"{len(self.sessions)} sessions"
        )

    async def _load_all(self) -> None:
        """加载所有数据"""
        self.flashcards = await self._load_file(
            self.flashcards_file, Flashcard
        )
        self.records = await self._load_file(
            self.records_file, StudyRecord
        )
        self.sessions = await self._load_file(
            self.sessions_file, StudySession
        )

    @staticmethod
    async def _load_file(filepath: Path, model_class) -> list:
        """从 JSON 文件加载数据"""
        if not filepath.exists():
            return []
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            return [model_class(**item) for item in data]
        except Exception as e:
            logger.warning(f"Failed to load {filepath}: {e}")
            return []

    async def _save_file(self, filepath: Path, data: list) -> None:
        """保存数据到 JSON 文件"""
        try:
            json_data = [
                item.model_dump(mode="json") for item in data
            ]
            filepath.write_text(
                json.dumps(json_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"Failed to save {filepath}: {e}")

    # ========== 抽认卡管理 ==========

    async def list_flashcards(self, category: Optional[str] = None, scene: Optional[str] = None) -> List[Flashcard]:
        result = self.flashcards
        if category:
            result = [c for c in result if c.category == category]
        if scene:
            result = [c for c in result if c.scene == scene]
        return result

    async def get_categories(self) -> List[Dict[str, Any]]:
        """获取丰富的分类目录结构"""
        # 先按 category 聚合
        cat_data: Dict[str, Dict] = {}
        for card in self.flashcards:
            cat = card.category or "基础口语"
            scn = card.scene or "默认场景"
            tag = getattr(card, 'tag', '日常生活') or "日常生活"

            if cat not in cat_data:
                cat_data[cat] = {"tag": tag, "scenes": {}}
            if scn not in cat_data[cat]["scenes"]:
                cat_data[cat]["scenes"][scn] = 0
            cat_data[cat]["scenes"][scn] += 1

        # 转换为前端期望的列表格式
        result = []
        for cat_name, info in cat_data.items():
            scenes_list = [{"name": s, "card_count": c} for s, c in info["scenes"].items()]
            total_cards = sum(s["card_count"] for s in scenes_list)
            result.append({
                "name": cat_name,
                "tag": info["tag"],
                "scene_count": len(scenes_list),
                "total_cards": total_cards,
                "scenes": scenes_list,
            })
        return result

    async def get_flashcard(self, card_id: str) -> Optional[Flashcard]:
        for card in self.flashcards:
            if card.id == card_id:
                return card
        return None

    async def add_flashcard(self, card: FlashcardCreate) -> Flashcard:
        new_card = Flashcard(
            id=f"card_{len(self.flashcards)}",
            category=card.category or "基础口语",
            scene=card.scene or "默认场景",
            question=card.question,
            answer=card.answer,
        )
        self.flashcards.append(new_card)
        await self._save_file(self.flashcards_file, self.flashcards)
        return new_card

    async def add_flashcards_bulk(self, cards: List[FlashcardCreate]) -> int:
        """批量导入抽认卡，自动去重（基于 question 字段）"""
        existing_questions = {c.question for c in self.flashcards}
        added = 0
        start_id = len(self.flashcards)

        for card in cards:
            if card.question not in existing_questions:
                new_card = Flashcard(
                    id=f"card_{start_id + added}",
                    category=card.category or "基础口语",
                    scene=card.scene or "默认场景",
                    question=card.question,
                    answer=card.answer,
                )
                self.flashcards.append(new_card)
                existing_questions.add(card.question)
                added += 1

        if added > 0:
            await self._save_file(self.flashcards_file, self.flashcards)
            logger.info(f"Bulk imported {added} flashcards")
        return added

    async def get_flashcard_count(self) -> int:
        return len(self.flashcards)

    # ========== 学习记录管理 ==========

    async def add_study_record(self, record: StudyRecordCreate) -> StudyRecord:
        new_record = StudyRecord(
            id=f"rec_{uuid.uuid4().hex[:8]}",
            card_id=record.card_id,
            rating=record.rating,
            session_id=record.session_id,
        )
        self.records.append(new_record)
        await self._save_file(self.records_file, self.records)

        # 更新会话统计
        if record.session_id:
            await self._update_session_stats(record.session_id, record.rating)

        return new_record

    async def _update_session_stats(self, session_id: str, rating: str) -> None:
        """更新会话的统计数据"""
        for session in self.sessions:
            if session.id == session_id:
                session.total_cards += 1
                if rating == "know":
                    session.know_count += 1
                elif rating == "fuzzy":
                    session.fuzzy_count += 1
                elif rating == "unknown":
                    session.unknown_count += 1
                await self._save_file(self.sessions_file, self.sessions)
                break

    async def get_card_progress(self) -> Dict[str, str]:
        """获取每张卡片的最新评分"""
        progress: Dict[str, str] = {}
        # 按时间排序，后面的覆盖前面的
        for record in sorted(self.records, key=lambda r: r.studied_at):
            progress[record.card_id] = record.rating
        return progress

    async def get_records_by_days(self, days: int = 7) -> List[StudyRecord]:
        cutoff = datetime.now() - timedelta(days=days)
        return [r for r in self.records if r.studied_at >= cutoff]

    async def get_study_stats(self) -> Dict[str, Any]:
        total = len(self.flashcards)
        progress = await self.get_card_progress()
        studied = len(progress)

        know = sum(1 for r in progress.values() if r == "know")
        fuzzy = sum(1 for r in progress.values() if r == "fuzzy")
        unknown = sum(1 for r in progress.values() if r == "unknown")
        accuracy = round((know / studied * 100) if studied > 0 else 0)

        daily_counts = await self.get_daily_counts(30)

        return {
            "total": total,
            "studied": studied,
            "know": know,
            "fuzzy": fuzzy,
            "unknown": unknown,
            "accuracy": accuracy,
            "daily_counts": daily_counts,
        }

    async def get_daily_counts(self, days: int = 30) -> Dict[str, int]:
        cutoff = datetime.now() - timedelta(days=days)
        counts: Dict[str, int] = {}
        for record in self.records:
            if record.studied_at >= cutoff:
                date_str = record.studied_at.strftime("%Y-%m-%d")
                counts[date_str] = counts.get(date_str, 0) + 1
        return counts

    # ========== 学习会话管理 ==========

    async def create_session(self) -> StudySession:
        session = StudySession(
            id=f"sess_{uuid.uuid4().hex[:8]}",
        )
        self.sessions.append(session)
        await self._save_file(self.sessions_file, self.sessions)
        return session

    async def end_session(self, session_id: str) -> Optional[StudySession]:
        for session in self.sessions:
            if session.id == session_id:
                session.ended_at = datetime.now()
                await self._save_file(self.sessions_file, self.sessions)
                return session
        return None

    async def list_sessions(self, limit: int = 20) -> List[StudySession]:
        sorted_sessions = sorted(
            self.sessions, key=lambda s: s.started_at, reverse=True
        )
        return sorted_sessions[:limit]
