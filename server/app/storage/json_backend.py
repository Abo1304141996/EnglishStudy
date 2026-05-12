"""
JSON 文件存储后端（目录化）

新版数据结构：
data/
├── packs/
│   └── <pack_id>/
│       ├── meta.json          # PackMeta
│       └── scenes/
│           └── <scene_id>.json # {meta, cards}
├── study_records.json
└── study_sessions.json

启动时若检测到旧版 flashcards.json，会自动迁移到新结构。
"""
import json
import logging
import re
import shutil
import unicodedata
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from app.config import settings
from app.models.flashcard import Flashcard, FlashcardCreate
from app.models.pack import PackMeta, PackSummary, PackCreate, SceneMeta
from app.models.study_record import StudyRecord, StudyRecordCreate
from app.models.study_session import StudySession
from app.storage.base import BaseStudyStorage

logger = logging.getLogger(__name__)


# ---------- 辅助：slug ----------

_SLUG_SAFE = re.compile(r"[^a-zA-Z0-9_\-]+")


def _slugify(name: str) -> str:
    """生成文件名安全的 slug。中文等非 ASCII 字符 → 哈希后缀"""
    base = unicodedata.normalize("NFKC", name).strip()
    ascii_part = _SLUG_SAFE.sub("-", base).strip("-").lower()
    if ascii_part:
        return ascii_part[:40]
    # 全部是非 ASCII（如纯中文）→ 用短 hash
    return "p-" + uuid.uuid5(uuid.NAMESPACE_DNS, base).hex[:10]


def _unique_slug(base: str, existing: set) -> str:
    if base not in existing:
        return base
    i = 2
    while f"{base}-{i}" in existing:
        i += 1
    return f"{base}-{i}"


# ---------- 主类 ----------


