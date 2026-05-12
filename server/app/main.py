"""
英语抽认卡后端主入口
"""
import csv
import io
import logging
import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import settings
from app.storage import get_storage, close_storage
from app.models import FlashcardCreate, PackCreate, PackUpdate, SceneCreate, SceneUpdate
from app.services.card_ai import get_card_ai

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="[%(asctime)s][%(levelname)s][%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="英语抽认卡后端 API",
    description="英语抽认卡学习网站的后端服务",
    version="1.0.0",
)

# CORS 配置（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




# ========== 应用生命周期事件 ==========


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    logger.info("Application starting up...")

    try:
        storage = await get_storage()
        count = await storage.get_flashcard_count()
        logger.info(f"Storage initialized: {count} flashcards loaded")

        # 如果数据库为空，自动从 CSV 导入
        if count == 0:
            await _auto_import_csv(storage)
    except Exception as e:
        logger.error(f"Storage initialization failed: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    logger.info("Application shutting down...")
    try:
        await close_storage()
        logger.info("Storage closed successfully")
    except Exception as e:
        logger.warning(f"Error closing storage: {e}")


async def _auto_import_csv(storage):
    """启动时自动从 CSV 导入数据"""
    from pathlib import Path

    # 查找 CSV 文件（检查多个可能的位置）
    csv_paths = [
        Path("../client/data/flashcards.csv"),
        Path("../flashcards.csv"),
        Path("data/flashcards.csv"),
    ]

    for csv_path in csv_paths:
        if csv_path.exists():
            logger.info(f"Auto-importing flashcards from {csv_path}")
            try:
                text = csv_path.read_text(encoding="utf-8")
                cards = _parse_csv_text(text)
                count = await storage.add_flashcards_bulk(cards)
                logger.info(f"Auto-imported {count} flashcards from {csv_path}")
                return
            except Exception as e:
                logger.warning(f"Failed to auto-import from {csv_path}: {e}")

    logger.info("No CSV file found for auto-import")


def _parse_csv_text(text: str) -> list[FlashcardCreate]:
    """解析 CSV 文本为 FlashcardCreate 列表"""
    cards = []
    for line in text.strip().split("\n"):
        # 找到最后一个逗号作为分隔符（因为问题中可能包含逗号）
        sep_index = line.rfind(",")
        if sep_index == -1:
            continue

        question = line[:sep_index].strip()
        answer = line[sep_index + 1 :].strip()

        if question and answer:
            cards.append(FlashcardCreate(question=question, answer=answer))
    return cards


# ========== API: 抽认卡数据 ==========


@app.get("/api/categories")
async def get_categories():
    """获取所有学习包的分类、场景和统计信息"""
    storage = await get_storage()
    packs = await storage.get_categories()
    # 同时返回旧格式 categories（兼容 client/ 旧前端）
    categories = {p["name"]: [s["name"] for s in p["scenes"]] for p in packs}
    return JSONResponse({
        "success": True,
        "packs": packs,
        "categories": categories,
    })


@app.get("/api/flashcards")
async def list_flashcards(category: Optional[str] = None, scene: Optional[str] = None):
    """获取抽认卡（支持根据category和scene进行过滤）"""
    storage = await get_storage()
    cards = await storage.list_flashcards(category=category, scene=scene)

    return JSONResponse(
        {
            "success": True,
            "count": len(cards),
            "flashcards": [card.model_dump(mode="json") for card in cards],
        }
    )


@app.get("/api/flashcards/{card_id}")
async def get_flashcard(card_id: str):
    """获取单张抽认卡"""
    storage = await get_storage()
    card = await storage.get_flashcard(card_id)

    if not card:
        raise HTTPException(status_code=404, detail="卡片不存在")

    return JSONResponse(
        {
            "success": True,
            "flashcard": card.model_dump(mode="json"),
        }
    )


@app.post("/api/flashcards/import")
async def import_flashcards(file: UploadFile = File(..., description="CSV 文件")):
    """导入 CSV 抽认卡数据"""
    storage = await get_storage()

    try:
        content = await file.read()
        text = content.decode("utf-8")
        cards = _parse_csv_text(text)

        if not cards:
            return JSONResponse(
                {"success": False, "message": "未解析到有效数据"}, status_code=400
            )

        count = await storage.add_flashcards_bulk(cards)
        total = await storage.get_flashcard_count()

        return JSONResponse(
            {
                "success": True,
                "imported": count,
                "total": total,
                "message": f"成功导入 {count} 张新卡片（共 {total} 张）",
            }
        )
    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== API: 学习记录 ==========


class RateRequest(BaseModel):
    """评分请求"""

    card_id: str = Field(description="卡片ID")
    rating: str = Field(description="评分: know | fuzzy | unknown")
    session_id: Optional[str] = Field(default=None, description="会话ID")


@app.post("/api/study/rate")
async def rate_card(request: RateRequest):
    """提交卡片评分"""
    if request.rating not in ("know", "fuzzy", "unknown"):
        raise HTTPException(
            status_code=400, detail="rating 必须为 know/fuzzy/unknown"
        )

    storage = await get_storage()

    from app.models import StudyRecordCreate

    record_create = StudyRecordCreate(
        card_id=request.card_id,
        rating=request.rating,
        session_id=request.session_id,
    )
    record = await storage.add_study_record(record_create)

    return JSONResponse(
        {
            "success": True,
            "record": record.model_dump(mode="json"),
        }
    )


@app.get("/api/study/records")
async def list_study_records(days: int = 7):
    """获取最近的学习记录"""
    storage = await get_storage()
    records = await storage.get_records_by_days(days)

    return JSONResponse(
        {
            "success": True,
            "count": len(records),
            "records": [r.model_dump(mode="json") for r in records],
        }
    )


@app.get("/api/study/stats")
async def get_study_stats():
    """获取学习统计数据"""
    storage = await get_storage()
    stats = await storage.get_study_stats()

    return JSONResponse({"success": True, **stats})


@app.get("/api/study/progress")
async def get_study_progress():
    """获取每张卡片的最新评分状态"""
    storage = await get_storage()
    progress = await storage.get_card_progress()

    return JSONResponse(
        {
            "success": True,
            "count": len(progress),
            "progress": progress,
        }
    )


# ========== API: 学习会话 ==========


@app.post("/api/session/start")
async def start_session():
    """开始新的学习会话"""
    storage = await get_storage()
    session = await storage.create_session()

    return JSONResponse(
        {
            "success": True,
            "session": session.model_dump(mode="json"),
        }
    )


@app.put("/api/session/{session_id}/end")
async def end_session(session_id: str):
    """结束学习会话"""
    storage = await get_storage()
    session = await storage.end_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    return JSONResponse(
        {
            "success": True,
            "session": session.model_dump(mode="json"),
        }
    )


@app.get("/api/session/history")
async def list_sessions(limit: int = 20):
    """获取历史会话列表"""
    storage = await get_storage()
    sessions = await storage.list_sessions(limit)

    return JSONResponse(
        {
            "success": True,
            "count": len(sessions),
            "sessions": [s.model_dump(mode="json") for s in sessions],
        }
    )


# ========== API: 学习包 / 场景 管理 ==========


@app.get("/api/packs")
async def list_packs():
    """列出全部学习包（含场景统计）"""
    storage = await get_storage()
    packs = storage.list_packs()
    return JSONResponse({
        "success": True,
        "packs": [p.model_dump(mode="json") for p in packs],
    })


@app.post("/api/packs")
async def create_pack(req: PackCreate):
    storage = await get_storage()
    try:
        meta = await storage.create_pack(req.name, req.tag or "日常生活")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse({"success": True, "pack": meta.model_dump(mode="json")})


@app.patch("/api/packs/{pack_id}")
async def update_pack(pack_id: str, req: PackUpdate):
    storage = await get_storage()
    try:
        meta = await storage.update_pack(pack_id, req.name, req.tag)
    except KeyError:
        raise HTTPException(status_code=404, detail="学习包不存在")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse({"success": True, "pack": meta.model_dump(mode="json")})


@app.delete("/api/packs/{pack_id}")
async def delete_pack(pack_id: str, force: bool = False):
    storage = await get_storage()
    try:
        await storage.delete_pack(pack_id, force=force)
    except KeyError:
        raise HTTPException(status_code=404, detail="学习包不存在")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse({"success": True})


@app.post("/api/packs/{pack_id}/scenes")
async def create_scene(pack_id: str, req: SceneCreate):
    storage = await get_storage()
    try:
        meta = await storage.create_scene(pack_id, req.name)
    except KeyError:
        raise HTTPException(status_code=404, detail="学习包不存在")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse({"success": True, "scene": meta.model_dump(mode="json")})


@app.patch("/api/packs/{pack_id}/scenes/{scene_id}")
async def update_scene(pack_id: str, scene_id: str, req: SceneUpdate):
    storage = await get_storage()
    try:
        meta = await storage.update_scene(pack_id, scene_id, req.name)
    except KeyError:
        raise HTTPException(status_code=404, detail="场景不存在")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse({"success": True, "scene": meta.model_dump(mode="json")})


@app.delete("/api/packs/{pack_id}/scenes/{scene_id}")
async def delete_scene(pack_id: str, scene_id: str, force: bool = False):
    storage = await get_storage()
    try:
        await storage.delete_scene(pack_id, scene_id, force=force)
    except KeyError:
        raise HTTPException(status_code=404, detail="场景不存在")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse({"success": True})


# ========== API: AI 卡片解析 ==========


class ParseCardsRequest(BaseModel):
    text: str = Field(description="用户粘贴的原始英语积累文本")


class CardItem(BaseModel):
    front: str
    back: str


class RefineCardRequest(BaseModel):
    front: str
    back: str
    instruction: str = Field(description="用户的修改指令")
    original_source: Optional[str] = None


class CommitCardsRequest(BaseModel):
    pack_id: Optional[str] = Field(default=None, description="已有学习包 ID")
    pack_name: Optional[str] = Field(default=None, description="新建学习包名（与 pack_id 二选一）")
    pack_tag: Optional[str] = Field(default="日常生活")
    scene_id: Optional[str] = None
    scene_name: Optional[str] = None
    cards: List[CardItem]


@app.post("/api/ai/parse-cards")
async def ai_parse_cards(req: ParseCardsRequest):
    """把用户粘贴的英语积累文本，通过 AI 解析为情境化卡片候选"""
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="文本不能为空")
    try:
        cards = await get_card_ai().parse_cards(text)
    except Exception as e:
        logger.error(f"AI parse failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    return JSONResponse({"success": True, "count": len(cards), "cards": cards})


@app.post("/api/ai/refine-card")
async def ai_refine_card(req: RefineCardRequest):
    """根据用户指令让 AI 重新生成单张卡片"""
    try:
        new_card = await get_card_ai().refine_card(
            req.front, req.back, req.instruction, req.original_source
        )
    except Exception as e:
        logger.error(f"AI refine failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    return JSONResponse({"success": True, "card": new_card})


@app.post("/api/cards/commit")
async def commit_cards(req: CommitCardsRequest):
    """把审核通过的卡片落地到指定 pack/scene；支持顺手新建 pack/scene"""
    storage = await get_storage()
    if not req.cards:
        raise HTTPException(status_code=400, detail="cards 不能为空")

    # 解析 / 创建 pack
    if req.pack_id:
        pack = storage.get_pack(req.pack_id)
        if not pack:
            raise HTTPException(status_code=404, detail="学习包不存在")
    elif req.pack_name:
        pack = storage.find_pack_by_name(req.pack_name)
        if not pack:
            try:
                pack = await storage.create_pack(req.pack_name, req.pack_tag or "日常生活")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="必须指定 pack_id 或 pack_name")

    # 解析 / 创建 scene
    if req.scene_id:
        if (pack.id, req.scene_id) not in storage.scenes:
            raise HTTPException(status_code=404, detail="场景不存在")
        scene_id = req.scene_id
    elif req.scene_name:
        scn = storage.find_scene_by_name(pack.id, req.scene_name)
        if not scn:
            try:
                scn = await storage.create_scene(pack.id, req.scene_name)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        scene_id = scn.id
    else:
        raise HTTPException(status_code=400, detail="必须指定 scene_id 或 scene_name")

    # 转 question/answer 格式：front -> question, back -> answer
    raw_cards = [{"question": c.front, "answer": c.back} for c in req.cards]
    added = await storage.add_cards_to_scene(pack.id, scene_id, raw_cards)
    return JSONResponse({
        "success": True,
        "added": len(added),
        "pack_id": pack.id,
        "scene_id": scene_id,
        "cards": [c.model_dump(mode="json") for c in added],
    })


# ========== 系统接口 ==========


@app.get("/v1/ping")
async def health_check():
    """健康检查"""
    storage = await get_storage()
    count = await storage.get_flashcard_count()
    return {"status": "ok", "service": "english_flashcard_backend", "flashcard_count": count}


# ========== 静态文件挂载 (前端) ==========

# 将前端文件挂载到根路径，这样就可以在同一个端口访问前后端了
client_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../client-v2"))
if os.path.exists(client_dir):
    app.mount("/", StaticFiles(directory=client_dir, html=True), name="static")
else:
    logger.warning(f"Frontend directory not found at {client_dir}")

# ========== 主函数 ==========

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting English Flashcard Backend on {settings.host}:{settings.port}")

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
