"""
英语抽认卡后端主入口
"""
import csv
import io
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import settings
from app.storage import get_storage, close_storage
from app.models import FlashcardCreate
from app.voice.router import router as voice_router

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

# 注册语音交互 WebSocket 路由
app.include_router(voice_router)


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


# ========== 系统接口 ==========


@app.get("/v1/ping")
async def health_check():
    """健康检查"""
    storage = await get_storage()
    count = await storage.get_flashcard_count()
    return {"status": "ok", "service": "english_flashcard_backend", "flashcard_count": count}


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