class JSONStudyStorage(BaseStudyStorage):
    """目录化 JSON 存储"""

    def __init__(self):
        self.data_dir = Path(settings.data_dir)
        self.packs_dir = self.data_dir / "packs"
        self.records_file = self.data_dir / "study_records.json"
        self.sessions_file = self.data_dir / "study_sessions.json"

        # pack_id -> PackMeta
        self.packs: Dict[str, PackMeta] = {}
        # (pack_id, scene_id) -> SceneMeta
        self.scenes: Dict[Tuple[str, str], SceneMeta] = {}
        # (pack_id, scene_id) -> List[Flashcard]
        self.scene_cards: Dict[Tuple[str, str], List[Flashcard]] = {}

        self.records: List[StudyRecord] = []
        self.sessions: List[StudySession] = []

    # ========== 初始化 ==========

    async def initialize(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.packs_dir.mkdir(parents=True, exist_ok=True)

        # 迁移旧数据
        legacy_file = self.data_dir / "flashcards.json"
        if legacy_file.exists() and not any(self.packs_dir.iterdir()):
            logger.info("Detected legacy flashcards.json, migrating...")
            try:
                self._migrate_legacy(legacy_file)
            except Exception as e:
                logger.error(f"Legacy migration failed: {e}", exc_info=True)

        await self._load_packs()
        self.records = await self._load_simple(self.records_file, StudyRecord)
        self.sessions = await self._load_simple(self.sessions_file, StudySession)

        total_cards = sum(len(v) for v in self.scene_cards.values())
        logger.info(
            f"JSONStudyStorage initialized: "
            f"{len(self.packs)} packs, {len(self.scenes)} scenes, "
            f"{total_cards} cards, {len(self.records)} records"
        )

    # ---------- 旧数据迁移 ----------

    def _migrate_legacy(self, legacy_file: Path) -> None:
        """把单一 flashcards.json 拆分到 packs/<id>/scenes/<id>.json"""
        raw = json.loads(legacy_file.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return

        # 按 (category, scene) 聚合
        grouped: Dict[str, Dict[str, Any]] = {}
        for item in raw:
            cat = item.get("category") or "基础口语"
            scn = item.get("scene") or "默认场景"
            tag = item.get("tag") or "日常生活"

            if cat not in grouped:
                grouped[cat] = {"tag": tag, "scenes": {}}
            grouped[cat]["scenes"].setdefault(scn, []).append(item)

        # 落盘
        used_pack_slugs: set = set()
        for cat_name, info in grouped.items():
            pack_slug = _unique_slug(_slugify(cat_name), used_pack_slugs)
            used_pack_slugs.add(pack_slug)
            pack_dir = self.packs_dir / pack_slug
            scenes_dir = pack_dir / "scenes"
            scenes_dir.mkdir(parents=True, exist_ok=True)

            pack_meta = PackMeta(id=pack_slug, name=cat_name, tag=info["tag"])
            (pack_dir / "meta.json").write_text(
                json.dumps(pack_meta.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            used_scene_slugs: set = set()
            for scn_name, items in info["scenes"].items():
                scn_slug = _unique_slug(_slugify(scn_name), used_scene_slugs)
                used_scene_slugs.add(scn_slug)

                cards = []
                for idx, item in enumerate(items):
                    cards.append({
                        "id": item.get("id") or f"{pack_slug}-{scn_slug}-{idx}",
                        "category": cat_name,
                        "scene": scn_name,
                        "tag": info["tag"],
                        "question": item.get("question", ""),
                        "answer": item.get("answer", ""),
                        "created_at": item.get("created_at") or datetime.now().isoformat(),
                    })

                scene_data = {
                    "meta": {
                        "id": scn_slug,
                        "name": scn_name,
                        "card_count": len(cards),
                        "created_at": datetime.now().isoformat(),
                    },
                    "cards": cards,
                }
                (scenes_dir / f"{scn_slug}.json").write_text(
                    json.dumps(scene_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

        # 备份旧文件
        backup = legacy_file.with_suffix(".json.bak")
        shutil.move(str(legacy_file), str(backup))
        logger.info(f"Legacy migration done. Backup: {backup}")

    # ---------- 加载 ----------

    async def _load_packs(self) -> None:
        self.packs.clear()
        self.scenes.clear()
        self.scene_cards.clear()

        if not self.packs_dir.exists():
            return

        for pack_dir in sorted(self.packs_dir.iterdir()):
            if not pack_dir.is_dir():
                continue
            meta_file = pack_dir / "meta.json"
            if not meta_file.exists():
                continue
            try:
                pack_meta = PackMeta(**json.loads(meta_file.read_text(encoding="utf-8")))
                self.packs[pack_meta.id] = pack_meta
            except Exception as e:
                logger.warning(f"Failed to load pack meta {meta_file}: {e}")
                continue

            scenes_dir = pack_dir / "scenes"
            if not scenes_dir.exists():
                continue
            for scn_file in sorted(scenes_dir.glob("*.json")):
                try:
                    scn_data = json.loads(scn_file.read_text(encoding="utf-8"))
                    scn_meta = SceneMeta(**scn_data["meta"])
                    cards = [Flashcard(**c) for c in scn_data.get("cards", [])]
                    scn_meta.card_count = len(cards)
                    self.scenes[(pack_meta.id, scn_meta.id)] = scn_meta
                    self.scene_cards[(pack_meta.id, scn_meta.id)] = cards
                except Exception as e:
                    logger.warning(f"Failed to load scene {scn_file}: {e}")

    @staticmethod
    async def _load_simple(filepath: Path, model_class) -> list:
        if not filepath.exists():
            return []
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            return [model_class(**item) for item in data]
        except Exception as e:
            logger.warning(f"Failed to load {filepath}: {e}")
            return []

    @staticmethod
    async def _save_simple(filepath: Path, data: list) -> None:
        try:
            json_data = [item.model_dump(mode="json") for item in data]
            filepath.write_text(
                json.dumps(json_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"Failed to save {filepath}: {e}")

    def _save_scene(self, pack_id: str, scene_id: str) -> None:
        meta = self.scenes.get((pack_id, scene_id))
        cards = self.scene_cards.get((pack_id, scene_id), [])
        if not meta:
            return
        meta.card_count = len(cards)
        scn_file = self.packs_dir / pack_id / "scenes" / f"{scene_id}.json"
        scn_file.parent.mkdir(parents=True, exist_ok=True)
        scn_file.write_text(
            json.dumps(
                {
                    "meta": meta.model_dump(mode="json"),
                    "cards": [c.model_dump(mode="json") for c in cards],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _save_pack_meta(self, pack_id: str) -> None:
        meta = self.packs.get(pack_id)
        if not meta:
            return
        pack_dir = self.packs_dir / pack_id
        pack_dir.mkdir(parents=True, exist_ok=True)
        (pack_dir / "meta.json").write_text(
            json.dumps(meta.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ========== Pack / Scene 管理 ==========

    def list_packs(self) -> List[PackSummary]:
        result = []
        for pack_id, meta in self.packs.items():
            scenes = [
                {"id": sid, "name": s.name, "card_count": s.card_count}
                for (pid, sid), s in self.scenes.items()
                if pid == pack_id
            ]
            total_cards = sum(s["card_count"] for s in scenes)
            result.append(PackSummary(
                id=pack_id,
                name=meta.name,
                tag=meta.tag,
                scene_count=len(scenes),
                total_cards=total_cards,
                scenes=scenes,
            ))
        return result

    def get_pack(self, pack_id: str) -> Optional[PackMeta]:
        return self.packs.get(pack_id)

    def find_pack_by_name(self, name: str) -> Optional[PackMeta]:
        for p in self.packs.values():
            if p.name == name:
                return p
        return None

    def find_scene_by_name(self, pack_id: str, name: str) -> Optional[SceneMeta]:
        for (pid, sid), s in self.scenes.items():
            if pid == pack_id and s.name == name:
                return s
        return None

    async def create_pack(self, name: str, tag: str = "日常生活") -> PackMeta:
        if self.find_pack_by_name(name):
            raise ValueError(f"学习包 '{name}' 已存在")
        existing_ids = set(self.packs.keys())
        pack_id = _unique_slug(_slugify(name), existing_ids)
        meta = PackMeta(id=pack_id, name=name, tag=tag)
        self.packs[pack_id] = meta
        (self.packs_dir / pack_id / "scenes").mkdir(parents=True, exist_ok=True)
        self._save_pack_meta(pack_id)
        return meta

    async def update_pack(self, pack_id: str, name: Optional[str], tag: Optional[str]) -> PackMeta:
        meta = self.packs.get(pack_id)
        if not meta:
            raise KeyError(pack_id)
        if name and name != meta.name:
            other = self.find_pack_by_name(name)
            if other and other.id != pack_id:
                raise ValueError(f"学习包 '{name}' 已存在")
            meta.name = name
        if tag:
            meta.tag = tag
        self._save_pack_meta(pack_id)
        # 同步更新该 pack 下所有 cards 的 category/tag
        for (pid, sid), cards in self.scene_cards.items():
            if pid != pack_id:
                continue
            for c in cards:
                if name:
                    c.category = name
                if tag:
                    c.tag = tag
            self._save_scene(pid, sid)
        return meta

    async def delete_pack(self, pack_id: str, force: bool = False) -> None:
        meta = self.packs.get(pack_id)
        if not meta:
            raise KeyError(pack_id)
        scene_ids = [sid for (pid, sid) in self.scenes.keys() if pid == pack_id]
        if scene_ids and not force:
            raise ValueError("学习包下仍有场景，无法删除（请使用 force 或先清空场景）")

        # 删目录
        pack_dir = self.packs_dir / pack_id
        if pack_dir.exists():
            shutil.rmtree(pack_dir)

        for sid in scene_ids:
            self.scenes.pop((pack_id, sid), None)
            self.scene_cards.pop((pack_id, sid), None)
        self.packs.pop(pack_id, None)

    async def create_scene(self, pack_id: str, name: str) -> SceneMeta:
        if pack_id not in self.packs:
            raise KeyError(pack_id)
        if self.find_scene_by_name(pack_id, name):
            raise ValueError(f"场景 '{name}' 已存在")
        existing_ids = {sid for (pid, sid) in self.scenes.keys() if pid == pack_id}
        scene_id = _unique_slug(_slugify(name), existing_ids)
        meta = SceneMeta(id=scene_id, name=name, card_count=0)
        self.scenes[(pack_id, scene_id)] = meta
        self.scene_cards[(pack_id, scene_id)] = []
        self._save_scene(pack_id, scene_id)
        return meta

    async def update_scene(self, pack_id: str, scene_id: str, name: Optional[str]) -> SceneMeta:
        meta = self.scenes.get((pack_id, scene_id))
        if not meta:
            raise KeyError((pack_id, scene_id))
        if name and name != meta.name:
            other = self.find_scene_by_name(pack_id, name)
            if other and other.id != scene_id:
                raise ValueError(f"场景 '{name}' 已存在")
            meta.name = name
            # 同步更新该场景下所有 cards 的 scene 字段
            for c in self.scene_cards.get((pack_id, scene_id), []):
                c.scene = name
        self._save_scene(pack_id, scene_id)
        return meta

    async def delete_scene(self, pack_id: str, scene_id: str, force: bool = False) -> None:
        meta = self.scenes.get((pack_id, scene_id))
        if not meta:
            raise KeyError((pack_id, scene_id))
        cards = self.scene_cards.get((pack_id, scene_id), [])
        if cards and not force:
            raise ValueError("场景下仍有卡片，无法删除（请使用 force）")
        scn_file = self.packs_dir / pack_id / "scenes" / f"{scene_id}.json"
        if scn_file.exists():
            scn_file.unlink()
        self.scenes.pop((pack_id, scene_id), None)
        self.scene_cards.pop((pack_id, scene_id), None)

    # ========== 抽认卡管理（兼容旧接口） ==========

    async def list_flashcards(
        self, category: Optional[str] = None, scene: Optional[str] = None
    ) -> List[Flashcard]:
        result: List[Flashcard] = []
        for (pid, sid), cards in self.scene_cards.items():
            pack_meta = self.packs.get(pid)
            scn_meta = self.scenes.get((pid, sid))
            if not pack_meta or not scn_meta:
                continue
            if category and pack_meta.name != category and pid != category:
                continue
            if scene and scn_meta.name != scene and sid != scene:
                continue
            result.extend(cards)
        return result

    async def list_cards_by_id(self, pack_id: str, scene_id: str) -> List[Flashcard]:
        return list(self.scene_cards.get((pack_id, scene_id), []))

    async def get_categories(self) -> List[Dict[str, Any]]:
        """兼容旧接口：返回 PackSummary 格式（dict 化）"""
        return [p.model_dump(mode="json") for p in self.list_packs()]

    async def get_flashcard(self, card_id: str) -> Optional[Flashcard]:
        for cards in self.scene_cards.values():
            for c in cards:
                if c.id == card_id:
                    return c
        return None

    async def add_flashcard(self, card: FlashcardCreate) -> Flashcard:
        # 兼容旧接口：根据 category/scene 寻找或创建 pack/scene
        pack = self.find_pack_by_name(card.category or "基础口语")
        if not pack:
            pack = await self.create_pack(card.category or "基础口语", card.tag or "日常生活")
        scn = self.find_scene_by_name(pack.id, card.scene or "默认场景")
        if not scn:
            scn = await self.create_scene(pack.id, card.scene or "默认场景")

        new_card = Flashcard(
            id=f"card_{uuid.uuid4().hex[:8]}",
            category=pack.name,
            scene=scn.name,
            tag=pack.tag,
            question=card.question,
            answer=card.answer,
        )
        self.scene_cards[(pack.id, scn.id)].append(new_card)
        self._save_scene(pack.id, scn.id)
        return new_card

    async def add_flashcards_bulk(self, cards: List[FlashcardCreate]) -> int:
        existing_questions = {c.question for cs in self.scene_cards.values() for c in cs}
        added = 0
        # 按 (category, scene) 分组以减少 IO
        groups: Dict[Tuple[str, str], List[FlashcardCreate]] = {}
        for card in cards:
            if card.question in existing_questions:
                continue
            key = (card.category or "基础口语", card.scene or "默认场景")
            groups.setdefault(key, []).append(card)
            existing_questions.add(card.question)

        for (cat_name, scn_name), items in groups.items():
            pack = self.find_pack_by_name(cat_name)
            if not pack:
                pack = await self.create_pack(cat_name, items[0].tag or "日常生活")
            scn = self.find_scene_by_name(pack.id, scn_name)
            if not scn:
                scn = await self.create_scene(pack.id, scn_name)

            for card in items:
                new_card = Flashcard(
                    id=f"card_{uuid.uuid4().hex[:8]}",
                    category=pack.name,
                    scene=scn.name,
                    tag=pack.tag,
                    question=card.question,
                    answer=card.answer,
                )
                self.scene_cards[(pack.id, scn.id)].append(new_card)
                added += 1
            self._save_scene(pack.id, scn.id)
        if added > 0:
            logger.info(f"Bulk imported {added} flashcards")
        return added

    async def add_cards_to_scene(
        self, pack_id: str, scene_id: str, cards: List[Dict[str, str]]
    ) -> List[Flashcard]:
        """向指定场景批量追加卡片（AI 解析后入库用）"""
        if (pack_id, scene_id) not in self.scenes:
            raise KeyError((pack_id, scene_id))
        pack = self.packs[pack_id]
        scn = self.scenes[(pack_id, scene_id)]
        added: List[Flashcard] = []
        for c in cards:
            new_card = Flashcard(
                id=f"card_{uuid.uuid4().hex[:8]}",
                category=pack.name,
                scene=scn.name,
                tag=pack.tag,
                question=c.get("question", "").strip(),
                answer=c.get("answer", "").strip(),
            )
            if not new_card.question or not new_card.answer:
                continue
            self.scene_cards[(pack_id, scene_id)].append(new_card)
            added.append(new_card)
        self._save_scene(pack_id, scene_id)
        return added

    async def get_flashcard_count(self) -> int:
        return sum(len(v) for v in self.scene_cards.values())

    # ========== 学习记录 ==========

    async def add_study_record(self, record: StudyRecordCreate) -> StudyRecord:
        new_record = StudyRecord(
            id=f"rec_{uuid.uuid4().hex[:8]}",
            card_id=record.card_id,
            rating=record.rating,
            session_id=record.session_id,
        )
        self.records.append(new_record)
        await self._save_simple(self.records_file, self.records)

        if record.session_id:
            await self._update_session_stats(record.session_id, record.rating)
        return new_record

    async def _update_session_stats(self, session_id: str, rating: str) -> None:
        for session in self.sessions:
            if session.id == session_id:
                session.total_cards += 1
                if rating == "know":
                    session.know_count += 1
                elif rating == "fuzzy":
                    session.fuzzy_count += 1
                elif rating == "unknown":
                    session.unknown_count += 1
                await self._save_simple(self.sessions_file, self.sessions)
                break

    async def get_card_progress(self) -> Dict[str, str]:
        progress: Dict[str, str] = {}
        for record in sorted(self.records, key=lambda r: r.studied_at):
            progress[record.card_id] = record.rating
        return progress

    async def get_records_by_days(self, days: int = 7) -> List[StudyRecord]:
        cutoff = datetime.now() - timedelta(days=days)
        return [r for r in self.records if r.studied_at >= cutoff]

    async def get_study_stats(self) -> Dict[str, Any]:
        total = await self.get_flashcard_count()
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

    # ========== 学习会话 ==========

    async def create_session(self) -> StudySession:
        session = StudySession(id=f"sess_{uuid.uuid4().hex[:8]}")
        self.sessions.append(session)
        await self._save_simple(self.sessions_file, self.sessions)
        return session

    async def end_session(self, session_id: str) -> Optional[StudySession]:
        for session in self.sessions:
            if session.id == session_id:
                session.ended_at = datetime.now()
                await self._save_simple(self.sessions_file, self.sessions)
                return session
        return None

    async def list_sessions(self, limit: int = 20) -> List[StudySession]:
        sorted_sessions = sorted(self.sessions, key=lambda s: s.started_at, reverse=True)
        return sorted_sessions[:limit]
